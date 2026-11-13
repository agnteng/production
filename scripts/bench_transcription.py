#!/usr/bin/env python3
"""Transcription benchmark: adopt a model or prompt only if it scores at least
as well as the current one (org ADR: transcription through OpenRouter).

    python3 scripts/bench_transcription.py                       the default model
    python3 scripts/bench_transcription.py --models a/b,c/d      compare against it
    python3 scripts/bench_transcription.py --spec scripts/bench/2026-11-11.json

Each spec (scripts/bench/<date>.json) names spans of an event's audio with a
trusted reference: a published transcript.md, or chunk files that were checked
by hand. Every model transcribes each span in the pipeline's own 30s chunks,
and is scored on:

  WER       word error rate against the reference (lower is better)
  invented  chunks whose words mostly aren't in the reference: the failure
            that matters most, since it reads fluently
  caught    of those, how many the pipeline's own SUSPECT checks flagged
  cost      dollars for fresh requests (cached chunks are free)

A model passes when, on every span, its WER is within 1 point of the
baseline's and it invents no more chunks. Needs OPENROUTER_API_KEY; the chunk
cache means re-running a model costs nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import common
import transcribe_chunks as tc
from common import hm, parse_ts

ROOT = Path(__file__).resolve().parent.parent


def reference_words(spec: dict, event: Path, span: dict) -> tuple[list[str], list[dict]]:
    ref = span["reference"]
    if "transcript" in ref:
        text = (event / ref["transcript"]).read_text()
        lines = [ln for ln in text.splitlines() if ln.startswith("**[")]
        body = " ".join(re.sub(r"^\*\*\[[^\]]+\]\*\*\s*", "", ln) for ln in lines)
        return tc.words(body), []
    chunks = json.loads((common.media_dir(event) / ref["chunks"]).read_text())
    a, b = parse_ts(span["start"]), parse_ts(span["end"])
    chunks = [c for c in chunks if c["end"] > a and c["start"] < b]
    return tc.words(" ".join(c["text"] for c in chunks)), chunks


def wer(ref: list[str], hyp: list[str]) -> float:
    """Word-level edit distance over reference length."""
    if not ref:
        return 0.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def invented(chunks: list[dict], ref_chunks: list[dict], ref_words: list[str]) -> list[str]:
    """Chunks sharing under 60% of their distinct longer words with the
    reference around them (the same rule as transcribe_chunks.suspects)."""
    out = []
    pool = set(ref_words)
    for c in chunks:
        mine = {w for w in tc.words(c["text"]) if len(w) > 3}
        if len(mine) < 8:
            continue
        near = pool
        if ref_chunks:
            near = set(tc.words(" ".join(
                r["text"] for r in ref_chunks
                if r["end"] > c["start"] - 15 and r["start"] < c["end"] + 15)))
        if len(mine & near) / len(mine) < 0.6:
            out.append(hm(c["start"]))
    return out


def run(model: str, spec: dict, event: Path) -> list[dict]:
    audio = common.work_dir(event) / "audio.mp3"
    coarse_path = common.work_dir(event) / "coarse.json"
    coarse = json.loads(coarse_path.read_text()) if coarse_path.exists() else None
    rows = []
    for span in spec["spans"]:
        before = tc.SPENT[0]
        chunks = tc.transcribe(audio, parse_ts(span["start"]), parse_ts(span["end"]), 30,
                               model=model)
        ref_words, ref_chunks = reference_words(spec, event, span)
        hyp = tc.words(" ".join(c["text"] for c in chunks))
        bad = invented(chunks, ref_chunks, ref_words)
        flagged = {line.split()[1].rstrip(":") for line in tc.suspects(chunks, coarse)}
        rows.append({"model": model, "span": span["name"], "wer": wer(ref_words, hyp),
                     "invented": bad, "caught": [t for t in bad if t in flagged],
                     "cost": tc.SPENT[0] - before})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", default=str(ROOT / "scripts" / "bench" / "2026-11-11.json"))
    ap.add_argument("--baseline", default=tc.MODEL)
    ap.add_argument("--models", default="", help="comma-separated OpenRouter model ids")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    event = common.event_dir(spec["event"])
    models = [args.baseline] + [m for m in args.models.split(",") if m and m != args.baseline]
    rows = [r for m in models for r in run(m, spec, event)]

    base = {r["span"]: r for r in rows if r["model"] == args.baseline}
    print(f"\n{'model':38} {'span':6} {'WER':>6} {'invented':>9} {'caught':>7} {'cost':>7}")
    for r in rows:
        print(f"{r['model']:38} {r['span']:6} {r['wer']:6.1%} {len(r['invented']):>9} "
              f"{len(r['caught']):>7} {r['cost']:>7.3f}"
              + (f"   invented at {', '.join(r['invented'])}" if r["invented"] else ""))
    verdicts = []
    for m in models[1:]:
        ok = all(r["wer"] <= base[r["span"]]["wer"] + 0.01
                 and len(r["invented"]) <= len(base[r["span"]]["invented"])
                 for r in rows if r["model"] == m)
        verdicts.append(ok)
        print(f"\n{m}: {'PASS' if ok else 'FAIL'} against {args.baseline}")
    sys.exit(0 if all(verdicts) else 1)


if __name__ == "__main__":
    main()
