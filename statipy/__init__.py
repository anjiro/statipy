"""
A simple static site generator. It will use .md files to generate
variables used to render Jinja2 templates.
"""
import os, sys, shutil, re, logging
import jinja2
import dateutil.parser
from   codecs      import open
from   collections import defaultdict

try:
	import coloredlogs
except:
	pass
else:
	fmt = '%(asctime)s %(levelname)s %(message)s'
	coloredlogs.install(level='WARN', milliseconds=True, fmt=fmt)


_default_vars = {
	'DEFAULT_LANG': 'en',
}


def search_parents(path, filename, stop='/'):
	"""Search path and its parents for the given filename. Return the
	full absolute path to the file, including the filename. Return None if
	the root of the drive is reached and nothing is found."""
	if path == stop:
		return None
	f = os.path.basename(filename)
	if f != filename:
		raise NameError("Filename must be without path")
	c = os.path.join(path, f)
	if os.path.exists(c):
		return c
	p = os.path.abspath(os.path.normpath(os.path.join(path, os.path.pardir)))
	if p == path:
		return None
	return search_parents(p, filename, stop)



def get_meta(lines):
	"""Extract the metadata from a set of lines representing a file.
	Convert each metadata key to lower case.  Return a tuple
	(metadata, remaining_lines) where metadata is a dict. Attempt to
	interpret values from medata, converting to date, numbers, or lists."""
	#Load all of the initial lines with key: value; stop processing
	# key/values on the first blank line or if there's no colon in the line
	# or if it doesn't start with a letter
	meta = {}
	for i,l in enumerate(lines):
		if re.match('^\s*$|^[^A-Za-z]', l) or ':' not in l:
			break
		key, val = l.split(':', 1)
		key = key.lower().strip()
		val = val.strip()
		if val == 'None':
			continue

		if key == 'date':
			meta[key] = dateutil.parser.parse(val)
			continue

		#If the key is plural and there's a comma in val, interpret it as
		# a list
		if key.endswith('s') and ',' in val:
			meta[key] = re.split(r'\s*,\s*', val)
			continue

		#Try to convert the value to a number
		try:
			v = float(val)
		except:
			meta[key] = val.strip()
		else:
			if v.is_integer():
				meta[key] = int(v)
			else:
				meta[key] = v

	return meta, lines[i+1:]



class ParentLoader(jinja2.BaseLoader):
	"""A Jinja2 template loader that searches the path and all parent
	directories for the necessary template."""
	def __init__(self, path, stop='/', default=None):
		"""The path and its parents will be searched for the template,
		stopping when the value of stop is reached. If a default template
		name is specified, however, when this name is requested parent
		directories will _not_ be searched."""
		self.path    = path
		self.stop    = stop
		self.default = default

	def get_source(self, environment, template):
		if template == self.default:
			path = template
		elif os.path.sep in template:
			path = template
		else:
			logging.debug('search_parents({}, {}, {})'.format(self.path, template, self.stop))
			path = search_parents(self.path, template, self.stop)
		if path is None or not os.path.exists(path):
			raise jinja2.TemplateNotFound(template,
					"Can't find a matching file" if path is None else
					"Path '{}' doesn't exist".format(path))
		mtime = os.path.getmtime(path)
		with open(path) as f:
			source = f.read()
		return source, path, lambda: mtime == os.path.getmtime(path)

		



class Statipy(object):
	"""The class that does everything."""
	def __init__(self, **kwargs):
		"""Pass options as kwargs. Currently supported options are:
			content_dir       - the directory to search for content to render
			output_dir        - the directory in which to store the output
			skip_dirs         - a list of subdirectories in content_dir to skip
			default_template  - the default file to use as a template
			jinja_markdown    - attempt to render jinja in Markdown (default: True)
			jinja2_filters    - a dict of user-defined filters
			jinja2_tests      - a dict of user-defined tests
			jinja2_extensions - a list of user-defined extensions
			callbacks         - dict of functions to be run at different points

			These options can also be stored in a dict called "options" in
			site_config.py.
		"""
		self.options = {
			'content_dir':        'content',       #Where to look for content
			'output_dir':         'output',        #Where to put output
			'default_template':   'default.jinja', #Use if not specified in .md files
			'root_subdir':        None,            #Put files here in site root
			'jinja_markdown':     True,            #Render Jinja in Markdown
			'date_from_filename': True,            #If no 'Date:' in meta, try filename
			'callbacks':          {},              #Callback to run functions on Environment
		}

		self.root = os.getcwd()
		self.templ_vars = _default_vars

		self.callback('init_start')

		#Attempt to load templ_vars and options from site_config.py
		try:
			import site_config
		except ImportError:
			logging.debug("ImportError in loading site_config.py. Current "
					"path is: {}; files I see:\n{}".format(self.root,
						os.listdir(self.root)))
			sys.stderr.write('Error importing site_config.py or file not '
					'found. Are you in the right directory? Exiting.\n')
			sys.exit(-1)
		else:
			try:
				from site_config import templ_vars
			except ImportError:
				logging.info("No templ_vars in site_config.py")
			else:
				self.templ_vars.update(templ_vars)

			try:
				from site_config import options
			except ImportError:
				logging.info("No options in site_config.py")
			else:
				self.options.update(options)

		self.options.update(kwargs)

		logging.info("options: {0}".format(self.options))

		try:
			from site_config import markdown
			self.markdown = markdown
		except ImportError:
			from markdown import Markdown
			self.markdown = Markdown(extensions=['markdown.extensions.extra',
				'markdown.extensions.codehilite', 'markdown.extensions.smarty'])

		self.callback('init_end')


	def callback(self, callback_name, context=None):
		"""Call a callback named callback_name in the callbacks dict,
		providing optional context to the callback."""
		logging.info("Call callback '{}'".format(callback_name))
		self.options['callbacks'].get(callback_name, lambda c: None)(context)

	
	def generate_site(self):
		destfiles = self.prepare_output()
		self.load_pages(destfiles=destfiles)
		self.callback('end_run')


	def prepare_output(self):
		"""Walk through the output directory and find what files are there
		so we can remove or replace them later."""
		destfiles = []
		curdir = os.getcwd()
		if not os.path.exists(self.options['output_dir']):
			os.mkdir(self.options['output_dir'])
		os.chdir(self.options['output_dir'])
		for dirpath, _, filenames in os.walk('.'):
			if dirpath == '.':
				destfiles.extend(filenames)
			else:
				p = os.path.relpath(dirpath)
				destfiles.extend([os.path.join(p, f) for f in filenames])
		os.chdir(curdir)

		return destfiles


	def load_pages(self, destfiles):
		"""Walk through the content directory and look for .md files which
		we can use as input to render template files."""
		#A dict of dicts to store the contents of _ directories. The first-
		# level key is the parent directory of the _ dir; the second-level
		# key is the name of the _ dir without the '_'. The value is a
		# list of rendered pages.
		extravars = defaultdict(dict)

		#Walk through the directory bottom-up so that we get any
		# subdirectories with extra variables first.
		for root, dirs, files in os.walk(self.options['content_dir'],
			topdown=False, followlinks=True):

			rootbase = os.path.relpath(root, self.options['content_dir'])
			if any(rootbase.startswith(sd) for sd in
					self.options.get('skip_dirs', [])):
				continue

			#Per-directory environment to get templates from current
			# directory or its parents
			environment = jinja2.Environment(
				loader=ParentLoader(root, stop=self.root,
					default=self.options['default_template']),
				extensions=self.options.get('jinja2_extensions', []))

			#Add any filters specified in options
			environment.filters.update(self.options.get('jinja2_filters', {}))
			environment.tests.update(  self.options.get('jinja2_tests',   {}))

			self.callback('setup_environment', environment)

			root_basename = os.path.basename(root)  #The name only of the current directory
			parent_dir    = os.path.split(root)[0]  #The full path of the parent directory

			#Get a list of directories above this one; useful for
			# directories that may move. Use in .md files with
			# jinja_markdown true as: [somefile]({{roots[0]}}/somefile.jpg]
			roots = ['']
			for d in rootbase.split(os.path.sep):
				roots.append(os.path.join(roots[-1], d))
			extravars[root]['roots'] = roots[1:]

			#If the subdirectory starts with _, read and parse all .md files
			# within it and add them as variables to the page with the
			# directory name (without the _).
			# For example: _food/bananas.md, _food/apples.md become
			# page.food.bananas and page.food.apples .
			in_subfiles = root_basename.startswith('_')
			if in_subfiles:
				logging.debug('Inside {}'.format(root))
				root_basename = root_basename[1:]  #Drop the _
				extravars[parent_dir][root_basename] = []

			#Go through each file in the current directory (root)
			for f in files:
				rname, ext = os.path.splitext(f)

				#Skip hidden and template files
				if f.startswith('.') or ext == '.jinja':
					continue

				#Figure out where it should go in output for files to be
				# copied or written
				destroot = os.path.relpath(
					os.path.join(
						os.path.join(parent_dir, root_basename) if in_subfiles else root,
						rname),          #Filename with no extension
					start=self.options['content_dir'])

				#See if we have root_subdir and redirect files in these
				# destionations to the root
				rsub = self.options['root_subdir']
				if rsub and os.path.commonpath([destroot, rsub]) == rsub:
					destroot = os.path.relpath(destroot, rsub)

				#Update the list of files we might delete from output if their
				# source file doesn't exist anymore.
				destfile = destroot + ('.html' if ext == '.md' else ext)
				if destfile in destfiles:
					destfiles.remove(destfile)

				#Before we do anything else, let's check to see if the source
				# file has been updated since the last run; if not, we don't
				# need to process it.
				#BUG: This fails when something in a _ dir has been changed;
				# it won't re-render files that depend on those. For now, move
				# this check to apply only to files that get copied.
				#For now, bypass the bug by only skipping when there are no _
				# directories present.
				full_src = os.path.join(root, f)
				full_dst = os.path.join(self.options['output_dir'], destfile)
				if os.path.exists(full_dst) and \
						not any(dn.startswith('_') for dn in dirs) and \
						os.path.getmtime(full_dst) >= os.path.getmtime(full_src):
					logging.info("Skip copying {} -> {} (unchanged since last run)".format(
						full_src, full_dst))
					continue

				#If it's a .md, we should render it
				if ext == '.md':
					here = os.getcwd()
					os.chdir(root)  #Be sure we're in root for relative paths
					try:
						meta = self.render(f, environment, extravars.get(root, {}))
					except UnboundLocalError:
						logging.error("Error rendering file {}".format(full_src))
						raise
					os.chdir(here)
					#If we're in a _ dir, put the rendered file in extravars,
					# otherwise write the rendered result to disk
					if in_subfiles:
						extravars[parent_dir][root_basename].append(meta)
					elif meta['content']:
						if destfile in destfiles:
							destfiles.remove(destfile)
						self.write(meta['content'], destfile)

						#Print a '.' for every file we process
						sys.stdout.write('.')
						sys.stdout.flush()

				#Otherwise copy it
				else:
					#BUG: see above bug; this compensates by not copying
					# unmodified files
					if os.path.exists(full_dst) and \
							os.path.getmtime(full_dst) >= os.path.getmtime(full_src):
						logging.info("Skip copying {} -> {} (unchanged since last run)".format(
							full_src, full_dst))
						continue
					try:
						os.makedirs(os.path.dirname(full_dst))
					except OSError as e:
						pass
					logging.info("Copy file {0} to {1}".format(full_src, full_dst))
					shutil.copy(full_src, full_dst)

					#Print a '.' for every file we process
					sys.stdout.write('.')
					sys.stdout.flush()

		#Now we go through any of the files that are remaining in the
		# destfiles and remove them and their parent folders from the
		# output directory
		for f in destfiles:
			rmfile = os.path.join(self.options['output_dir'], f)
			os.unlink(rmfile)
			logging.info("Remove file {}".format(rmfile))

			destroot, fn = os.path.split(f)
			rm_dir = os.path.join(self.options['output_dir'], destroot)
			if len(os.listdir(rm_dir)) == 0:
				logging.info("Remove directory {}".format(rm_dir))
				os.rmdir(rm_dir)

	def render(self, path, environment, extravars={}):
		"""Parse the passed Markdown file and use it to render the
		requested template. Return the rendered page."""
		
		fullpath = os.path.relpath(os.path.join(os.getcwd(), path), self.root)
		logging.info("render({})".format(fullpath))
		
		#Read file and get metavars
		with open(path, 'r', encoding='utf-8') as f:
			lines = f.readlines()
		meta, lines = get_meta(lines)

		#If no date metadata and date_from_filename is True, attempt to
		# parse the filename for the date
		if 'date' not in meta and self.options['date_from_filename']:
			try:
				meta['date'] = dateutil.parser.parse(os.path.splitext(path)[0])
			except ValueError: #Couldn't parse filename as date
				pass

		#Define variables to render with
		rendervars = dict(self.templ_vars) #Any global variables defined in settings
		rendervars.update(extravars)
		rendervars.update(meta)
		rendervars['filename'] = path
		rendervars['htmlfile'] = os.path.splitext(path)[0] + '.html'

		#Skip files with 'skip' set in header, or no headers at all
		if rendervars.get('skip', False) or not meta:
			logging.info("Skip {} ({})".format(path,
				'no metadata in file' if not meta else '"skip" in metadata'))
			rendervars['content'] = None
			return rendervars

		mdlines = ''.join(lines)

		#Attempt to interpret jinja embedded within Markdown file
		if self.options['jinja_markdown']:
			try:
				mdlines = environment.from_string(''.join(lines)).render(page=rendervars)
			except:
				logging.error('\nProblem rendering file {}'.format(fullpath))
				raise

		#Render markdown content to HTML
		self.markdown.reset()  #Clear variables like footnotes
		rendervars['content'] = self.markdown.convert(mdlines)

		#Get the template. If the template variable is not specified in
		# the meta variables for the file, then try to get the default
		# template from the current directory only. If that fails, return
		# the Markdown-rendered HTML. If the template variable is in the
		# meta variables, search parent directories for the template file
		# as well. If that's not found, then raise an error.
		template_file = str(rendervars.get('template', self.options['default_template']))
		logging.info('Try template "{}" for "{}"'.format(template_file, fullpath))
		if not os.path.splitext(template_file)[1]:
			template_file += '.jinja'

		try:
			template = environment.get_template(template_file)
		except jinja2.loaders.TemplateNotFound as exmsg:
			if 'template' not in rendervars:
				logging.info("Couldn't find template '{}' for '{}': {}".format(
					template_file, fullpath, exmsg))
				return rendervars
			else:
				logging.error('*** No template "{0}" found for file "{1}". ***'.format(
					template_file, fullpath))
			sys.exit(-1)

		logging.info('Template "{0}" found for file "{1}".'.format(
			template_file, fullpath))

		#If we got here, we have a valid template. Render the template
		# using the contents of rendervars at least once. If we find
		# potential variables {{}} inside the content continue to render
		# until they are all gone (this takes care of variables created in
		# 'content' during the rendering step, e.g. by including an
		# external file). The contents of rendervars is visible to the
		# template and included files in the variable 'page'.
		while True:
			try:
				rendervars['content'] = template.render(page=rendervars)
			except:
				logging.error("Error rendering file {}".format(fullpath))
				raise
			if not re.search('{{[^}]+}}', rendervars['content']):
				break
			else:
				template = environment.from_string(rendervars['content'])
		return rendervars


	def write(self, page, path):
		"""Write the page to the path, making any necessary directories."""
		if path.startswith('/'):
			path = path[1:]

		base_path = os.path.join(self.options['output_dir'], path)

		#makedirs() can fail when the path already exists
		try:
			os.makedirs(os.path.dirname(base_path))
		except OSError as e:
			pass

		with open(base_path, 'w', encoding='utf-8') as f:
			f.write(page)



def main():
	import time, argparse

	p = argparse.ArgumentParser(description="Static website generator")
	p.add_argument('-d', action='store_true', help='Turn on debugging')

	args = p.parse_args()
	if args.d:
		logging.basicConfig(level=logging.DEBUG)

	t = time.time()
	sys.stdout.write("Statipy...")
	sys.stdout.flush()
	Statipy().generate_site()
	print(" generated site in {:.2f}s".format(time.time() - t))


if __name__ == '__main__':
	main()
