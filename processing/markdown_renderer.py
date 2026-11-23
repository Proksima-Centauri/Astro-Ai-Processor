"""Safe Markdown-to-HTML rendering for Altair chat messages."""

from __future__ import annotations

import re

import bleach
import markdown
from pygments.formatters import HtmlFormatter


_ALLOWED_TAGS = frozenset({
    "a", "blockquote", "br", "code", "del", "div", "em", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "li", "ol", "p", "pre", "span", "strong",
    "table", "tbody", "td", "th", "thead", "tr", "ul",
})
_ALLOWED_PROTOCOLS = frozenset({"http", "https"})
_SAFE_CLASS_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CODE_HIGHLIGHT_CSS = HtmlFormatter(style="monokai").get_style_defs(".codehilite")


def _allow_attribute(tag: str, name: str, value: str) -> bool:
    if tag == "a" and name in {"href", "title"}:
        return True
    if name == "class":
        return all(_SAFE_CLASS_TOKEN.fullmatch(token) for token in value.split())
    return False


def render_markdown_html(source: str) -> str:
    """Render Markdown and sanitize the resulting fragment for a Qt document.

    Raw HTML is accepted by Python-Markdown but is filtered here through an
    allow-list. Only web links survive; scripts, event handlers, styles,
    embedded resources, and non-web URL schemes are discarded.
    """
    text = str(source or "")
    parser = markdown.Markdown(
        extensions=("fenced_code", "tables", "codehilite", "nl2br", "sane_lists"),
        extension_configs={
            "codehilite": {
                "css_class": "codehilite",
                "guess_lang": False,
                "use_pygments": True,
            }
        },
        output_format="html",
    )
    rendered = parser.convert(text)
    return bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_allow_attribute,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
