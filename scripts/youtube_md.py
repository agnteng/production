#!/usr/bin/env python3
"""Write each talk's youtube.md from its description.md, so the two never drift.

    python3 scripts/youtube_md.py content/<date>            # every NN-*/ with a talk.json
    python3 scripts/youtube_md.py content/<date> --check    # exit 1 if any is stale

description.md is the source: it is what gets written and reviewed. youtube.md
is the same content in the format the channel already uses (YouTube renders no
markdown, so links go one per line as `Label: url`). The only things YouTube
needs that description.md doesn't hold are in NN-*/talk.json:

    {"speaker": "David Mihal", "tags": ["agentic engineering", "adr", …]}

`youtube_upload.py` regenerates youtube.md the same way before it reads it.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from common import die, event_dir

LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def plain(text: str) -> str:
    """Markdown inline → plain text: links keep their label, emphasis goes."""
    text = LINK.sub(r"\1", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])[*_](?!\s)(.+?)(?<!\s)[*_](?![\w*])", r"\1", text)
    return text.replace("\\", "").strip()


def sentence(text: str) -> str:
    """The channel's bullets end in a full stop."""
    return text if re.search(r"[.!?…]['\"”’)]*$", text) else text + "."


def render(description: str, speaker: str, tags: list[str]) -> str:
    """description.md (the house Substack format) → youtube.md."""
    lines = [ln.rstrip() for ln in description.strip().splitlines()]
    head = lines[0]
    m = re.match(r"#+\s*\[(.+)\]\([^)]*\)\s*$", head) or re.match(r"#+\s*(.+)$", head)
    if not m:
        die("description.md must open with '### [Talk Title](url)'")
    title = plain(m.group(1))

    summary, bullets, socials, mentioned = [], [], [], []
    section = "summary"
    for ln in lines[1:]:
        s = ln.strip()
        if not s:
            continue
        if plain(s).lower() == "main takeaways":
            section = "bullets"
        elif re.match(r"^[*\-+]\s+", s):
            bullets.append(sentence(plain(re.sub(r"^[*\-+]\s+", "", s))))
        elif s.startswith("Mentioned:"):
            mentioned = LINK.findall(s)
            section = "done"
        elif LINK.search(s) and re.match(r"^[^\[]*'s\s", s):
            socials = LINK.findall(s)
            section = "done"
        elif section == "summary":
            summary.append(plain(s))
        else:
            die(f"description.md: don't know where this line goes: {s[:80]!r}")
    if not summary or not bullets:
        die("description.md needs a summary sentence and Main Takeaways bullets")

    out = [f"Title: {title} - {speaker}", "", " ".join(summary), "", "Main Takeaways", ""]
    out += [f"- {b}" for b in bullets]
    if socials:
        out += ["", speaker, *(f"{label}: {url}" for label, url in socials)]
    if mentioned:
        out += ["", "Mentioned in the talk",
                *(f"{plain(label)}: {url}" for label, url in mentioned)]
    if tags:
        out += ["", "Tags: " + ", ".join(tags)]
    return "\n".join(out) + "\n"


def for_talk(folder: pathlib.Path) -> str | None:
    """The youtube.md this talk folder should have, or None if it has no
    talk.json (a Q&A folder, or a talk not yet written up)."""
    meta = folder / "talk.json"
    desc = folder / "description.md"
    if not meta.exists():
        return None
    if not desc.exists():
        die(f"{folder.name}: talk.json but no description.md")
    m = json.loads(meta.read_text())
    if not m.get("speaker"):
        die(f"{meta}: needs \"speaker\"")
    return render(desc.read_text(), m["speaker"], m.get("tags", []))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event")
    ap.add_argument("--check", action="store_true",
                    help="write nothing; exit 1 if any youtube.md is out of date")
    args = ap.parse_args()

    d = event_dir(args.event)
    stale = 0
    for folder in sorted(p for p in d.iterdir() if p.is_dir() and p.name[:2].isdigit()):
        want = for_talk(folder)
        if want is None:
            continue
        md = folder / "youtube.md"
        have = md.read_text() if md.exists() else ""
        if have == want:
            print(f"  {folder.name}: up to date")
        elif args.check:
            stale += 1
            print(f"  {folder.name}: STALE", file=sys.stderr)
        else:
            md.write_text(want)
            print(f"  {folder.name}: wrote youtube.md")
    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
