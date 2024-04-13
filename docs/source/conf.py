import os
import sys

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('../..'))

project = 'TaskBridge'
copyright = '2024, Keith Vassallo'
author = 'Keith Vassallo'
release = '0.1'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx_autodoc_typehints',
    'sphinx.ext.autosummary',
    'sphinx_rtd_dark_mode'
]
autodoc_mock_imports = ["six.moves", "icalendar", "caldav", "caldav.Principal", "Principal", "PyQt6"]

autodoc_default_options = {
    'autosummary': True,
    'private-members': True
}
autosummary_private_members = True

templates_path = ['_templates']
exclude_patterns = []

html_theme = 'sphinx_rtd_theme'
default_dark_mode = False
html_static_path = ['_static']


def skip(app, what, name, obj, would_skip, options):
    if name == "__init__":
        return False
    if name in ["__annotations__", "__dict__", "__doc__", "__module__", "__weakref__"]:
        return True
    return would_skip


def setup(app):
    app.connect("autodoc-skip-member", skip)
