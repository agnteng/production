"""The channel's end card (endcard.html), spliced into a Short's page: every Short ends on it."""
from __future__ import annotations

import pathlib

FRAGMENT = pathlib.Path(__file__).resolve().parent / "endcard.html"


def splice(page: str) -> str:
    """`page` with /*ENDCARD:CSS*/, <!--ENDCARD:HTML--> and /*ENDCARD:JS*/ replaced by the end card's parts."""
    text = FRAGMENT.read_text()
    css = text[text.index("<!--css-->") + 10:text.index("<!--html-->")]
    html = text[text.index("<!--html-->") + 11:text.index("<!--js-->")]
    js = text[text.index("<!--js-->") + 9:]
    for mark in ("/*ENDCARD:CSS*/", "<!--ENDCARD:HTML-->", "/*ENDCARD:JS*/"):
        if mark not in page:
            raise ValueError(f"page has no {mark} marker")
    return page.replace("/*ENDCARD:CSS*/", css).replace("<!--ENDCARD:HTML-->", html).replace("/*ENDCARD:JS*/", js)


def sounds(t: float, press: float) -> dict[str, list[float]]:
    """The end card's sounds: in on a big whoosh, and a ding when the like button is pressed."""
    return {"whoosh_big": [t], "ding": [t + press]}
