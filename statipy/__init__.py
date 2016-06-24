"""
A simple static site generator. It will use .md files to generate
variables used to render Jinja2 templates.
"""
import os, sys, shutil, re, logging
import jinja2
import dateutil.parser
from   codecs      import open
from   collections import defaultdict

# logging.basicConfig(level=logging.DEBUG)

_default_vars = {
	'DEFAULT_LANG': 'en',
}


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
		else:
			path = self.search_parents(self.path, template, self.stop)
		if path is None or not os.path.exists(path):
			raise jinja2.TemplateNotFound(template)
		mtime = os.path.getmtime(path)
		with file(path) as f:
			source = f.read().decode('utf-8')
		return source, path, lambda: mtime == os.path.getmtime(path)

		
	@classmethod
	def search_parents(cls, path, filename, stop='/'):
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
		return cls.search_parents(p, filename, stop)



class Statipy(object):
	"""The class that does everything."""
	def __init__(self, **kwargs):
		"""Pass options as kwargs. Currently supported options are:
			content_dir       - the directory to search for content to render
			output_dir        - the directory in which to store the output
			default_template  - the default file to use as a template
			jinja2_filters    - a dict of user-defined filters
			jinja2_extensions - a list of user-defined extensions

			These options can also be stored in a dict called "options" in
			site_config.py.
		"""
		self.options = {
			'content_dir':      'content',
			'output_dir':       'output',
			'default_template': 'default.jinja',
		}

		self.root = os.getcwd()
		self.templ_vars = _default_vars

		#Attempt to load templ_vars and options from site_config.py
		try:
			import site_config
		except ImportError:
			sys.stderr.write('No site_config.py file found, exiting\n')
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

	
	def generate_site(self):
		self.prepare_output()
		self.load_pages()


	def prepare_output(self):
		"""Prepare the output directory by removing any content there already."""
		if os.path.isdir(self.options['output_dir']):
			for name in os.listdir(self.options['output_dir']):
				if name.startswith('.'):
					continue
				path = os.path.join(self.options['output_dir'], name)
				if os.path.isfile(path):
					os.unlink(path)
				else:
					shutil.rmtree(path)
		else:
			os.makedirs(self.options['output_dir'])


	def load_pages(self):
		"""Walk through the content directory and look for .md files which
		we can use as input to render template files."""
		#A dict of dicts to store the contents of _ directories. The first-
		# level key is the parent directory of the _ dir; the second-level
		# key is the name of the _ dir without the '_'. The value is a
		# list of rendered pages.
		extravars = defaultdict(dict)

		#Walk through the directory bottom-up so that we get any
		# subdirectories with extra variables first.
		for root, dirs, files in os.walk(self.options['content_dir'],topdown=False):
			#Per-directory environment to get templates from current
			# directory or its parents
			environment = jinja2.Environment(
				loader=ParentLoader(root, stop=self.root,
					default=self.options['default_template']),
				extensions=self.options.get('jinja2_extensions', []))

			#Add any filters specified in options
			environment.filters.update(self.options.get('jinja2_filters', {}))

			#If the subdirectory starts with _, read and parse all .md files
			# within it and add them as variables with the directory name
			# (without the _).
			basename = os.path.basename(root)
			in_subfiles = basename.startswith('_')
			if in_subfiles:
				extravars[os.path.split(root)[0]][basename[1:]] = []  #Drop the _

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
							os.path.join(os.path.split(root)[0], basename[1:]) if in_subfiles else root,
							rname),          #Full path (no extension)
						start=self.options['content_dir'])  #Remove content/

				#If it's a .md, we should render it
				if ext == '.md':
					here = os.getcwd()
					os.chdir(root)  #Be sure we're in root for relative paths
					meta = self.render(f, environment, extravars.get(root, {}))
					os.chdir(here)
					#If we're in a _ dir, put the rendered file in extravars,
					# otherwise write the rendered result to disk
					if in_subfiles:
						extravars[os.path.split(root)[0]][basename[1:]].append(meta)
					elif meta['content']:
							self.write(meta['content'], destroot + '.html')

				#Otherwise copy it
				else:
					src = os.path.join(root, f)
					dst = os.path.join(self.options['output_dir'], destroot + ext)
					try:
						os.makedirs(os.path.dirname(dst))
					except OSError as e:
						pass
					logging.info("Copy file {0} to {1}".format(src, dst))
					shutil.copy(src, dst)


	def get_meta(self, lines):
		"""Extract the metadata from a set of lines representing a file.
		Convert each metadata key to lower case.  Return a tuple
		(metadata, remaining_lines)."""
		#Load all of the initial lines with key: value; stop processing
		# key/values on the first blank line or if there's no colon in the line
		# or if it doesn't start with a letter
		meta = {}
		for i,l in enumerate(lines):
			if re.match('^\s*$|^[^A-Za-z]', l) or ':' not in l:
				break
			key, val = l.split(':', 1)
			key = key.lower().strip()
			if key == 'date':
				meta[key] = dateutil.parser.parse(val)
			else:
				meta[key] = val.strip()

		return meta, lines[i+1:]


	def render(self, path, environment, extravars={}):
		"""Parse the passed Markdown file and use it to render the
		requested template. Return the rendered page."""
		
		#Read file and get metavars
		with open(path, 'r', encoding='utf-8') as f:
			lines = f.readlines()
		meta, lines = self.get_meta(lines)

		#Define variables to render with
		rendervars = dict(self.templ_vars) #Any global variables defined in settings
		rendervars.update(extravars)
		rendervars.update(meta)
		rendervars['filename'] = path

		#Skip files with 'skip' set in header, or no headers at all
		if rendervars.get('skip', False) or not meta:
			logging.info("Skipping file {0}".format(path))
			rendervars['content'] = None
			return rendervars

		#Render markdown content to HTML
		self.markdown.reset()  #Clear variables like footnotes
		rendervars['content'] = self.markdown.convert(''.join(lines))

		#Get the template. If the template variable is not specified in
		# the meta variables for the file, then try to get the default
		# template from the current directory only. If that fails, return
		# the Markdown-rendered HTML. If the template variable is in the
		# meta variables, search parent directories for the template file
		# as well. If that's not found, then raise an error.
		template_file = rendervars.get('template', self.options['default_template'])
		if not os.path.splitext(template_file)[1]:
			template_file += '.jinja'
		try:
			template = environment.get_template(template_file)
		except jinja2.loaders.TemplateNotFound:
			if 'template' not in rendervars:
				return rendervars
			else:
				logging.error('*** No template "{0}" found for file "{1}". ***'.format(
					template_file, path))
			sys.exit(-1)

		#If we got here, we have a valid template, so render away, storing
		# the contents of rendervars in the variable 'page'
		rendervars['content'] = template.render(page=rendervars)
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

		with open(base_path, 'w') as f:
			f.write(page.encode('utf-8'))



def main():
	import time
	t = time.time()
	sys.stdout.write("Statipy...")
	sys.stdout.flush()
	Statipy().generate_site()
	print(" generated site in {:.2f}s".format(time.time() - t))


if __name__ == '__main__':
	main()
