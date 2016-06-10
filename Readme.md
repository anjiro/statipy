#Statipy

Statipy is a very simple static site generator, written in Python, and
heavily inspired by the more complex
[Pelican](http://getpelican.com/).

Most static site generators are aimed at blogging and make it
difficult to make a truly static, modular site without a lot of
messing around. Statipy aims to fix this problem.

##Features

Like many other static site generators, Statipy uses
[Jinja2](http://jinja.pocoo.org/) templates. However, the main
features that differentiate Statipy are:

- Mirrored site layout: set up your site in `content/` as you want it,
	and Statipy will copy the same structure into your site's `output/`
	directory.
- Non-centralized templates: templates (with a `.jinja` extension)
	live in the same directories as your content, rather than in a
	central template directory.
- Single file architecture: Statipy is under 300 lines long and lives
	in a single file. You can provide an optional `site_config.py` file
	for additional configuration. See the repository for an example.
