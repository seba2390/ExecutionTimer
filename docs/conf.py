"""Sphinx configuration for the executiontimer documentation."""

from datetime import date

import execution_timer

project = "executiontimer"
author = "Sebastian Yde Madsen"
copyright = f"{date.today().year}, {author}"
release = execution_timer.__version__
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
]

exclude_patterns = ["_build"]
nitpicky = True

# Markdown pages
myst_enable_extensions = ["colon_fence", "deflist", "fieldlist"]
myst_heading_anchors = 3

# API reference
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"
autodoc_preserve_defaults = True
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_rtype = False
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# Type variables in decorator signatures have no page of their own.
nitpick_ignore_regex = [("py:class", r"(~|execution_timer\._timer\.)?[PRT]")]

# HTML output
# The GitHub mark from Primer Octicons (mark-github-16).
_GITHUB_MARK = (
    '<svg fill="currentColor" viewBox="0 0 16 16"><path d="'
    "M6.766 11.328c-2.063-.25-3.516-1.734-3.516-3.656 0-.781.281-1.625.75-2.188-.203-.515-.172-"
    "1.609.063-2.062.625-.078 1.468.25 1.968.703.594-.187 1.219-.281 1.985-.281.765 0 1.39.094 "
    "1.953.265.484-.437 1.344-.765 1.969-.687.218.422.25 1.515.046 2.047.5.593.766 1.39.766 2.2"
    "03 0 1.922-1.453 3.375-3.547 3.64.531.344.89 1.094.89 1.954v1.625c0 .468.391.734.86.547C13"
    ".781 14.359 16 11.53 16 8.03 16 3.61 12.406 0 7.984 0 3.563 0 0 3.61 0 8.031a7.88 7.88 0 0"
    " 0 5.172 7.422c.422.156.828-.125.828-.547v-1.25c-.219.094-.5.156-.75.156-1.031 0-1.64-.562"
    "-2.078-1.609-.172-.422-.36-.672-.719-.719-.187-.015-.25-.093-.25-.187 0-.188.313-.328.625-"
    ".328.453 0 .844.281 1.25.86.313.452.64.655 1.031.655s.641-.14 1-.5c.266-.265.47-.5.657-.65"
    "6"
    '"/></svg>'
)

html_theme = "furo"
html_title = "executiontimer"
html_static_path = ["_static"]
html_favicon = "_static/icon-light.svg"
html_copy_source = False
html_show_sourcelink = False
html_theme_options = {
    "light_logo": "icon-light.svg",
    "dark_logo": "icon-dark.svg",
    "source_repository": "https://github.com/seba2390/ExecutionTimer/",
    "source_branch": "main",
    "source_directory": "docs/",
    "light_css_variables": {
        "color-brand-primary": "#4F46E5",
        "color-brand-content": "#4F46E5",
        "color-brand-visited": "#4F46E5",
    },
    "dark_css_variables": {
        "color-brand-primary": "#818CF8",
        "color-brand-content": "#818CF8",
        "color-brand-visited": "#818CF8",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/seba2390/ExecutionTimer",
            "html": _GITHUB_MARK,
            "class": "",
        },
    ],
}
copybutton_exclude = ".linenos, .gp, .go"
