#!/usr/bin/env python3
"""Render one talk's transcript.md from transcribe_chunks.py output.

    python3 scripts/talk_transcript.py content/<date>/01-name/transcript.md \\
        --title "Talk Title" --speaker "Name, role" --offset 8:36 \\
        work/talk1.json [work/talk1_fix.json …]

`meetup_video.py talk` calls this for you; run it by hand only to re-render
after patching a span.

Several chunk files can be passed: a chunk from a later file replaces every
chunk from an earlier file that it overlaps. That is how a bad 30s chunk gets
patched with a 10s re-run of the same span.

Timestamps are rewritten relative to --offset, so they match the clip, not the
raw recording. Gemini sometimes emits its own `[ 0m5s46ms - 0m9s936ms ]`
segment markers; those are stripped, since they are relative to the chunk and
mean nothing in the clip.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re

from common import hm, parse_ts

SEG = re.compile(r"\[\s*\d+m\d+s\d+ms\s*-\s*\d+m\d+s\d+ms\s*\]")
NOISE = re.compile(r"\[(?:ambient sound|silence|clunk|speaker[^\]]*|bell ringing|"
                   r"throat clearing[^\]]*|unintelligible)\]", re.I)


def merge(layers: list[list[dict]]) -> list[dict]:
    """Later layers replace every earlier chunk they overlap."""
    merged: list[dict] = []
    for new in layers:
        for c in new:
            merged = [m for m in merged
                      if m["end"] <= c["start"] or m["start"] >= c["end"]]
        merged += new
    return sorted(merged, key=lambda c: c["start"])


def render(chunks: list[dict], offset: float, title: str, speaker: str) -> str:
    lines = [f"# {title}", "", f"{speaker}. Timestamps are from the start of the clip.",
             "Machine transcript (Gemini via OpenRouter), lightly cleaned; names and",
             "products checked against the slides.", ""]
    for c in chunks:
        text = " ".join(NOISE.sub("", SEG.sub("", c["text"])).split())
        if text:
            lines += [f"**[{hm(c['start'] - offset)}]** {text}", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("chunks", nargs="+")
    ap.add_argument("--offset", required=True, help="clip start on the event timeline")
    ap.add_argument("--title", required=True)
    ap.add_argument("--speaker", required=True)
    args = ap.parse_args()

    merged = merge([json.loads(pathlib.Path(f).read_text()) for f in args.chunks])
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(merged, parse_ts(args.offset), args.title, args.speaker))
    print(f"wrote {out} ({len(merged)} chunks)")


if __name__ == "__main__":
    main()
