#!/usr/bin/env python3
"""Chunked transcription through OpenRouter, with trustworthy timings.

    python3 scripts/transcribe_chunks.py <event>/work/audio.mp3 --out <event>/work/talk1.json \\
        --seconds 30 --start 8:36 --end 21:28 [--check <event>/work/coarse.json]

Why chunks rather than one request for the whole file: a model asked to
timestamp 46 minutes of audio drifts, and the drift is invisible: the text
reads fine while the numbers wander. Cutting video on those numbers produces
clips that open mid-sentence.

So timing comes from the chunk grid, which is exact by construction: chunk `i`
starts at `start + i * seconds` in the source, and ffmpeg cuts it there. The
model only ever sees a short window and is only asked what was said, never when.

Every chunk's text is cached in work/_cache/, keyed by the audio's content, the
span, the model and the prompt, so re-running a span or an overlapping window
never pays for the same audio twice. --no-cache forces fresh requests.

After transcribing, two checks print SUSPECT lines (see `suspects`):
  - against its own neighbours: a chunk far wordier than the median is
    invented, and one with no speech in a talk-length span is hiding some;
  - with --check, against an independent pass over the same time (normally the
    60s coarse pass): a chunk whose words mostly don't appear there, or that
    has far more of them, is the model filling a gap rather than hearing it.
Re-run any SUSPECT span at --seconds 10 and pass both files to
talk_transcript.py; the later file wins where they overlap.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import common
from common import hm

API = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"
# The plain prompt. Do not add a list of names or terms: on 2026-11-11 a prompt
# with a vocabulary list produced 1,000+ word chunks of fluent fiction.
PROMPT = (
    "Transcribe this audio verbatim. Include speaker changes and audience "
    "reactions in square brackets, e.g. [applause], [laughter]. "
    "Output only the transcript, no commentary."
)
FAILED = "[TRANSCRIPTION FAILED"


def duration(path: pathlib.Path) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip())


def file_digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def ask(blob64: str, key: str, model: str, prompt: str, retries: int = 3) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "input_audio", "input_audio": {"data": blob64, "format": "mp3"}}]}],
    }).encode()
    last = ""
    for _ in range(retries):
        req = urllib.request.Request(
            API, data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=300).read())
            return (r["choices"][0]["message"]["content"] or "").strip()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
            if e.code in (401, 402):
                # Revoked key or no credit: retrying cannot help, and the skill
                # says to stop and ask, never to fall back to another engine.
                common.die(f"OpenRouter {last}. The key needs replacing; stop here.")
        except Exception as e:  # noqa: BLE001 - transient network
            last = str(e)
    return f"{FAILED}: {last}]"


def transcribe(audio: pathlib.Path, start: float, end: float, seconds: float, *,
               model: str = MODEL, prompt: str = PROMPT, workers: int = 10,
               cache: bool = True) -> list[dict]:
    """[{i, start, end, text}] over [start, end) of `audio`, `seconds` apart."""
    work = audio.parent
    # Clamp: a window past the end yields empty chunks, and a model handed an
    # empty chunk invents plausible-sounding speech rather than nothing.
    end = min(end or float("inf"), duration(audio))
    spans, t = [], start
    while t < end - 0.05:
        spans.append((len(spans), t, min(seconds, end - t)))
        t += seconds

    tmp = work / "_chunks"
    cdir = work / "_cache"
    tmp.mkdir(exist_ok=True)
    cdir.mkdir(exist_ok=True)
    digest = file_digest(audio)
    ptag = hashlib.sha256(f"{model}\n{prompt}".encode()).hexdigest()[:12]
    key = None
    cached = 0

    def one(spec):
        nonlocal key, cached
        i, off, length = spec
        hit = cdir / f"{digest}-{off:.2f}-{length:.2f}-{ptag}.txt"
        if cache and hit.exists():
            cached += 1
            return {"i": i, "start": off, "end": off + length, "text": hit.read_text()}
        if key is None:
            key = common.openrouter_key()
        part = tmp / f"c{off:09.2f}-{length:.2f}.mp3"
        subprocess.run(["ffmpeg", "-y", "-ss", str(off), "-i", str(audio),
                        "-t", str(length), "-c", "copy", str(part)],
                       capture_output=True, check=False)
        text = ask(base64.b64encode(part.read_bytes()).decode(), key, model, prompt)
        part.unlink(missing_ok=True)
        if not text.startswith(FAILED):
            hit.write_text(text)
        print(f"  {hm(off)} done", file=sys.stderr)
        return {"i": i, "start": off, "end": off + length, "text": text}

    print(f"{len(spans)} chunks of {seconds:g}s ({hm(start)}–{hm(end)}) via {model}",
          file=sys.stderr)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = sorted(ex.map(one, spans), key=lambda r: r["i"])
    if cached:
        print(f"  {cached} of {len(spans)} chunks from cache", file=sys.stderr)
    return results


def write(results: list[dict], out: pathlib.Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1))
    with out.with_suffix(".txt").open("w") as fh:
        for r in results:
            fh.write(f"[{hm(r['start'])}] {r['text']}\n\n")


WORD = re.compile(r"[a-z0-9']+")
TAG = re.compile(r"\[[^\]]*\]")


def words(text: str) -> list[str]:
    return WORD.findall(TAG.sub(" ", text.lower()))


def suspects(results: list[dict], reference: list[dict] | None = None) -> list[str]:
    """Chunks that look invented or empty. Returns one line per suspect.

    Against the chunk's own pass: far wordier than the median rate, or no
    speech in a span where people are talking.

    Against `reference` (an independent pass over the same time, normally the
    60s coarse pass): the share of the chunk's distinct longer words that the
    reference also heard in the same stretch (plus a margin, since the grids
    don't line up), and the word count against the reference's rate there. An
    invented passage is fluent and on topic, so it passes the first check; it
    fails this one because the other pass never heard those words.
    """
    out: list[str] = []
    counts = sorted(len(words(r["text"])) for r in results if not r["text"].startswith(FAILED))
    median = counts[len(counts) // 2] if counts else 0
    span = (results[0]["end"] - results[0]["start"]) if results else 0
    rate = median / span if span else 0
    for r in results:
        if r["text"].startswith(FAILED):
            out.append(f"FAILED  {hm(r['start'])}: {r['text'][:120]}")
            continue
        n = len(words(r["text"]))
        length = r["end"] - r["start"]
        if rate and n > 3 * rate * length + 10:
            out.append(f"SUSPECT {hm(r['start'])}: {n} words, median chunk {median}: likely invented")
        elif rate > 1 and n == 0:
            out.append(f"SUSPECT {hm(r['start'])}: no speech in a talk-length span: check it")

    if reference:
        for r in results:
            if r["text"].startswith(FAILED):
                continue
            mine = words(r["text"])
            near = [c for c in reference
                    if c["end"] > r["start"] - 15 and c["start"] < r["end"] + 15]
            if len(mine) < 25 or not near:
                continue
            theirs = set()
            ref_n = 0.0
            for c in near:
                w = words(c["text"])
                theirs.update(w)
                overlap = min(c["end"], r["end"]) - max(c["start"], r["start"])
                if overlap > 0:
                    ref_n += len(w) * overlap / (c["end"] - c["start"])
            distinct = {w for w in mine if len(w) > 3}
            if len(distinct) < 8:
                continue
            shared = len(distinct & theirs) / len(distinct)
            # Calibrated on 2026-11-11: real chunks share >= 0.84 at the 5th
            # percentile; the Q&A chunk at 45:10 that had to be re-done by hand
            # shared 0.36; another talk's audio replayed into the Q&A, <= 0.45.
            if shared < 0.6:
                out.append(f"SUSPECT {hm(r['start'])}: only {shared:.0%} of its words are in the "
                           f"other pass: likely invented")
            elif len(mine) > 2.5 * ref_n + 30:
                out.append(f"SUSPECT {hm(r['start'])}: {len(mine)} words where the other pass "
                           f"heard ~{ref_n:.0f}: likely padded")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--start", default="0", help="seconds or M:SS (default: 0)")
    ap.add_argument("--end", default="0", help="seconds or M:SS (default: 0, the end)")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--check", metavar="JSON",
                    help="another pass over the same time to cross-check against "
                         "(normally work/coarse.json)")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    results = transcribe(pathlib.Path(args.audio), common.parse_ts(args.start),
                         common.parse_ts(args.end), args.seconds, model=args.model,
                         prompt=args.prompt, workers=args.workers,
                         cache=not args.no_cache)
    write(results, out)
    print(f"\nwrote {out} and {out.with_suffix('.txt')}", file=sys.stderr)
    ref = json.loads(pathlib.Path(args.check).read_text()) if args.check else None
    for line in suspects(results, ref):
        print(f"  {line}", file=sys.stderr)


if __name__ == "__main__":
    main()
