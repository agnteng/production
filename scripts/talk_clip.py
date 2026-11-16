# /// script
# requires-python = ">=3.12"
# dependencies = ["opencv-python-headless==4.11.0.86", "pillow==12.3.0", "numpy==2.2.6"]
# ///
"""Cut a vertical clip from a published talk, for YouTube Shorts, X and LinkedIn.

    mise exec -- uv run scripts/talk_clip.py source <event> <talk>
    mise exec -- uv run scripts/talk_clip.py render <event> <talk> [--id why]
    mise exec -- uv run scripts/talk_clip.py frames <event> <talk> --id why

<event> is `content/<date>`, `<date>` or a Luma slug; <talk> is the talk
folder (`02-david-mihal`) or any unique part of it.

The look: the speaker, full screen, and big captions of one to three words.
No title band, no name, no slide panel: the post's text carries the hook.
The camera follows the speaker's face and cuts between a wide shot and a
close one at the end of each sentence, with a slow push-in during each shot.
Captions are Manrope ExtraBold in capitals, white, or signal yellow when the
group holds a number or a word listed in `highlight`.

What a clip is lives in the talk folder as `clips.json`:

    {"clips": [{"id": "why", "start": "3:50", "end": "4:28",
                "highlight": ["why", "weird"]}]}

Times are from 0:00 of the talk, as in its transcript.md. Optional: `face`,
`[x, y]` in source pixels near the speaker at the start, when another face
could be taken for theirs. `render` moves each end to the nearest pause within
1.5 s and writes it back as `cut`; delete `cut` to choose again.

Captions come from a 4-second chunk pass over the cut (transcribe_chunks.py,
cached). Inside each chunk, words are spread over the moments the speaker is
actually loud, so a caption lands within a few tenths of a second of the word.
Fix a misheard word in `work/clips/<talk>.<id>.json` and render again.

Output, outside the repository: `$AGNTENG_MEDIA/<date>/shorts/<talk>.<id>.mp4`
and `.srt`. Fonts and the face model are fetched once into ~/.cache/agnteng
and checked against pinned hashes. The skill is `.claude/skills/talk-clip/SKILL.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import common
from common import die, hm, parse_ts
from talk_transcript import tidy

HERE = pathlib.Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30
SNAP = 1.5
CHUNK = 4
CACHE = pathlib.Path.home() / ".cache" / "agnteng"
ASSETS = {
    "font": ("https://github.com/google/fonts/raw/b31870aff700ab7a1d74fa0c6887d95beb9e0037/ofl/manrope/Manrope%5Bwght%5D.ttf",
             "3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6", "Manrope-wght.ttf"),
    "face": ("https://github.com/opencv/opencv_zoo/raw/f12e12798e8314f7c074a6656816c048dcc95b7a/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
             "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4", "face_detection_yunet_2023mar.onnx"),
}
WHITE, YELLOW, NAVY = (244, 245, 255), (249, 200, 53), (5, 7, 30)
CAPTION_Y = 0.70          # centre of the caption, as a share of the height
CAPTION_PX = 104
MIN_SHOT = 2.4            # seconds before the framing may cut again


def asset(name: str) -> pathlib.Path:
    url, digest, filename = ASSETS[name]
    path = CACHE / filename
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".part")
        urllib.request.urlretrieve(url, part)
        if hashlib.sha256(part.read_bytes()).hexdigest() != digest:
            part.unlink()
            die(f"{url}: unexpected checksum; not using it")
        part.rename(path)
    return path


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


# -------------------------------------------------------------------- audio

HOP = 0.02  # seconds per loudness frame


def loudness(video: pathlib.Path, a: float, b: float) -> np.ndarray:
    """dB per 20 ms from a to b."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, a):.3f}", "-to", f"{b:.3f}", "-i", str(video),
                          "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], check=True, capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = int(16000 * HOP)
    frames = x[: len(x) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-6)


def snap(video: pathlib.Path, t: float) -> float:
    """The quiet moment nearest t, within SNAP seconds; t if there is none."""
    start = max(0.0, t - SNAP)
    db = loudness(video, start, t + SNAP)
    quiet = db < np.percentile(db, 20) + 4
    best, run = None, 0
    for i, q in enumerate(quiet):
        run = run + 1 if q else 0
        if run >= 5:  # 100 ms
            centre = start + (i - run / 2) * HOP
            if best is None or abs(centre - t) < abs(best - t):
                best = centre
    if best is None:
        print(f"  no pause within {SNAP}s of {hm(t)}: cutting there", file=sys.stderr)
        return t
    return best


# ----------------------------------------------------------------- captions


def word_times(chunks: list[dict], a: float, db: np.ndarray) -> list[tuple[float, float, str]]:
    """(start, end, word) relative to a, each chunk's words spread over its loud frames."""
    active = db > np.percentile(db, 25) + 6
    out = []
    for c in chunks:
        words = [w for w in tidy(c["text"]).split() if not re.fullmatch(r"\w{1,3}-[,.]?", w)]
        if not words:
            continue
        i0, i1 = int((c["start"] - a) / HOP), int((c["end"] - a) / HOP)
        idx = [i for i in range(max(0, i0), min(len(active), i1)) if active[i]] or list(range(max(0, i0), min(len(db), i1)))
        if not idx:
            continue
        weights = np.array([len(w) + 1 for w in words], float)
        edges = np.concatenate([[0], np.cumsum(weights)]) / weights.sum()
        for k, w in enumerate(words):
            s = idx[min(len(idx) - 1, int(edges[k] * len(idx)))] * HOP
            e = (idx[min(len(idx) - 1, max(0, int(edges[k + 1] * len(idx)) - 1))] + 1) * HOP
            out.append((s, max(e, s + 0.08), w))
    return out


def groups(words: list[tuple[float, float, str]], highlight: set[str], length: float) -> list[dict]:
    """One to three words per caption, broken at punctuation."""
    out, cur = [], []
    def flush():
        if cur:
            out.append(cur[:])
            cur.clear()
    for w in words:
        shown = " ".join(x[2] for x in cur + [w])
        if cur and (len(cur) >= 3 or len(re.sub(r"[^\w?' ]", "", shown)) > 15):
            flush()
        cur.append(w)
        if w[2][-1] in ".,?!;:":
            flush()
    flush()
    caps = []
    for i, g in enumerate(out):
        text = " ".join(re.sub(r"[.,;:!\"“”]+$|^[\"“”]+", "", x[2]) for x in g).upper()
        plain = {re.sub(r"[^\w']", "", x[2]).lower() for x in g}
        start = g[0][0]
        nxt = out[i + 1][0][0] if i + 1 < len(out) else length
        end = min(nxt, g[-1][1] + 0.35)
        caps.append({"start": start, "end": max(end, start + 0.25), "text": text,
                     "hot": bool(plain & highlight) or any(ch.isdigit() for ch in text),
                     "stop": g[-1][2][-1] in ".?!"})
    return caps


def srt(caps: list[dict]) -> str:
    def ts(s: float) -> str:
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "".join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text'].capitalize()}\n\n" for i, c in enumerate(caps, 1))


def caption_image(text: str, hot: bool) -> np.ndarray:
    """RGBA: the caption in Manrope ExtraBold with a navy edge and a soft shadow."""
    font = ImageFont.truetype(str(asset("font")), CAPTION_PX)
    font.set_variation_by_axes([800])
    size = CAPTION_PX
    while font.getlength(text) > W - 120 and size > 56:
        size -= 4
        font = ImageFont.truetype(str(asset("font")), size)
        font.set_variation_by_axes([800])
    pad = 40
    l, t, r, b = font.getbbox(text, stroke_width=8)
    img = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((pad - l, pad - t + 6), text, font=font, fill=(0, 0, 0, 170),
                                stroke_width=10, stroke_fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(img).text((pad - l, pad - t), text, font=font, fill=YELLOW if hot else WHITE,
                             stroke_width=8, stroke_fill=NAVY)
    return np.array(img)


# -------------------------------------------------------------------- faces


def track(video: pathlib.Path, a: float, b: float, sw: int, sh: int, hint: list[int] | None) -> tuple[np.ndarray, np.ndarray, float]:
    """Smoothed face centre (x, y) per output frame in source pixels, and the median face height."""
    step, scale = 0.2, 960 / sw
    dw, dh = 960, int(round(sh * scale))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(video),
                          "-vf", f"fps={1 / step},scale={dw}:{dh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         check=True, capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, dh, dw, 3)
    det = cv2.FaceDetectorYN.create(str(asset("face")), "", (dw, dh), 0.55)
    prev = (hint[0] * scale, hint[1] * scale) if hint else None
    xs, ys, hs = [], [], []
    for f in frames:
        _, faces = det.detect(f)
        pick = None
        if faces is not None and len(faces):
            cands = [(x + w / 2, y + h / 2, h) for x, y, w, h in faces[:, :4] if y + h < dh * 0.85]
            if cands:
                if prev:
                    near = min(cands, key=lambda c: (c[0] - prev[0]) ** 2 + (c[1] - prev[1]) ** 2)
                    if abs(near[0] - prev[0]) < dw * 0.2:
                        pick = near
                else:
                    pick = max(cands, key=lambda c: c[2])
        if pick:
            prev = pick[:2]
        xs.append(pick[0] if pick else np.nan)
        ys.append(pick[1] if pick else np.nan)
        hs.append(pick[2] if pick else np.nan)
    xs, ys = np.array(xs), np.array(ys)
    found = ~np.isnan(xs)
    if found.sum() < max(3, len(xs) // 4):
        die(f"found the speaker's face in {found.sum()} of {len(xs)} samples: set `face` in clips.json")
    t = np.arange(len(xs)) * step
    xs, ys = np.interp(t, t[found], xs[found]), np.interp(t, t[found], ys[found])
    k = np.ones(9) / 9  # 1.8 s: a calm camera, not a twitchy one
    xs = np.convolve(np.pad(xs, 4, mode="edge"), k, "valid")
    ys = np.convolve(np.pad(ys, 4, mode="edge"), k, "valid")
    n = int(round((b - a) * FPS))
    tt = np.arange(n) / FPS
    return np.interp(tt, t, xs) / scale, np.interp(tt, t, ys) / scale, float(np.nanmedian(hs)) / scale


def shots(caps: list[dict], length: float) -> list[tuple[float, str]]:
    """(start, framing): close first, then cut at sentence ends at most every MIN_SHOT seconds."""
    out, last = [(0.0, "close")], 0.0
    for c in caps:
        if c["stop"] and c["end"] - last >= MIN_SHOT and length - c["end"] >= MIN_SHOT:
            out.append((c["end"], "wide" if out[-1][1] == "close" else "close"))
            last = c["end"]
    return out


# ------------------------------------------------------------------- render


def render(event: pathlib.Path, talk: pathlib.Path, spec_path: pathlib.Path, only: str | None) -> None:
    spec = json.loads(spec_path.read_text())
    video = source(event, talk)
    sw, sh, duration = probe(video)
    work = common.work_dir(event) / "clips"
    work.mkdir(exist_ok=True)
    audio = work / f"{talk.name}.mp3"
    if not audio.is_file():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-b:a", "96k", str(audio)], check=True)
    for clip in spec["clips"]:
        if only and clip["id"] != only:
            continue
        if not clip.get("cut"):
            clip["cut"] = [round(snap(video, parse_ts(clip["start"])), 2), round(snap(video, parse_ts(clip["end"])), 2)]
            spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")
        a, b = clip["cut"]
        length = b - a
        if not 3 <= length <= 140:
            die(f"clip {clip['id']}: {length:.0f}s long; X takes 140s at most without Premium")
        if b > duration:
            die(f"clip {clip['id']}: ends at {hm(b)}, after the video ({hm(duration)})")
        words_file = work / f"{talk.name}.{clip['id']}.json"
        # A words file for this cut is kept, hand corrections included; a new cut replaces it.
        kept = json.loads(words_file.read_text()) if words_file.is_file() else []
        if not kept or abs(kept[0]["start"] - a) > 0.05:
            subprocess.run([sys.executable, str(HERE / "transcribe_chunks.py"), str(audio), "--out", str(words_file),
                            "--seconds", str(CHUNK), "--start", f"{a:.2f}", "--end", f"{b:.2f}"],
                           check=True, stdout=subprocess.DEVNULL)
        db = loudness(video, a, b)
        caps = groups(word_times(json.loads(words_file.read_text()), a, db),
                      {w.lower() for w in clip.get("highlight", [])}, length)
        out = shorts_dir(event) / f"{talk.name}.{clip['id']}.mp4"
        out.with_suffix(".srt").write_text(srt(caps))
        fx, fy, face_h = track(video, a, b, sw, sh, clip.get("face"))
        cuts = shots(caps, length)
        images = [caption_image(c["text"], c["hot"]) for c in caps]
        n = len(fx)
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(video),
                                "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                "-r", str(FPS), "-i", "-", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(video),
                                "-map", "0:v", "-map", "1:a", "-af",
                                f"afade=t=in:d=0.1,afade=t=out:st={max(0, length - 0.2):.3f}:d=0.2,loudnorm=I=-14:TP=-1.5:LRA=11",
                                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                                "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)],
                               stdin=subprocess.PIPE)
        close_h = float(np.clip(face_h * 6.5, sh * 0.45, sh * 0.7))
        size = sw * sh * 3
        for i in range(n):
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
            t = i / FPS
            k = max(j for j, (s, _) in enumerate(cuts) if s <= t + 1e-6)
            s0, framing = cuts[k]
            s1 = cuts[k + 1][0] if k + 1 < len(cuts) else length
            push = 1 - 0.05 * (t - s0) / max(0.1, s1 - s0)  # 5% slow push-in per shot
            ch = (sh if framing == "wide" else close_h) * push
            cw = ch * W / H
            cx = fx[i] - cw / 2
            cy = (sh - ch) / 2 if framing == "wide" else fy[i] - ch * 0.34
            cx, cy = float(np.clip(cx, 0, sw - cw)), float(np.clip(cy, 0, sh - ch))
            crop = frame[int(cy):int(cy + ch), int(cx):int(cx + cw)]
            img = cv2.resize(crop, (W, H), interpolation=cv2.INTER_LANCZOS4)
            for c, im in zip(caps, images):
                if c["start"] <= t < c["end"]:
                    age = t - c["start"]
                    if age < 0.1:  # a small pop as each caption appears
                        f = 0.86 + 1.4 * age
                        im = cv2.resize(im, (max(1, int(im.shape[1] * f)), max(1, int(im.shape[0] * f))), interpolation=cv2.INTER_AREA)
                    ih, iw = im.shape[:2]
                    x0, y0 = (W - iw) // 2, int(H * CAPTION_Y - ih / 2)
                    region = img[y0:y0 + ih, x0:x0 + iw].astype(np.float32)
                    alpha = im[:, :, 3:4].astype(np.float32) / 255
                    img[y0:y0 + ih, x0:x0 + iw] = (region * (1 - alpha) + im[:, :, :3] * alpha).astype(np.uint8)
                    break
            enc.stdin.write(img.tobytes())
        enc.stdin.close()
        dec.kill()
        dec.wait()
        if enc.wait():
            die("ffmpeg could not encode the clip")
        print(f"  {out}  {hm(a)}-{hm(b)} ({length:.0f}s), {len(caps)} captions, {len(cuts)} shots\n  {out.with_suffix('.srt')}")


def frames(event: pathlib.Path, talk: pathlib.Path, clip_id: str) -> None:
    """Twelve frames of the rendered clip on one sheet, to check it without playing it."""
    out = shorts_dir(event) / f"{talk.name}.{clip_id}.mp4"
    if not out.is_file():
        die(f"{out} does not exist: render it first")
    _, _, length = probe(out)
    sheet = out.with_suffix(".frames.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf",
                    f"fps={12 / length:.4f},scale=270:-1,tile=6x2", "-frames:v", "1", "-q:v", "3", str(sheet)], check=True)
    print(f"  {sheet}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("source", "render", "frames"):
        s = sub.add_parser(name)
        s.add_argument("event")
        s.add_argument("talk")
        if name != "source":
            s.add_argument("--id", required=name == "frames", help="the clip's id in clips.json")
    args = p.parse_args()
    event = common.event_dir(args.event)
    talk = find_talk(event, args.talk)
    if args.cmd == "source":
        print(source(event, talk))
    elif args.cmd == "frames":
        frames(event, talk, args.id)
    else:
        spec = talk / "clips.json"
        if not spec.is_file():
            die(f"{spec.relative_to(common.ROOT)} does not exist: write it first (see --help)")
        render(event, talk, spec, args.id)


if __name__ == "__main__":
    main()
