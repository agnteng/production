#!/usr/bin/env python3
"""Turn one event recording into per-talk clips.

One big camera file per event, an optional intro nobody wants cut, then three
~10 minute talks. This script owns the mechanical half:

    probe       what is in raw/, how long, what codecs
    audio       extract work/audio.mp3 (the input to transcribe_chunks.py)
    cut         cut the talks out, one folder per talk
    talk        cut one talk, transcribe it in 30s chunks, cross-check them
                against the coarse pass and write transcript.md
    splice      build one clip from several spans
    frames      sample frames over a span: a contact sheet to read slides
                from, and every QR code on screen decoded

Media lives outside the repository, in <media>/<date>/ (see common.MEDIA_ROOT):
raw/ for the camera files, work/ for scratch, and one .mp4 per talk folder.
content/<date>/ keeps only what gets published.

raw/ may hold several files. Cameras split a long recording at a file-size
limit (Sony XAVC at ~4 GB of FAT32 or ~50 min), and the split is seamless, so
the files are treated as ONE timeline in filename order: every timecode in this
script, and in the transcripts, is on that joined timeline.

Boundary detection is deliberately NOT decided here. Silence alone is a bad
signal in a live room. Transcription and boundaries live in
transcribe_chunks.py and detect_talks.py; `talk` strings cut, transcription
and transcript together once the boundaries are known.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import common
from common import die, event_dir, hm, hms, parse_ts

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".m4v", ".avi"}


def need(binary: str) -> None:
    if not shutil.which(binary):
        die(f"{binary} not found on PATH")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def find_sources(d: Path) -> list[Path]:
    """Every video in raw/, in filename order — which for a camera that split
    one recording (C0084, C0085, …) is recording order."""
    raw = common.media_dir(d) / "raw"
    if not raw.is_dir():
        die(f"no raw/ directory in {d}")
    vids = sorted(p for p in raw.iterdir()
                  if p.suffix.lower() in VIDEO_EXTS and not p.name.startswith("."))
    if not vids:
        die(f"no video in {raw} (looked for {', '.join(sorted(VIDEO_EXTS))})")
    return vids


def source_input(d: Path) -> list[str]:
    """ffmpeg input args for the event's joined timeline.

    One file: `-i file`. Several: the concat demuxer over a list in work/, so
    `-ss` and `-t` address the joined timeline and a talk that straddles the
    file split cuts like any other.
    """
    vids = find_sources(d)
    if len(vids) == 1:
        return ["-i", str(vids[0])]
    listing = common.work_dir(d) / "sources.txt"
    listing.write_text("".join(f"file '{v.resolve()}'\n" for v in vids))
    return ["-f", "concat", "-safe", "0", "-i", str(listing)]


def total_duration(d: Path) -> float:
    return sum(probe(v).duration for v in find_sources(d))


@dataclass
class Probe:
    duration: float
    vcodec: str
    acodec: str
    width: int
    height: int
    fps: str


def probe(path: Path) -> Probe:
    need("ffprobe")
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        die(f"ffprobe failed: {r.stderr.strip()[:300]}")
    data = json.loads(r.stdout)
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"), {})
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), {})
    return Probe(
        duration=float(data.get("format", {}).get("duration", 0.0)),
        vcodec=v.get("codec_name", "?"), acodec=a.get("codec_name", "?"),
        width=int(v.get("width", 0) or 0), height=int(v.get("height", 0) or 0),
        fps=v.get("r_frame_rate", "?"))


# ── audio ─────────────────────────────────────────────────


def extract_audio(inp: list[str], dest: Path) -> None:
    """Mono 16 kHz mp3. Speech-grade, and small enough that a three-hour
    recording still lands far under the API's 500 MB ceiling."""
    need("ffmpeg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = run(["ffmpeg", "-nostdin", "-y", *inp, "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "libmp3lame", "-b:a", "64k", str(dest)])
    if r.returncode != 0:
        die(f"audio extraction failed: {r.stderr.strip()[-500:]}")


def cmd_probe(args) -> None:
    d = event_dir(args.event)
    total = 0.0
    for src in find_sources(d):
        p = probe(src)
        print(f"source   : {src}")
        print(f"  size   : {src.stat().st_size / 1e9:.2f} GB")
        print(f"  span   : {hm(total)} → {hm(total + p.duration)} on the joined timeline")
        print(f"  video  : {p.vcodec} {p.width}x{p.height} @ {p.fps}")
        print(f"  audio  : {p.acodec}")
        total += p.duration
    print(f"duration : {hms(total)}  ({total/60:.1f} min)")


def cmd_audio(args) -> None:
    d = event_dir(args.event)
    out = common.work_dir(d) / "audio.mp3"
    if out.exists() and not args.force:
        print(f"exists: {out} (--force to redo)")
        return
    print("extracting audio…", file=sys.stderr)
    extract_audio(source_input(d), out)
    print(f"{out}  ({probe(out).duration/60:.1f} min)")


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[\s_]+", "-", s).strip("-") or "talk"


def cut_clip(inp: list[str], dest: Path, start: float, end: float, mode: str,
             fps: float = 0) -> None:
    """Cut [start, end) of the joined timeline into dest.

    `-ss` sits before the input, so seeking is fast; with a re-encode ffmpeg
    still decodes from the prior keyframe and drops frames up to `start`, so the
    cut is frame-accurate. Only `copy` snaps to a keyframe.
    """
    need("ffmpeg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    length = end - start
    if length <= 0:
        die(f"{dest.name}: end must be after start")
    if mode == "copy":
        cmd = ["ffmpeg", "-nostdin", "-y", "-ss", hms(start), *inp, "-t", hms(length),
               "-map", "0:v:0", "-map", "0:a:0",
               "-c", "copy", "-avoid_negative_ts", "make_zero", str(dest)]
    else:
        vcodec = (["-c:v", "h264_videotoolbox", "-b:v", "10M"] if mode == "hw"
                  else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"])
        rate = ["-r", f"{fps:g}"] if fps else []
        # -map: the Sony files carry a third, timed-metadata track (rtmd)
        # that mp4 cannot hold; take only picture and sound.
        cmd = ["ffmpeg", "-nostdin", "-y", "-ss", hms(start), *inp, "-t", hms(length),
               "-map", "0:v:0", "-map", "0:a:0", *rate,
               *vcodec, "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(dest)]
    r = run(cmd)
    if r.returncode != 0:
        die(f"cut failed for {dest.name}: {r.stderr.strip()[-500:]}")


def cmd_splice(args) -> None:
    """Build one clip from several spans of the source.

    For a talk that has to be reassembled: a demo that failed live and was shown
    later, dead air while someone fights a projector, a question that interrupts.
    Each span is encoded with identical settings so the pieces concatenate
    without a re-encode of the join.
    """
    d = event_dir(args.event)
    inp = source_input(d)
    total = total_duration(d)

    spans = []
    for spec in args.span:
        if "-" not in spec:
            die(f"--span needs START-END, got {spec!r}")
        a, _, b = spec.partition("-")
        start, end = parse_ts(a), parse_ts(b)
        if end <= start:
            die(f"span {spec}: end must be after start")
        if end > total + 1:
            die(f"span {spec}: end {hm(end)} is past the source ({hm(total)})")
        spans.append((start, end))

    out = common.clip_path(d, args.out)
    (d / args.out).mkdir(exist_ok=True)
    kept = sum(e - s for s, e in spans)
    print(f"source: {d.name}  ({hm(total)})")
    for i, (s, e) in enumerate(spans, 1):
        print(f"  part {i}  {hm(s)} → {hm(e)}  ({(e-s)/60:5.2f} min)")
    print(f"  → {out.name}  ({kept/60:.2f} min from {len(spans)} parts)")
    if args.dry_run:
        print("\n(dry run, nothing written)")
        return

    work = common.work_dir(d) / "_splice"
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, (s, e) in enumerate(spans):
        part = work / f"part{i:02d}.mp4"
        print(f"encoding part {i+1}/{len(spans)}…", file=sys.stderr)
        cut_clip(inp, part, s, e, args.mode, args.fps)
        parts.append(part)

    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    r = run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", "-movflags", "+faststart", str(out)])
    if r.returncode != 0:
        die(f"concat failed: {r.stderr.strip()[-500:]}")

    got = probe(out).duration
    drift = got - kept
    flag = "" if abs(drift) < 1.5 else f"  ⚠ {drift:+.1f}s vs the sum of the spans"
    print(f"\n  {out}  ({got/60:.2f} min){flag}")
    for p in parts:
        p.unlink(missing_ok=True)
    listing.unlink(missing_ok=True)


def talk_dir(d: Path, i: int, name: str) -> Path:
    """content/<date>/NN-speaker-slug/ — one folder per talk, holding the clip,
    the transcript and the descriptions."""
    return d / f"{i:02d}-{slugify(name)}"


def cmd_cut(args) -> None:
    d = event_dir(args.event)
    inp = source_input(d)
    total = total_duration(d)

    specs = []
    for i, spec in enumerate(args.talk, args.first):
        if "@" not in spec:
            die(f"--talk needs Name@START-END, got {spec!r}")
        name, _, span = spec.partition("@")
        if "-" not in span:
            die(f"--talk needs START-END, got {span!r}")
        a, _, b = span.partition("-")
        start, end = parse_ts(a), parse_ts(b)
        if end > total + 1:
            die(f"{name}: end {hm(end)} is past the source ({hm(total)})")
        specs.append((i, name.strip(), start, end))

    for (_, n1, _, e1), (_, n2, s2, _) in zip(specs, specs[1:]):
        if s2 < e1:
            print(f"warning: {n1} ends {hm(e1)} but {n2} starts {hm(s2)} — overlap",
                  file=sys.stderr)

    print(f"source: {d.name}  ({hm(total)})")
    for i, name, start, end in specs:
        out = common.clip_path(d, talk_dir(d, i, name).name)
        print(f"  {i:02d}  {hm(start)} → {hm(end)}  ({(end-start)/60:5.1f} min)  {out}")
    if args.dry_run:
        print("\n(dry run, nothing written)")
        return
    print()
    for i, name, start, end in specs:
        out = common.clip_path(d, talk_dir(d, i, name).name)
        print(f"cutting {out.name}…", file=sys.stderr)
        cut_clip(inp, out, start, end, args.mode, args.fps)
        got = probe(out).duration
        drift = got - (end - start)
        flag = "" if abs(drift) < 1.0 else f"  ⚠ {drift:+.1f}s vs requested"
        print(f"  {out}  ({got/60:.1f} min){flag}")


def cmd_talk(args) -> None:
    """One talk end to end, from a single span: the clip, a 30s-chunk
    transcription (plus any 10s --fix re-runs), the SUSPECT checks against the
    talk's own chunks and against work/coarse.json, and transcript.md with
    timestamps relative to the clip. The span is typed once, so the clip, the
    transcription window and the transcript offset cannot disagree.
    """
    import talk_transcript
    import transcribe_chunks

    d = event_dir(args.event)
    if "@" not in args.talk:
        die(f"--talk needs Name@START-END, got {args.talk!r}")
    name, _, span = args.talk.partition("@")
    name = name.strip()
    start, end = common.parse_span(span)
    total = total_duration(d)
    if end > total + 1:
        die(f"{name}: end {hm(end)} is past the source ({hm(total)})")

    folder = talk_dir(d, args.n, name)
    clip = common.clip_path(d, folder.name)
    folder.mkdir(parents=True, exist_ok=True)
    print(f"{folder.name}: {hm(start)} → {hm(end)}  ({(end - start) / 60:.1f} min)")
    if args.dry_run:
        print("(dry run, nothing written)")
        return

    if clip.exists() and not args.recut:
        print(f"  clip exists, keeping it (--recut to redo): {clip}", file=sys.stderr)
    else:
        print(f"  cutting {clip.name}…", file=sys.stderr)
        cut_clip(source_input(d), clip, start, end, args.mode, args.fps)
        got = probe(clip).duration
        if abs(got - (end - start)) >= 1.0:
            print(f"  ⚠ clip is {got - (end - start):+.1f}s vs requested", file=sys.stderr)

    audio = common.work_dir(d) / "audio.mp3"
    if not audio.exists():
        die(f"{audio} missing: run `meetup_video.py audio {args.event}` first")
    layers = [transcribe_chunks.transcribe(audio, start, end, 30)]
    transcribe_chunks.write(layers[0], common.work_dir(d) / f"{folder.name}.json")
    fixes: list[dict] = []
    for spec in args.fix or []:
        a, b = common.parse_span(spec)
        fixes += transcribe_chunks.transcribe(audio, a, b, 10)
    if fixes:
        transcribe_chunks.write(fixes, common.work_dir(d) / f"{folder.name}_fix.json")
        layers.append(fixes)
    merged = talk_transcript.merge(layers)

    coarse = common.work_dir(d) / "coarse.json"
    ref = json.loads(coarse.read_text()) if coarse.exists() else None
    if ref is None:
        print("  note: no work/coarse.json, so no cross-check against the coarse pass",
              file=sys.stderr)
    found = transcribe_chunks.suspects(merged, ref)
    for line in found:
        print(f"  {line}")

    md = folder / "transcript.md"
    title = args.title
    if not title and md.exists():
        first = md.read_text().splitlines()[0]
        title = first[2:].strip() if first.startswith("# ") else None
    md.write_text(talk_transcript.render(merged, start, title or name,
                                         args.speaker or name))
    print(f"  wrote {md} ({len(merged)} chunks)")
    if found:
        print("  re-run each SUSPECT span with --fix START-END (10s chunks), "
              "then read the result against the coarse pass")


def cmd_frames(args) -> None:
    """Frames over a span, for reading what was on screen.

    Writes work/frames/<tag>/: one jpg every --every seconds named by its
    timeline second, sheet-NN.jpg contact sheets (4x4, timestamps burned in)
    to read the title slide and on-screen links from, and qr.txt with every
    QR code zbarimg decodes, deduplicated, with the first second it appeared.
    """
    need("ffmpeg")
    d = event_dir(args.event)
    inp = source_input(d)
    a, _, b = args.span.partition("-")
    start, end = parse_ts(a), parse_ts(b)
    out = common.work_dir(d) / "frames" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()

    # Full resolution: a QR code on a projected slide is small in frame.
    # -skip_frame nokey: decode keyframes only. The camera writes one every
    # half second or so, plenty for a slide, and it skips decoding the other
    # 98% of a 100 fps stream — minutes instead of most of an hour.
    r = run(["ffmpeg", "-nostdin", "-y", "-skip_frame", "nokey", "-ss", hms(start), *inp,
             "-t", hms(end - start),
             "-map", "0:v:0", "-vf", f"fps=1/{args.every:g}", "-fps_mode", "cfr", "-q:v", "3",
             str(out / "f_%05d.jpg")])
    if r.returncode != 0:
        die(f"frame extraction failed: {r.stderr.strip()[-400:]}")
    frames = sorted(out.glob("f_*.jpg"))
    for n, f in enumerate(frames):
        f.rename(out / f"t{int(start + n * args.every):05d}.jpg")
    frames = sorted(out.glob("t*.jpg"))

    # Contact sheets, 16 frames each in reading order. Homebrew's ffmpeg has
    # no drawtext, so the times go in sheet-NN.txt beside each sheet: tile k
    # (left to right, top to bottom) is line k.
    for k in range(0, len(frames), 16):
        group = frames[k:k + 16]
        n = k // 16
        listing = out / "_sheet.txt"
        listing.write_text("".join(f"file '{f.resolve()}'\n" for f in group))
        run(["ffmpeg", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-vf", "scale=640:-2,tile=4x4", "-frames:v", "1", "-q:v", "4",
             str(out / f"sheet-{n:02d}.jpg")])
        (out / f"sheet-{n:02d}.txt").write_text(
            "".join(f"{j + 1:2d}  {hm(int(f.stem[1:]))}  {f.name}\n"
                    for j, f in enumerate(group)))
        listing.unlink(missing_ok=True)

    qr: dict[str, int] = {}
    if shutil.which("zbarimg"):
        for f in frames:
            r = run(["zbarimg", "-q", "--raw", "-Sdisable", "-Sqrcode.enable", str(f)])
            for line in r.stdout.splitlines():
                line = line.strip()
                if line and line not in qr:
                    qr[line] = int(f.stem[1:])
        (out / "qr.txt").write_text("".join(f"{hm(t)}\t{v}\n" for v, t in qr.items()))
    else:
        print("note: zbarimg not on PATH (brew install zbar) — QR codes not scanned",
              file=sys.stderr)

    print(f"{len(frames)} frames, {len(list(out.glob('sheet-*.jpg')))} contact sheets → {out}")
    for v, t in qr.items():
        print(f"  QR at {hm(t)}: {v}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="what is in raw/")
    p.add_argument("event")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("audio", help="extract work/audio.mp3 from raw/")
    p.add_argument("event")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_audio)

    p = sub.add_parser("frames", help="contact sheets + QR codes over a span")
    p.add_argument("event")
    p.add_argument("--span", required=True, metavar="START-END")
    p.add_argument("--tag", required=True, help="subfolder under work/frames/")
    p.add_argument("--every", type=float, default=5.0,
                   help="seconds between frames (default: 5)")
    p.set_defaults(func=cmd_frames)

    p = sub.add_parser("cut", help="cut talks out of the source")
    p.add_argument("event")
    p.add_argument("--talk", action="append", required=True, metavar="NAME@START-END",
                   help="repeat per talk, e.g. --talk 'Tim Haldorsson@12:04-22:31' "
                        "(H:MM:SS works past an hour)")
    p.add_argument("--mode", choices=["hw", "x264", "copy"], default="hw",
                   help="hw: videotoolbox, frame accurate, fast (default); "
                        "x264: slower, more portable; "
                        "copy: instant but snaps to keyframes")
    p.add_argument("--fps", type=float, default=50,
                   help="output frame rate (default: 50, half the camera's 100; "
                        "0 keeps the source rate)")
    p.add_argument("--first", type=int, default=1,
                   help="number of the first clip (default 1); e.g. --first 4 "
                        "--talk 'QA@42:10-66:12' for the Q&A after three talks")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_cut)

    p = sub.add_parser("talk", help="cut + transcribe + transcript.md for one talk")
    p.add_argument("event")
    p.add_argument("--talk", required=True, metavar="NAME@START-END",
                   help="e.g. 'David Mihal@21:42-32:10', or 'QA@42:10-66:14'")
    p.add_argument("--n", type=int, required=True, help="folder number: 1 → 01-name/")
    p.add_argument("--title", help="talk title (default: the existing transcript's h1, else the name)")
    p.add_argument("--speaker", help="byline, e.g. 'David Mihal, co-founder of Meridian'")
    p.add_argument("--fix", action="append", metavar="START-END",
                   help="re-transcribe this span in 10s chunks and patch it in; repeatable")
    p.add_argument("--recut", action="store_true", help="re-cut the clip even if it exists")
    p.add_argument("--mode", choices=["hw", "x264", "copy"], default="hw")
    p.add_argument("--fps", type=float, default=50)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_talk)

    p = sub.add_parser("splice", help="build one clip from several spans")
    p.add_argument("event")
    p.add_argument("--span", action="append", required=True, metavar="START-END",
                   help="repeat in playback order, e.g. --span 19:23-27:08")
    p.add_argument("--out", required=True, help="output basename, no extension")
    p.add_argument("--mode", choices=["hw", "x264", "copy"], default="hw")
    p.add_argument("--fps", type=float, default=50)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_splice)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
