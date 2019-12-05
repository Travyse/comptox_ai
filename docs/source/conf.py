#!/usr/bin/env python3

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import time
from pathlib import Path
import importlib.resources as pkg_resources

import comptox_ai  # Just so we can find the version string

# -- Project information -----------------------------------------------------

project = 'ComptoxAI'
copyright = time.strftime('%Y, Joseph D. Romano')
author = 'Joseph D. Romano, PhD'

# The full version, including alpha/beta/rc tags
#comptox_ai_root = Path(os.path.abspath(__file__)).parent.parent.parent
#comptox_ai_src = os.path.join(comptox_ai_root, 'comptox_ai')
#if comptox_ai_root not in sys.path:
#    sys.path.insert(0, comptox_ai_root)
#version_file = open(os.path.join(comptox_ai_root, 'VERSION'), 'r')
#str_version = version_file.read().strip()
str_version = comptox_ai.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'numpydoc',
    'sphinx.ext.autosummary',
    'IPython.sphinxext.ipython_console_highlighting',
    'IPython.sphinxext.ipython_directive',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# Suffix for source filenames
source_suffix = '.rst'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

rst_prolog = """
.. |version| replace:: VERSION
""".replace('VERSION', str_version)


def skip(app, what, name, obj, would_skip, options):
    if name == "__init__":
        return False
    return would_skip


def setup(app):
    app.connect("autodoc-skip-member", skip)

# -- Options for HTML output -------------------------------------------------

themedir = os.path.join(os.pardir, 'scipy-sphinx-theme', '_theme')
if not os.path.isdir(themedir):
    raise RuntimeError("Get the scipy-sphinx-theme first, "
                       "via git submodule init && git submodule update")

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'scipy'
html_theme_path = [themedir]

html_theme_options = {
    "rootlinks": [
        ("https://comptox.ai/", "comptox.ai"),
        #("https://comptox.ai/docs", "API Docs home")
    ]
}

html_title = "%s v%s Manual" % (project, str_version)

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
#html_static_path = ['_static']

# Autosummary stuff:

import glob
autosummary_generate = True
