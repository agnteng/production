#!/usr/bin/env python3
"""Cut a vertical clip from a published talk, for YouTube Shorts, X and LinkedIn.

    python3 scripts/talk_clip.py source <event> <talk>
    python3 scripts/talk_clip.py sheet  <event> <talk> --span 7:00-8:10
    python3 scripts/talk_clip.py render <event> <talk> [--id cost]

<event> is `content/<date>`, `<date>` or a Luma slug; <talk> is the talk
folder (`02-federico-kunze-kullmer`) or any unique part of it.

What a clip is lives in the talk folder as `clips.json`, one entry per clip:

    {"clips": [{"id": "cost", "start": "7:00", "end": "8:08",
                "hook": ["$1 to 15 cents", "per conversation"],
                "slide": [x, y, w, h], "speaker": [x, y, w, h]}]}

Times are from 0:00 of the talk, as in its transcript.md. `slide` and
`speaker` are boxes in the source video's pixels (the sheet labels them):
`slide` is shown 16:9 at the top, `speaker` 4:3 below it. Boxes of another
shape are widened to fit, never stretched.

The frame, 1080x1920: the hook on electric blue (0-300), the slide
(300-908), the speaker (908-1720) with captions over its lower part, and the
speaker's name and meetup on navy (1720-1920). Text is drawn by headless
Chrome from `clip.html`, because ffmpeg here has no text filters.

`render` first moves each end to the nearest pause within 1.5 s, so a clip
never opens or closes mid-word, and writes the result back as `cut`. Delete
`cut` to choose again. Captions come from a 4-second chunk pass over the cut
(transcribe_chunks.py, cached), tidied with the transcript's rules and timed
by word length within each chunk, so a caption can lead or trail by about a
second.

Output, outside the repository: `$AGNTENG_MEDIA/<date>/shorts/<talk>.<id>.mp4`
and `.srt`. The skill is `.claude/skills/talk-clip/SKILL.md`.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import common
from common import die, hm, parse_span, parse_ts
from talk_transcript import tidy

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "clip.html"
W, H = 1080, 1920
SLIDE_Y, SLIDE_H = 300, 608
SPEAKER_Y, SPEAKER_H = 908, 812
CAPTION_Y, CAPTION_H = 1500, 200
SNAP = 1.5
CHUNK = 4
CHROMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "/Applications/Chromium.app/Contents/MacOS/Chromium")


# ------------------------------------------------------------------ finding


def find_talk(event: pathlib.Path, name: str) -> pathlib.Path:
    found = [d for d in sorted(event.glob("[0-9][0-9]-*")) if d.is_dir() and name in d.name]
    if len(found) != 1:
        die(f"{name!r} matches {len(found)} talk folders in {event}: {[d.name for d in found]}")
    return found[0]


def shorts_dir(event: pathlib.Path) -> pathlib.Path:
    d = common.media_dir(event) / "shorts"
    d.mkdir(exist_ok=True)
    return d


def source(event: pathlib.Path, talk: pathlib.Path) -> pathlib.Path:
    """The talk's video: the local clip, else its YouTube upload, downloaded once."""
    local = common.clip_path(event, talk.name)
    if local.is_file():
        return local
    copy = common.media_dir(event) / f"{talk.name}.youtube.mp4"
    if copy.is_file():
        return copy
    meta = talk / "youtube.json"
    if not meta.is_file():
        die(f"{talk.name}: no local video ({local}) and no youtube.json to download it from")
    url = json.loads(meta.read_text())["url"]
    if not shutil.which("yt-dlp"):
        die("yt-dlp not found: run this under `mise exec --` (mise.toml pins it)")
    print(f"  downloading {url} → {copy}")
    r = subprocess.run(["yt-dlp", "--no-warnings", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]",
                        "--merge-output-format", "mp4", "-o", str(copy), url], capture_output=True, text=True)
    if r.returncode or not copy.is_file():
        die(f"yt-dlp: {r.stderr.strip()[-400:]}")
    return copy


def probe(video: pathlib.Path) -> tuple[int, int, float]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(video)],
                         check=True, capture_output=True, text=True).stdout
    d = json.loads(out)
    return d["streams"][0]["width"], d["streams"][0]["height"], float(d["format"]["duration"])


# ------------------------------------------------------------------- chrome


def chrome(width: int, height: int, *args: str) -> str:
    binary = next(filter(None, (shutil.which(c) for c in (os.environ.get("CHROME_BIN"), *CHROMES) if c)), None)
    if not binary:
        die("no Chrome or Chromium found: install one or set CHROME_BIN")
    with tempfile.TemporaryDirectory() as profile:
        try:
            return subprocess.run(
                [binary, "--headless=new", "--hide-scrollbars", f"--window-size={width},{height}",
                 "--force-device-scale-factor=1", "--virtual-time-budget=8000",
                 "--default-background-color=00000000", f"--user-data-dir={profile}", *args],
                check=False, capture_output=True, text=True, timeout=120).stdout
        except subprocess.TimeoutExpired:
            die("Chrome did not finish within two minutes")


def draw(cfg: dict, width: int, height: int, png: pathlib.Path) -> None:
    """Render clip.html with `cfg` to a transparent PNG."""
    with tempfile.TemporaryDirectory() as tmp:
        page = pathlib.Path(tmp) / "page.html"
        page.write_text(TEMPLATE.read_text().replace("/*CFG*/null", json.dumps(cfg).replace("</", "<\\/")))
        # Chrome screenshots whatever is there when time runs out: check first.
        title = re.search(r"<title>(.*?)</title>", chrome(width, height, "--dump-dom", page.as_uri()), re.S)
        if not title or title.group(1) != "ready":
            die(f"clip.html did not render ({title.group(1) if title else 'no title'})")
        chrome(width, height, f"--screenshot={png}", page.as_uri())
    if not png.is_file():
        die("Chrome made no screenshot")


# -------------------------------------------------------------------- sheet


def cmd_sheet(event: pathlib.Path, talk: pathlib.Path, span: str) -> None:
    """Five frames across the span, with a grid in source pixels, to choose the boxes from."""
    video = source(event, talk)
    w, h, _ = probe(video)
    a, b = parse_span(span)
    out = shorts_dir(event) / f"{talk.name}.sheet.png"
    times = [a + (b - a) * i / 4 for i in range(5)]
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(times):
            jpg = pathlib.Path(tmp) / f"{i}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                            "-q:v", "3", str(jpg)], check=True)
            frames.append((hm(t), base64.b64encode(jpg.read_bytes()).decode()))
        step = 120 if w >= 1600 else 80
        scale = 960 / w
        grid = "".join(
            f'<i style="left:{x * scale}px;top:0;width:1px;height:100%"></i><em style="left:{x * scale + 2}px;top:2px">{x}</em>'
            for x in range(0, w, step)) + "".join(
            f'<i style="top:{y * scale}px;left:0;height:1px;width:100%"></i><em style="top:{y * scale + 2}px;left:2px">{y}</em>'
            for y in range(step, h, step))
        cells = "".join(
            f'<figure><img src="data:image/jpeg;base64,{b64}"><div class="g">{grid}</div><figcaption>{t}</figcaption></figure>'
            for t, b64 in frames)
        page = pathlib.Path(tmp) / "sheet.html"
        page.write_text(f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;background:#111;display:grid;grid-template-columns:960px 960px;gap:8px;padding:8px;font:12px monospace}}
figure{{margin:0;position:relative;width:960px;height:{h * scale}px}}
img{{width:960px;display:block}} .g{{position:absolute;inset:0}}
i{{position:absolute;background:rgba(255,230,0,.55)}} em{{position:absolute;color:#ff0;font-style:normal;text-shadow:0 0 2px #000}}
figcaption{{position:absolute;right:6px;bottom:4px;color:#fff;background:#000;padding:2px 6px;font-size:16px}}
</style>{cells}""")
        rows = (len(frames) + 1) // 2
        chrome(1940, int(rows * (h * scale + 8) + 16), f"--screenshot={out}", page.as_uri())
    print(f"  {out}\n  source {w}x{h}; grid lines every {step}px, labelled in source pixels")


# ------------------------------------------------------------------- render


def silences(audio: pathlib.Path, a: float, b: float, db: int) -> list[float]:
    """Midpoints of pauses between a and b, in source seconds."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(a), "-to", str(b), "-i", str(audio),
                        "-af", f"silencedetect=noise={db}dB:d=0.12", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [a + (s + e) / 2 for s, e in zip(starts, ends)]


def snap(audio: pathlib.Path, t: float) -> float:
    """The pause nearest t, trying quieter thresholds first; t if the room never goes quiet."""
    for db in (-34, -28, -24, -20):
        found = silences(audio, max(0, t - SNAP), t + SNAP, db)
        if found:
            return min(found, key=lambda m: abs(m - t))
    print(f"  no pause within {SNAP}s of {hm(t)}: cutting there", file=sys.stderr)
    return t


def caption_lines(chunks: list[dict], start: float, end: float) -> list[tuple[float, float, str]]:
    """Short caption lines, timed by their share of each chunk's characters."""
    out = []
    for c in chunks:
        # A cut-off word ("c-", "h-") reads as a typo on screen.
        words = [w for w in tidy(c["text"]).split() if not re.fullmatch(r"\w{1,3}-[,.]?", w)]
        if not words:
            continue
        groups, cur = [], []
        for word in words:
            if cur and (len(cur) >= 4 or len(" ".join(cur + [word])) > 24):
                groups.append(cur)
                cur = []
            cur.append(word)
            if word[-1] in ".?!" and len(cur) >= 2:
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        total = sum(len(" ".join(g)) for g in groups)
        t = c["start"]
        for g in groups:
            d = (c["end"] - c["start"]) * len(" ".join(g)) / total
            a, b = max(t, start), min(t + d, end)
            if b - a > 0.05:
                out.append((a - start, b - start, " ".join(g)))
            t += d
    return out


def srt(lines: list[tuple[float, float, str]]) -> str:
    def ts(s: float) -> str:
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "".join(f"{i}\n{ts(a)} --> {ts(b)}\n{text}\n\n" for i, (a, b, text) in enumerate(lines, 1))


def fit(box: list[int], ratio: float, w: int, h: int) -> tuple[int, int, int, int]:
    """Widen the box around its centre to the ratio, kept inside the frame."""
    x, y, bw, bh = box
    if bw / bh < ratio:
        nw, nh = bh * ratio, bh
    else:
        nw, nh = bw, bw / ratio
    nw, nh = min(nw, w), min(nh, h)
    if nw / nh > ratio + 0.01:
        nw = nh * ratio
    elif nw / nh < ratio - 0.01:
        nh = nw / ratio
    cx, cy = x + bw / 2, y + bh / 2
    nx = min(max(0, cx - nw / 2), w - nw)
    ny = min(max(0, cy - nh / 2), h - nh)
    even = lambda v: int(v) // 2 * 2
    return even(nw), even(nh), even(nx), even(ny)


def meetup_line(event: pathlib.Path, speaker: str) -> tuple[str, str]:
    data = json.loads((common.WEBSITE_CONTENT / event.name / "event.json").read_text())
    title = next((s.get("title", "") for s in data.get("speakers", []) if s.get("name") == speaker), "")
    meetup = f"Agentic Engineering {data['city']} #{data['number']}"
    return speaker, f"{title} · {meetup}" if title else meetup


def render(event: pathlib.Path, talk: pathlib.Path, spec_path: pathlib.Path, only: str | None) -> None:
    spec = json.loads(spec_path.read_text())
    video = source(event, talk)
    w, h, duration = probe(video)
    speaker = json.loads((talk / "talk.json").read_text())["speaker"]
    name, line = meetup_line(event, speaker)
    work = common.work_dir(event) / "clips"
    work.mkdir(exist_ok=True)
    audio = work / f"{talk.name}.mp3"
    if not audio.is_file():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-b:a", "96k", str(audio)], check=True)
    changed = False
    for clip in spec["clips"]:
        if only and clip["id"] != only:
            continue
        missing = [k for k in ("id", "start", "end", "hook", "slide", "speaker") if not clip.get(k)]
        if missing:
            die(f"{spec_path}: clip {clip.get('id', '?')} has no {', '.join(missing)}")
        if not clip.get("cut"):
            a, b = snap(audio, parse_ts(clip["start"])), snap(audio, parse_ts(clip["end"]))
            clip["cut"] = [round(a, 2), round(b, 2)]
            changed = True
        a, b = clip["cut"]
        if not 3 <= b - a <= 140:
            die(f"clip {clip['id']}: {b - a:.0f}s long; X takes 140s at most without Premium")
        if b > duration:
            die(f"clip {clip['id']}: ends at {hm(b)}, after the video ({hm(duration)})")
        words = work / f"{talk.name}.{clip['id']}.json"
        subprocess.run([sys.executable, str(HERE / "transcribe_chunks.py"), str(audio), "--out", str(words),
                        "--seconds", str(CHUNK), "--start", f"{a:.2f}", "--end", f"{b:.2f}"], check=True)
        lines = caption_lines(json.loads(words.read_text()), a, b)
        out = shorts_dir(event) / f"{talk.name}.{clip['id']}.mp4"
        out.with_suffix(".srt").write_text(srt(lines))
        sw, sh, sx, sy = fit(clip["slide"], 16 / 9, w, h)
        pw, ph, px, py = fit(clip["speaker"], W / SPEAKER_H, w, h)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            frame, caps = tmp / "frame.png", tmp / "caps.png"
            draw({"mode": "frame", "hook": clip["hook"], "speaker": name, "line": line}, W, H, frame)
            draw({"mode": "captions", "captions": [t for _, _, t in lines]}, W, CAPTION_H * len(lines), caps)
            n = len(lines)
            graph = [
                f"color=c=0x05071e:s={W}x{H}:r=30:d={b - a:.3f}[bg]",
                "[0:v]split=2[v1][v2]",
                f"[v1]crop={sw}:{sh}:{sx}:{sy},scale={W}:{SLIDE_H},setsar=1[slide]",
                f"[v2]crop={pw}:{ph}:{px}:{py},scale={W}:{SPEAKER_H},setsar=1[spk]",
                f"[bg][slide]overlay=0:{SLIDE_Y}[l1]",
                f"[l1][spk]overlay=0:{SPEAKER_Y}[l2]",
                "[l2][1:v]overlay=0:0[l3]",
                f"[2:v]split={n}" + "".join(f"[s{i}]" for i in range(n)) if n > 1 else "[2:v]null[s0]",
            ]
            last = "l3"
            for i, (ca, cb, _) in enumerate(lines):
                graph.append(f"[s{i}]crop={W}:{CAPTION_H}:0:{i * CAPTION_H}[k{i}]")
                graph.append(f"[{last}][k{i}]overlay=0:{CAPTION_Y}:enable='between(t,{ca:.3f},{cb:.3f})'[c{i}]")
                last = f"c{i}"
            graph.append(f"[{last}]format=yuv420p[vout]")
            fade = max(0.0, b - a - 0.2)
            graph.append(f"[0:a]afade=t=in:d=0.12,afade=t=out:st={fade:.3f}:d=0.2,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(video),
                            "-loop", "1", "-i", str(frame), "-loop", "1", "-i", str(caps),
                            "-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]",
                            "-t", f"{b - a:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(out)], check=True)
        print(f"  {out}  {hm(a)}-{hm(b)} ({b - a:.0f}s), {n} captions\n  {out.with_suffix('.srt')}")
    if changed:
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")
        print(f"  {spec_path.relative_to(common.ROOT)}: cut written back")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("source", "sheet", "render"):
        s = sub.add_parser(name)
        s.add_argument("event")
        s.add_argument("talk")
        if name == "sheet":
            s.add_argument("--span", required=True, help="START-END from 0:00 of the talk, e.g. 7:00-8:10")
        if name == "render":
            s.add_argument("--id", help="render only this clip")
    args = p.parse_args()
    event = common.event_dir(args.event)
    talk = find_talk(event, args.talk)
    if args.cmd == "source":
        print(source(event, talk))
    elif args.cmd == "sheet":
        cmd_sheet(event, talk, args.span)
    else:
        spec = talk / "clips.json"
        if not spec.is_file():
            die(f"{spec.relative_to(common.ROOT)} does not exist: write it first (see --help)")
        render(event, talk, spec, args.id)


if __name__ == "__main__":
    main()
