"""
A simple static site generator. It will use .md files to generate
variables used to render Jinja2 templates.
"""
import os, sys, shutil, re, logging
import jinja2
import dateutil.parser
from   codecs import open

# logging.basicConfig(level=logging.DEBUG)

_default_vars = {
	'DEFAULT_LANG': 'en',
}


class ParentLoader(jinja2.BaseLoader):
	"""A Jinja2 template loader that searches the path and all parent
	directories for the necessary template."""
	def __init__(self, path, stop='/'):
		"""The path and its parents will be searched for the template,
		stopping when the value of stop is reached."""
		self.path = path
		self.stop = stop


	def get_source(self, environment, template):
		path = self.search_parents(self.path, template, self.stop)
		if path is None:
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
			logging.info('No site_config.py file found, skipping local config')
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
		extravars = {}
		for root, dirs, files in os.walk(self.options['content_dir'], topdown=False):
			rootbn = os.path.basename(root)

			#Per-directory environment to get templates from current dir
			environment = jinja2.Environment(
				loader=ParentLoader(root),
				extensions=self.options.get('jinja2_extensions', []))
			environment.filters.update(self.options.get('jinja2_filters', {}))


			#If the subdirectory starts with _, read and parse all .md files
			# within it and add them as variables with the directory name
			# (without the _).
			if rootbn.startswith('_'):
				bn = rootbn[1:] #Drop the _
				extravars[bn] = []
				for f in files:
					rname, ext = os.path.splitext(f)
					if f.startswith('.') or ext != '.md':
						continue
					with open(os.path.join(root, f), 'r', encoding='utf-8') as fl:
						lines = fl.readlines()
						meta, lines = self.get_meta(lines)
					self.markdown.reset()  #Clear variables like footnotes
					meta['content'] = self.markdown.convert(''.join(lines))
					meta['filename'] = f
					extravars[bn].append(meta)
				continue

			#Go through each file in the current directory (root)
			for f in files:
				rname, ext = os.path.splitext(f)

				#Skip hidden and template files
				if f.startswith('.') or ext == '.jinja':
					continue

				#Figure out where it should go in output
				destroot = os.path.join(
					root.split(os.path.sep, 1)[1] if os.path.sep in root else root,
					rname)

				#If it's a .md, we should render it
				if ext == '.md':
					here = os.getcwd()
					os.chdir(root)
					p = self.render(f, environment, extravars)
					os.chdir(here)
					if p:
						self.write(p, destroot + '.html')

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

			#If we were in a top-level directory, then clear out extravars
			# for the next time; otherwise, we were in a subdir and we should
			# keep them.
			if os.path.normpath(os.path.join(root, os.path.pardir)) == self.options['content_dir']:
				extravars = {}


	def get_meta(self, lines):
		"""Extract the metadata from a set of lines representing a file.
		Return a tuple (metadata, remaining_lines)."""
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

		return meta, lines[i:]


	def render(self, path, environment, extravars={}):
		"""Parse the passed Markdown file and use it to render the
		requested template. Return the rendered page."""
		
		rendervars = dict(self.templ_vars) #Any global variables defined in settings
		rendervars.update(extravars)
		#Strip off content dir
		with open(path, 'r', encoding='utf-8') as f:
			lines = f.readlines()

		meta, lines = self.get_meta(lines)
		rendervars.update(meta)


		#Skip files with 'skip' set in header, or no headers at all
		if rendervars.get('skip', False) or not meta:
			logging.info("Skipping file {0}".format(path))
			return False

		#Set up variables for rendering, put the rest of the file into content
		self.markdown.reset()  #Clear variables like footnotes
		rendervars['content'] = self.markdown.convert(''.join(lines))

		#Which template to render?
		if 'template' not in rendervars:
			rendervars['template'] = self.options['default_template']
		if not os.path.splitext(rendervars['template'])[1]:
			rendervars['template'] += '.jinja'

		#Get the template
		try:
			template = environment.get_template(rendervars['template'])
		except jinja2.loaders.TemplateNotFound:
			logging.error('*** No template "{0}" found for file "{1}". ***'.format(
				rendervars['template'], path))
			sys.exit()

		return template.render(page=rendervars, **rendervars)


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
