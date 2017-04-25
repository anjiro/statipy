# Example Statipy site

This is a simple Statipy example site. Its structure looks like the
following:

```
├── site_config.py
├── site_config_extra.py
├── content
│   ├── default.jinja
│   ├── index.md
│   └── mypage.md
│   ├── _lists
│   │   ├── aardvark.md
│   │   ├── bear.md
│   │   ├── cat.md
│   │   ├── elephant.md
│   │   ├── monkey.md
│   │   └── wolf.md
```

## `site_config.py`

The `site_config.py` file is empty, because the example doesn't do
anything particularly complex. See `site_config_extra.py` at the
bottom of this file for an explanation of the more complex things that
can be done.

## `content`

The `content` directory holds the content for the site.

### `default.jinja`

`default.jinja` is the name of the template file that Statipy will
search for if no other template files can be found. In this case, it's
the only template file provided, so it will be the one that's used.

`default.jinja` illustrates how to use a directory beginning with an
underscore (`_`) to process a number of files at once. It contains the
code:

```
<ul>
	{% for l in page.lists %}
		<li><strong>{{ l.title }}:</strong> {{ l.count }} characters</li>
	{% endfor %}
</ul>
```

The contents of the `_lists` directory are each rendered as Markdown
and stored in the `page.lists` variable, which the template then loops
over. At each iteration, it creates a new `<li>` and lists the two
variables present in each file within `_lists`: `title` and `count`.

###  `index.md`

This will use `default.jinja` to render itself into `index.html`.

###  `mypage.md`

This is another page that will use `default.jinja` to render itself.
It includes a built-in loop to generate some data as a demo.

###  `_lists`

This directory contains a number of items which will be rendered
within `default.jinja` as described above. For exmaple, here are the
contents of `elephant.md`:

```
Title: elephant
Count: 9
```

## `site_config_extra.py`

To illustrate the things that can be done in `site_config.py`, the
file `site_config_extra.py` has a number of Jinja2 filters. As a
consequence, it loads a number of modules which are not part of the
standard install. It is left as an exercise to the reader to install
these modules. The Jinja2 filters in `site_config_extra.py` include:

- `includefile`: Include a file as-is inside another one
- `includemd`: Render and include a Markdown file
- `md`: Render an inline block as Markdown
- `sortby`: Sort a list in a particular order, according to some
	attribute; used in the [FETLab](http://fetlab.rit.edu) site to sort
	people by PhD, Masters, or Undergrad status.
- `ago`: Return the number of seconds ago a date was; useful for
	sorting

To use `site_config_extra.py` it has to be renamed to
`site_config.py`.
