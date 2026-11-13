#!/usr/bin/env python3
"""Fitness checks: what a healthy repository looks like (docs/adr/0002).

    python3 scripts/fitness.py              repo checks (fast, no network)

Every check exists because its failure happened once. Exit 1 if any fails.

The internal-names check reads its denylist from PUBLIC_DENYLIST (the pattern
text itself, which CI supplies as a secret) or from the workspace this
checkout sits in. The patterns never live in this public repository.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FAILURES: list[str] = []


def fail(check: str, msg: str) -> None:
    FAILURES.append(f"{check}: {msg}")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                          text=True, check=True).stdout


def tracked() -> list[str]:
    return [p for p in git("ls-files", "-z").split("\0") if p]


# ── internal names (org ADR: public repositories name no infrastructure) ──

GENERIC = [
    r"op://",                                        # secret-store references
    r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",            # private IPv4
    r"\b192\.168\.\d{1,3}\.\d{1,3}\b",
    r"\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b",
    r"\b100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b",  # CGNAT / tailnets
    r"/Users/[a-z0-9_-]+/",                          # local home paths
    r"/home/[a-z0-9_-]+/",
]
SKIP_FILES = {"scripts/fitness.py"}


def denylist() -> list[str]:
    text = os.environ.get("PUBLIC_DENYLIST", "")
    if not text:
        f = ROOT.parent.parent / "private" / "denylist.txt"
        if ROOT.parent.name == "repos" and f.exists():
            text = f.read_text()
    pats = [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    if not pats:
        print("  note: no private denylist (PUBLIC_DENYLIST or the workspace); "
              "checking generic patterns only", file=sys.stderr)
    return pats


def check_internal_names() -> None:
    rx = re.compile("|".join(f"(?:{p})" for p in GENERIC + denylist()), re.I)

    def scan(where: str, text: str) -> None:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            # Report where, never the matched text: CI logs are public.
            fail("internal-names", f"{where}:{line} matches a denylisted pattern")
            return

    for path in tracked():
        if path in SKIP_FILES:
            continue
        p = ROOT / path
        try:
            scan(path, p.read_text())
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue
    for sha in git("rev-list", "HEAD").split():
        scan(f"commit {sha[:7]} message", git("log", "-1", "--format=%B", sha))
    extra = os.environ.get("FITNESS_EXTRA_TEXT", "")
    if extra:
        scan("pull request title/body", extra)


# ── media and scratch stay out of git (org ADR: media never enters git) ──

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".wav", ".m4a", ".mp3", ".mxf"}
SCRATCH_DIRS = {"raw", "work", "upload", "clips"}
MAX_BYTES = 5_000_000


def check_media() -> None:
    for path in tracked():
        p = Path(path)
        if p.suffix.lower() in MEDIA_EXT:
            fail("media", f"{path} is a media file")
        elif path.startswith("content/") and SCRATCH_DIRS & set(p.parts):
            fail("media", f"{path} is inside a media/scratch folder")
        elif (ROOT / p).is_file() and (ROOT / p).stat().st_size > MAX_BYTES:
            fail("media", f"{path} is over {MAX_BYTES // 1_000_000} MB")


# ── generated text in sync (docs/adr/0001) ──

def check_youtube_md() -> None:
    import youtube_md
    for event in sorted(p for p in (ROOT / "content").iterdir() if p.is_dir()):
        for folder in sorted(p for p in event.iterdir() if p.is_dir() and p.name[:2].isdigit()):
            want = youtube_md.for_talk(folder)
            if want is None:
                continue
            md = folder / "youtube.md"
            if not md.exists() or md.read_text() != want:
                fail("youtube-md", f"{md.relative_to(ROOT)} is stale: run scripts/youtube_md.py")


def main() -> None:
    checks = [("internal-names", check_internal_names), ("media", check_media),
              ("youtube-md", check_youtube_md)]
    for name, fn in checks:
        before = len(FAILURES)
        fn()
        print(f"  {'ok  ' if len(FAILURES) == before else 'FAIL'} {name}")
    for f in FAILURES:
        print(f"  ✗ {f}", file=sys.stderr)
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
