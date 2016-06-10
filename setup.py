#!/usr/bin/env python
from setuptools import setup

requires = ['jinja2 > 2.7', 'python-dateutil']
entry_points = {
	'console_scripts': [
		'statipy = statipy:main',
		'statipy-serve = SimpleHTTPServer:test',
	]
}

setup(
	name = 'statipy',
	version = '0.1',
	url = 'http://github.com/anjiro/statipy',
	author = 'Daniel Ashbrook',
	description = 'A very simple static site generator, not for blogging.',
	packages = ['statipy'],
	license = 'MIT',
	entry_points = entry_points,
)
