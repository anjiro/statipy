from markdown import Markdown
from datetime import datetime
import mkdcomments
comments = mkdcomments.CommentsExtension()
from fontawesome_markdown import FontAwesomeExtension
import re, os, sys, operator

#Custom Markdown Jinja2 filters
markdown = Markdown(extensions=['markdown.extensions.extra',
	'markdown.extensions.codehilite', 'markdown.extensions.smarty'])

def includefile(filename, *args):
	return open(filename).read()


def includemd(filename, *args):
	"""Use with {{ myfile.md | includemd }}"""
	m = markdown.convert(open(filename).read())
	open('/tmp/mdout', 'w').write(m)
	return m


def md(content, *args):
	"""Use with
	{% filter md %}
		#Header
	{% endfilter %}
	(Note that whitespace will be removed from the beginning of lines
	according to the first line, so indentation can be preserved.)
	"""
	ws = re.match(r'\s*', content.splitlines()[0]).group(0)
	c = re.compile('^%s' % ws, re.MULTILINE).sub('', content)
	return markdown.convert(c)


def sortby(items, attribute, sortlist):
	"""Use with {{ list | sortby(attribute, sortlist) }}
	where attribute is the attribute of each item in the list to sort by
	and sortlist is a list of possible values of that attribute sort, in
	the order for them to be sorted by."""
	ag = lambda a: a.__getattribute__(attribute).lower()
	sl = [s.lower() for s in sortlist]
	return sorted(items, key=lambda x:(sl.index(ag(x)) if ag(x) in sl
			else len(sl)+1, x.title))


def ago(dto, *args):
	"""Return the number of seconds ago the passed datetime object
	was."""
	return (datetime.now() - dto).total_seconds()


JINJA_EXTENSIONS = ['jinja2.ext.do']

JINJA_FILTERS = {
	'includefile': includefile,
	'includemd':   includemd,
	'md':          md,
	'sortby':      sortby,
	'ago':         ago,
	'type': type,
}


options = {
	'jinja2_filters':    JINJA_FILTERS,
	'jinja2_extensions': JINJA_EXTENSIONS,
}
