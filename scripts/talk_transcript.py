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
raw recording. Every paragraph goes through tidy(): fillers (um, uh), sound
annotations ([laughter], [applause]) and stutters ("the the") are removed, and
nothing else is touched. `--tidy FILE …` applies it to transcripts already
written. Gemini sometimes emits its own `[ 0m5s46ms - 0m9s936ms ]`
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


# Words people say while thinking. "ah" stays: it can mean something ("Ah, I see").
FILLER = r"(?:u+h+m*|u+m+|e+r+m+|h+m+|m{2,})"
# What the model writes about the sound rather than the speech.
SOUND = re.compile(r"\s*\[(?=[^\]]*(?:laugh|applau|clap|cheer|noise|sound|pause|sigh|cough|throat|"
                   r"inaudible|sing|scream|silence|feedback|music|speech|typing))[^\]]{1,40}\]", re.I)
# Doubled on purpose often enough to keep ("that that", "very very", "no no").
KEEP_DOUBLE = {"that", "had", "very", "really", "no", "yes", "yeah", "bye", "so", "ha", "la", "blah", "go"}
STUTTER = re.compile(r"\b(\w+)(?:\s+\1\b)+", re.I)
# Across a comma only small words stutter ("I, I think"); others are lists ("text to speech, speech to text").
STUTTER_COMMA = re.compile(r"\b(i|a|the|and|but|so|it|it's|we|you|they|he|she|to|of|in|on|is|was|my|our|your|this|if|or)(?:,\s+\1\b)+", re.I)


def tidy(text: str) -> str:
    """One paragraph without fillers, sound annotations and stutters; wording otherwise untouched."""
    text = SOUND.sub("", text)
    # A filler opening a sentence: drop it and capitalise what follows.
    text = re.sub(rf"(^|[.?!]\s+)(?:{FILLER}[,.]?\s+)+([a-z])", lambda m: m[1] + m[2].upper(), text, flags=re.I)
    text = re.sub(rf"\s*\b{FILLER}\b[,.]?(?=\s|$)", "", text, flags=re.I)
    text = re.sub(rf"^\s*\b{FILLER}\b[,.]?\s*", "", text, flags=re.I)
    text = STUTTER.sub(lambda m: m[0] if m[1].lower() in KEEP_DOUBLE else m[1], text)
    text = STUTTER_COMMA.sub(lambda m: m[1], text)
    text = re.sub(r"\s+([,.?!;:])", r"\1", text)
    text = re.sub(r"([,.?!;:])(?:\s*,)+", r"\1", text)
    return re.sub(r"^(?:[,;:]|\.(?!\.))\s*", "", " ".join(text.split()))


def merge(layers: list[list[dict]]) -> list[dict]:
    """Later layers replace every earlier chunk they overlap."""
    merged: list[dict] = []
    for new in layers:
        for c in new:
            merged = [m for m in merged
                      if m["end"] <= c["start"] or m["start"] >= c["end"]]
        merged += new
    return sorted(merged, key=lambda c: c["start"])


def render(chunks: list[dict], offset: float, title: str, speaker: str,
           checked: bool = True) -> str:
    """checked=False for talks imported from YouTube, whose slides nobody read."""
    lines = [f"# {title}", "", f"{speaker}. Timestamps are from the start of the clip.",
             "Machine transcript (Gemini via OpenRouter), lightly cleaned; names and",
             f"products {'checked' if checked else 'not yet checked'} against the slides.", ""]
    for c in chunks:
        text = tidy(" ".join(NOISE.sub("", SEG.sub("", c["text"])).split()))
        if text:
            lines += [f"**[{hm(c['start'] - offset)}]** {text}", ""]
    return "\n".join(lines)


def tidy_file(path: pathlib.Path) -> bool:
    """Tidy every paragraph of a transcript.md already written; True if it changed."""
    old = path.read_text()
    new = re.sub(r"^(\*\*\[[\d:]+\]\*\*) (.*)$", lambda m: f"{m[1]} {tidy(m[2])}", old, flags=re.M)
    if new != old:
        path.write_text(new)
    return new != old


def main() -> None:
    import sys
    if sys.argv[1:2] == ["--tidy"]:
        changed = [p for p in map(pathlib.Path, sys.argv[2:]) if tidy_file(p)]
        print(f"tidied {len(changed)} of {len(sys.argv) - 2} transcripts")
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("chunks", nargs="+")
    ap.add_argument("--offset", required=True, help="clip start on the event timeline")
    ap.add_argument("--title", required=True)
    ap.add_argument("--speaker", required=True)
    ap.add_argument("--unchecked", action="store_true",
                    help="names not checked against slides (talks imported from YouTube)")
    args = ap.parse_args()

    merged = merge([json.loads(pathlib.Path(f).read_text()) for f in args.chunks])
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(merged, parse_ts(args.offset), args.title, args.speaker,
                              checked=not args.unchecked))
    print(f"wrote {out} ({len(merged)} chunks)")


if __name__ == "__main__":
    main()
