# Statipy

Statipy is a very simple static site generator, written in Python 3, and
heavily inspired by the more complex [Pelican](http://getpelican.com/).

Most static site generators are aimed at blogging and make it
difficult to make a truly static, modular site without a lot of
messing around. Statipy aims to fix this problem.

## Features

Like many other static site generators, Statipy uses
[Jinja2](http://jinja.pocoo.org/) templates to render Markdown
content. However, the main features that differentiate Statipy are:

- Mirrored site layout: set up your site in `content/` as you want it,
	and Statipy will copy the same structure into your site's `output/`
	directory.
- Non-centralized templates: templates (with a `.jinja` extension)
	live in the same directories as your content, rather than in a
	central template directory.
- In-Markdown Jinja: sometimes it's handy to embed a bit of code in
	your content. Statipy will attempt to render your Markdown file with
	Jinja first. The `jinja_markdown` variable can turn off this option.
- Single file architecture: Statipy is under 400 lines long (not
  counting comments) and lives in a single file. You can provide
  an optional `site_config.py` file for additional configuration.
  See the repository for an example.

Here are several examples of sites built with Statipy:

- [fetlab.io](http://fetlab.io)
- [fetlab.io/dan](http://fetlab.io/dan)
- [fetlab.io/720-fall15](http://fetlab.io/720-fall15)
- [fetlab.io/722](http://fetlab.io/722)

You can see the source for these sites at
[github.com/fetlab/website](http://github.com/fetlab/website).

## Installation
Run `pip install git+https://github.com/anjiro/statipy.git`.

If you want output to be colorized, optionally `pip install
coloredlogs`.

## Usage
Create a directory to hold your files, then under that create a
directory named `content` and put your stuff in it. Run `statipy`.
Statipy will mirror the directory structure to a directory (with some
caveats, below) named `output` which will contain your site. You can
configure Statipy with a file called `site_config.py` (this file must
exist even if it's empty).

On installation, Statipy will also install a command `statipy-serve`
which will run a local http server. Simply change into your `output`
directory and run `statipy-serve`, optionally with a port number
(default is 8000).

### Special files
Statipy looks for some special files. First, it looks for Markdown
files with `.md` extensions to process and create content from.
Second, it looks for [Jinja2](http://jinja.pocoo.org) templates with
`.jinja` extensions. It uses the Markdown files as content to render
the templates with.

#### Local configuration files
Statipy looks for special local configuration files in each
content directory. By default it looks for a file called
`local_config.py`. If it finds such a file, it tries to load a
dict called `templ_vars` from that file. Values defined here are
accessible in templates via the `page` variable, just as those
defined in `site_config.py`. The filename of the local
configuration file can be changed in `site_config.py` via the
options dictionary.

#### Content
Statipy Markdown files have special metadata at the top. The metadata
consists of a tag followed by a colon. All metadata must be at the top
of the file with no blank lines in between. The only required piece of
metadata is a tag called `Title`. Other useful tags are `Template` to
select a template file (more below) and `Date` to allow sorting. All
tags are available to template files (in lower case).

A simple Markdown file might therefore look like this:

```.markdown
Title: My Great Page
Date: 2016-06-22
Template: awesome

This is my awesome page.
```

Each Markdown file is provided to the template under a variable named
`page`; the rendered content is `page.content` and any metadata is
likewise a sub-variable (e.g. `page.title` or `page.date`). See the
[List of page variables](#list-of-page-variables) below.

##### Special content
Sometimes it's helpful to separate content into multiple files. If you
create a directory starting with `_` (e.g., `_files/`), Statipy will
operate slightly differently. It will work as usual, rendering the
Markdown files with the given templates, but rather than writing them
to disk, it will pass them on to template files in the parent
directories as a list in `page.<name_without_underscore>`. For
example, if you have a directory called `_files/` with `hello.md` and
`goodbye.md`, then `page.files` will contain two items, consisting of
the contents of `hello.md` and `goodbye.md`. See the example for this
idea in action.

#### Templates
Statipy uses standard Jinja2 templates. It searches for template files
in the directory of the Markdown file; if it can't find a matching
template there, it will traverse the parent directories until it
finds a match or reaches the root (where `statipy` was run from).

If a template filename is specified in the metadata of a content file,
Statipy will search for that template; otherwise, it will use the
default template name (`default.jinja` or as configured in
`site_config.py`).

#### Configuration
You can create a file called `site_config.py` in your root directory
to further customize Statipy's operation. Statipy will attempt to
import two optional variables from this file: `templ_vars` and `options`.

`templ_vars` should be a dictionary of variables that you want
globally available to all of the templates.

`options`, also a dictionary, can customize several parts of Statipy.
Below are listed the dictionary keys and their meanings:

  - `content_dir`: the directory to search for content to render
		**(default: `content`)**
	- `output_dir`: the directory in which to store the output
		**(default: `output`)**
	- `root_subdir`: a subdirectory in `content_dir` whose contents will
		be copied to the root of your site instead. This is useful for
		keeping your files organized in `content_dir`.
	- `default_template`: the default filename to use for templates if
		not otherwise specified in Markdown metadata variables **(default:
		`default.jinja`)**
	- `jinja_markdown`: set to False to disable rendering of Jinja2
		content within Markdown files.
	- `jinja2_filters`: a dictionary of extra filters to add to Jinja2;
		keys are the names by which the filters will be accessible and
		values are functions. See the [Jinja2
		documentation](http://jinja.pocoo.org/docs/dev/api/# writing-filters)
		and the example `site_config.py` for more information.
	- `jinja2_extensions`: a list of strings specifying Jinja2
		extensions; see the list of available extensions [in the Jinja2
		documentation](http://jinja.pocoo.org/docs/dev/extensions/# jinja-extensions)
		and the example `site_config.py` for more information.
	- `date_from_filename`: if no `Date:` key is specified in the
		metadata part of the file, attempt to parse it from the filename.
		In this case, the filename should be of a format that can be
		parsed by
		`[dateutil.parser.parse](https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.parse)`
		(I suggest `YYYY-MM-DD.md`). If the filename can't be parsed in
		this way, no date will be included with the file's metadata.


## List of page variables

The `page` object is accessible from within each Jinja template. It
contains a number of variables that come from three potential sources:

1. Some (see the table below) are put there by Statipy.
2. Any metadata defined at the top of each Markdown file is saved as a
	 (lowercase-transformed) variable. This includes things like `title`
	 and `date` but any metadata following the format described
	 above in the [Content](#content) section will be placed here.
3. Any variables defined within the `templ_vars` dict inside
	 `site_config.py` will be available. This is useful for doing things
	 like defining a phone number that might change, or (in a
	 more-complex scenario) changing the configuration in response to an
	 envrionment variable.

The variables inserted by Statipy into each rendered page include:

Variable  | Explanation
----------|------------
`content` | The actual rendered content of the page.
`title`   | The title defined in the metadata for the Markdown file.
`filename`| The filename of the Markdown file being rendered, with path relative to the `content` directory.
`htmlfile`| The same as `filename` but with `.md` replaced with `.html`.
