# /// script
# requires-python = ">=3.12"
# dependencies = ["opencv-python-headless==4.11.0.86", "pillow==12.3.0", "numpy==2.3.5", "rembg==2.0.86", "onnxruntime==1.31.1"]
# ///
"""Cut a short-form clip from a published talk, for YouTube Shorts, X and LinkedIn.

    mise exec -- uv run scripts/talk_clip.py words  <event> <talk> --id why
    mise exec -- uv run scripts/talk_clip.py render <event> <talk> --id why
    mise exec -- uv run scripts/talk_clip.py frames <event> <talk> --id why

<event> is `content/<date>`, `<date>` or a Luma slug; <talk> is the talk
folder (`02-david-mihal`) or any unique part of it.

A clip, in `clips.json` in the talk folder:

    {"clips": [{"id": "why", "start": "3:50", "end": "4:26",
                "hook": {"from": "your agent", "to": "do that"},
                "highlight": ["why", "weird", "decisions", "context"],
                "stickers": {"weird": "1f914", "agent": "1f916", "context": "1f9e0"},
                "music": "voxel-revolution"}]}

`start`/`end` (from 0:00 of the talk) is the body. `hook` names the first and
last words of the cold open: a line from inside the body, played first over a
rising drone, then a zoom-blur, a hit and the beat drop into the body. Pauses
longer than 0.28 s are tightened to 0.1 s; every join is hidden by a change of
framing. `highlight` words are yellow, bigger, and punch the camera in;
`stickers` maps a word to a Noto 3D emoji code point that pops above the
speaker when it is said. `words` prints the timed words of the body so the hook
and highlights can be chosen from them.

Pipeline: Python cuts, tightens, tracks the face, frames and grades the
footage (`camera.mp4`) and assembles the voice; `short.html`, rendered by
HyperFrames, adds every caption, transition and effect; ffmpeg mixes the voice,
the music (ducked under the voice) and the sound effects (`sfx.py`) and muxes.
Project and output: `$AGNTENG_MEDIA/<date>/shorts/<talk>.<id>/` and
`<talk>.<id>.mp4` beside it. The skill is `.claude/skills/talk-clip/SKILL.md`.
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

import align
import common
import sfx
from common import die, hm, parse_ts
from talk_transcript import tidy

HERE = pathlib.Path(__file__).resolve().parent
W, H, FPS, SR = 1080, 1920, 30, 48000
SNAP = 1.5
CHUNK = 4
HOP = 0.02
CACHE = pathlib.Path.home() / ".cache" / "agnteng"
FONT = ("https://github.com/google/fonts/raw/b31870aff700ab7a1d74fa0c6887d95beb9e0037/ofl/manrope/Manrope%5Bwght%5D.ttf",
        "3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6", "Manrope-wght.ttf")
FACE = ("https://github.com/opencv/opencv_zoo/raw/f12e12798e8314f7c074a6656816c048dcc95b7a/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4", "face_detection_yunet_2023mar.onnx")
EMOJI_COMMIT = "d6a792cb12e3eb7224f4fbf13173a0dded455651"  # googlefonts/noto-emoji, 3D set (OFL / Apache-2.0)
MONTSERRAT = ("https://github.com/google/fonts/raw/8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5/ofl/montserrat/Montserrat-Italic%5Bwght%5D.ttf",
              "51607f316bc020e59f03cbf51543eecffbea501c0b31d73e5b82927c5cca442c", "Montserrat-Italic-wght.ttf")  # OFL
IMAGE_MODEL = "google/gemini-3-pro-image"
# One look for every generated image, so a clip's cutaways belong together and to the brand.
LOOK = ("Cinematic 3D render. Dark navy (#05071e) surroundings, electric blue (#1e2be6) rim light, warm signal-yellow "
        "(#f9c835) accent light, soft volumetric light, shallow depth of field, rich contrast. No text, letters, logos "
        "or watermark unless the description names them.")
ICON = ("A single 3D emoji-style icon, glossy and rounded like Apple or Noto 3D emoji, soft studio light, centred and "
        "filling most of a square frame, isolated on a plain flat pure white background, no ground shadow. No text unless "
        "the description names it.")
MUSIC = HERE / "music.json"
SIMPLE_ICONS = "16.30.0"  # CC0 brand marks; a product named on stage pops in as its logo
GAP_MAX, GAP_KEEP = 0.28, 0.10   # pauses longer than this shrink to this
MIN_SHOT, MAX_SHOT = 1.4, 3.0    # seconds between framing changes
SMALL = {"the", "a", "an", "you", "we", "i", "and", "it's", "its", "now", "so", "to", "of", "in", "on", "is", "that",
         "this", "it", "they", "or", "but", "if", "be", "at", "like", "how", "your", "my", "our"}


def fetch(url: str, digest: str, path: pathlib.Path) -> pathlib.Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(url, part)
        if digest and hashlib.sha256(part.read_bytes()).hexdigest() != digest:
            part.unlink()
            die(f"{url}: unexpected checksum; not using it")
        part.rename(path)
    return path


def asset(spec: tuple[str, str, str]) -> pathlib.Path:
    return fetch(spec[0], spec[1], CACHE / spec[2])


def emoji(code: str) -> pathlib.Path:
    return fetch(f"https://github.com/googlefonts/noto-emoji/raw/{EMOJI_COMMIT}/3D/png/512/emoji_u{code}.png", "",
                 CACHE / "emoji3d" / f"{code}.png")


def music_track(name: str) -> tuple[pathlib.Path, dict]:
    tracks = json.loads(MUSIC.read_text())
    if name not in tracks:
        die(f"no track {name!r} in {MUSIC.name}: {', '.join(tracks)}")
    t = tracks[name]
    return fetch(t["url"], t["sha256"], CACHE / "music" / f"{name}.mp3"), t


def generate(prompt: str, kind: str, folder: pathlib.Path) -> pathlib.Path:
    """A generated image: `full` is a 9:16 cutaway, `icon` a cut-out sticker. Cached by model, kind and prompt."""
    import base64
    from PIL import Image
    key = hashlib.sha256(f"{IMAGE_MODEL}|{kind}|{prompt}".encode()).hexdigest()[:12]
    out = folder / f"{key}.png"
    if out.exists():
        return out
    folder.mkdir(parents=True, exist_ok=True)
    body = {"model": IMAGE_MODEL, "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": "9:16" if kind == "full" else "1:1"},
            "messages": [{"role": "user", "content": f"{prompt}. {LOOK if kind == 'full' else ICON}"}]}
    for _ in range(3):
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {common.openrouter_key()}", "Content-Type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=300).read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 402):
                die(f"OpenRouter HTTP {e.code}: the key needs replacing; stop here")
            continue
        images = r["choices"][0]["message"].get("images") or []
        if images:
            raw = out.with_suffix(".raw.png")
            raw.write_bytes(base64.b64decode(images[0]["image_url"]["url"].split(",", 1)[1]))
            break
    else:
        die(f"{IMAGE_MODEL}: no image for {prompt!r}")
    if kind == "icon":
        from rembg import new_session, remove
        cut = remove(Image.open(raw).convert("RGB"), session=new_session("isnet-general-use"))
        box = cut.getbbox()
        cut = cut.crop(box) if box else cut
        side = max(cut.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(cut, ((side - cut.width) // 2, (side - cut.height) // 2))
        square.resize((512, 512), Image.LANCZOS).save(out)
    else:
        Image.open(raw).convert("RGB").save(out)
    print(f"  generated {kind}: {prompt[:60]}… → {out.name}")
    return out


def logo(slug: str, folder: pathlib.Path) -> pathlib.Path:
    """A brand's Simple Icons mark in its colour on a white rounded card, as SVG."""
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{slug}.svg"
    if not out.exists():
        base = f"https://cdn.jsdelivr.net/npm/simple-icons@{SIMPLE_ICONS}"
        data = json.loads(urllib.request.urlopen(f"{base}/data/simple-icons.json", timeout=60).read())
        icons = data if isinstance(data, list) else data.get("icons", [])
        hexcol = next((i["hex"] for i in icons if i.get("slug") == slug or i.get("title", "").lower() == slug), None)
        svg = urllib.request.urlopen(f"{base}/icons/{slug}.svg", timeout=60).read().decode()
        path = re.search(r'<path d="([^"]+)"', svg)
        if not hexcol or not path:
            die(f"no Simple Icons logo {slug!r} in {SIMPLE_ICONS}")
        out.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect width="120" height="120" rx="28" '
                       f'fill="#ffffff"/><g transform="translate(26 26) scale(2.8333)"><path fill="#{hexcol}" d="{path.group(1)}"/>'
                       f'</g></svg>')
    return out


# ------------------------------------------------------------------ finding


def find_talk(event: pathlib.Path, name: str) -> pathlib.Path:
    found = [d for d in sorted(event.glob("[0-9][0-9]-*")) if d.is_dir() and name in d.name]
    if len(found) != 1:
        die(f"{name!r} matches {len(found)} talk folders in {event}: {[d.name for d in found]}")
    return found[0]


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


def pcm(video: pathlib.Path, a: float, b: float, rate: int = 16000, channels: int = 1) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, a):.3f}", "-to", f"{b:.3f}", "-i", str(video),
                          "-vn", "-ac", str(channels), "-ar", str(rate), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    return x.reshape(-1, channels) if channels > 1 else x


def loudness(video: pathlib.Path, a: float, b: float) -> np.ndarray:
    """dB per 20 ms from a to b."""
    x = pcm(video, a, b)
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
        if run >= 5:
            centre = start + (i - run / 2) * HOP
            if best is None or abs(centre - t) < abs(best - t):
                best = centre
    if best is None:
        print(f"  no pause within {SNAP}s of {hm(t)}: cutting there", file=sys.stderr)
        return t
    return best


def quietest(video: pathlib.Path, lo: float, hi: float) -> float:
    db = loudness(video, lo, hi)
    return lo + (int(np.argmin(db)) + 0.5) * HOP if len(db) else (lo + hi) / 2


def keep_ranges(video: pathlib.Path, words: list[dict], keep: list | None, a: float, b: float) -> list[tuple[float, float]]:
    """The source ranges of the body: the whole cut, or each `keep` phrase from its first word to its last,
    cut on the quietest instant just before and just after it, so a join never clips a word."""
    if not keep:
        return [(a, b, 0, len(words) - 1)]
    out, after = [], 0
    for k in keep:
        first, last = (k["from"], k["to"]) if isinstance(k, dict) else k[:2]
        i = find_phrase(words, first, after)
        j = find_phrase(words, last, i) + len(last.split()) - 1
        prev_e = words[i - 1]["e"] if i > 0 else words[i]["s"] - 0.15
        next_s = words[j + 1]["s"] if j + 1 < len(words) else words[j]["e"] + 0.15
        lo = quietest(video, max(prev_e, words[i]["s"] - 0.15), words[i]["s"] + 0.01)
        hi = quietest(video, words[j]["e"] - 0.01, min(next_s, words[j]["e"] + 0.15))
        out.append((max(a, lo), min(b, hi), i, j))
        after = j + 1
    return out


def first_pause(video: pathlib.Path, a: float, b: float, last: bool = False) -> float | None:
    """The middle of the first (or last) quiet stretch of 80 ms or more between a and b: where a word ends."""
    db = loudness(video, a, b)
    quiet = db < np.percentile(loudness(video, a - 3, b + 3), 25) + 5
    runs, i = [], 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - i) * HOP >= 0.08:
                runs.append(a + (i + j) / 2 * HOP)
            i = j
        else:
            i += 1
    return (runs[-1] if last else runs[0]) if runs else None


def keep_spans(db: np.ndarray, a: float, b: float) -> list[tuple[float, float]]:
    """[a, b] without its long pauses: each pause over GAP_MAX shrinks to GAP_KEEP."""
    quiet = db < np.percentile(db, 30) + 5
    spans, cur, i = [], a, 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - i) * HOP > GAP_MAX and i > 0 and j < len(quiet):
                s, e = a + i * HOP + GAP_KEEP / 2, a + j * HOP - GAP_KEEP / 2
                spans.append((cur, s))
                cur = e
            i = j
        else:
            i += 1
    spans.append((cur, b))
    return [(s, e) for s, e in spans if e - s > 0.05]


# ----------------------------------------------------------------- words


def word_times(chunks: list[dict], a: float, db: np.ndarray) -> list[dict]:
    """Source-time words, each chunk's words spread over its loud frames."""
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
            out.append({"w": w, "s": a + s, "e": a + max(e, s + 0.08)})
    return out


def bare(w: str) -> str:
    return re.sub(r"[^\w']", "", w).lower()


def shown(w: str) -> str:
    return re.sub(r"[.,;:!\"“”]+$|^[\"“”]+", "", w).upper()


def find_phrase(words: list[dict], phrase: str, after: int = 0) -> int:
    toks = [bare(t) for t in phrase.split()]
    for i in range(after, len(words) - len(toks) + 1):
        if [bare(words[i + k]["w"]) for k in range(len(toks))] == toks:
            return i
    die(f"the words {phrase!r} are not in the clip's transcript: run `words` and copy them exactly")


def body_words(event: pathlib.Path, talk: pathlib.Path, video: pathlib.Path, clip: dict, spec_path: pathlib.Path,
               spec: dict) -> tuple[float, float, list[dict]]:
    if not clip.get("cut"):
        clip["cut"] = [round(snap(video, parse_ts(clip["start"])), 2), round(snap(video, parse_ts(clip["end"])), 2)]
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")
    a, b = clip["cut"]
    work = common.work_dir(event) / "clips"
    work.mkdir(exist_ok=True)
    audio = work / f"{talk.name}.mp3"
    if not audio.is_file():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-b:a", "96k", str(audio)], check=True)
    words_file = work / f"{talk.name}.{clip['id']}.json"
    # Kept with its hand corrections as long as the cut stays; a new cut replaces it.
    kept = json.loads(words_file.read_text()) if words_file.is_file() else []
    if not kept or abs(kept[0]["start"] - a) > 0.05 or kept[-1]["end"] < b - 0.5:
        subprocess.run([sys.executable, str(HERE / "transcribe_chunks.py"), str(audio), "--out", str(words_file),
                        "--seconds", str(CHUNK), "--start", f"{a:.2f}", "--end", f"{b:.2f}"],
                       check=True, stdout=subprocess.DEVNULL)
    chunks = json.loads(words_file.read_text())
    span_end = max(b, max(c["end"] for c in chunks))
    return a, b, [w for w in timed_words(video, chunks, a, span_end) if w["s"] < b - 0.05]


def timed_words(video: pathlib.Path, chunks: list[dict], a: float, b: float) -> list[dict]:
    """The transcript's words with the times forced alignment finds for them (ADR 0006); a word it cannot
    place sits between its neighbours. Without the aligner, the old estimate: each chunk's words spread over
    its loud frames, off by up to a second."""
    texts = [w for c in chunks for w in tidy(c["text"]).split() if not re.fullmatch(r"\w{1,3}-[,.]?", w)]
    try:
        spans = align.align(pcm(video, a, b), texts)
    except Exception as e:  # noqa: BLE001 - the estimate is a usable fallback
        print(f"  forced alignment failed ({e}); estimating word times", file=sys.stderr)
        return word_times(chunks, a, loudness(video, a, b))
    out = [{"w": w, "s": a + sp[0], "e": a + sp[1]} if sp else {"w": w, "s": None, "e": None} for w, sp in zip(texts, spans)]
    for i, w in enumerate(out):
        if w["s"] is None:
            prev = next((x["e"] for x in reversed(out[:i]) if x["s"] is not None), a)
            nxt = next((x["s"] for x in out[i + 1:] if x["s"] is not None), b)
            w["s"], w["e"] = prev, max(prev + 0.05, nxt)
    return out


# -------------------------------------------------------------------- faces


def track(video: pathlib.Path, a: float, b: float, sw: int, sh: int, hint: list[int] | None):
    """Face centre (x, y) as functions of source time, smoothed, and the median face height."""
    step, scale = 0.2, 960 / sw
    dw, dh = 960, int(round(sh * scale))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(video),
                          "-vf", f"fps={1 / step},scale={dw}:{dh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         check=True, capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, dh, dw, 3)
    det = cv2.FaceDetectorYN.create(str(asset(FACE)), "", (dw, dh), 0.55)
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
                    pick = near if abs(near[0] - prev[0]) < dw * 0.2 else None
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
    t = a + np.arange(len(xs)) * step
    xs, ys = np.interp(t, t[found], xs[found]), np.interp(t, t[found], ys[found])
    k = np.ones(7) / 7
    xs = np.convolve(np.pad(xs, 3, mode="edge"), k, "valid") / scale
    ys = np.convolve(np.pad(ys, 3, mode="edge"), k, "valid") / scale
    return (lambda s: float(np.interp(s, t, xs))), (lambda s: float(np.interp(s, t, ys))), float(np.nanmedian(hs)) / scale


# ------------------------------------------------------------------- timing


def timeline(segments: list[tuple[float, float]]) -> list[tuple[float, float, float]]:
    """(source start, source end, output start) for each kept span, back to back."""
    out, t = [], 0.0
    for s, e in segments:
        out.append((s, e, t))
        t += e - s
    return out


def to_out(spans: list[tuple[float, float, float]], s: float, first: int = 0, last: int | None = None) -> float | None:
    for src0, src1, o in spans[first:last]:
        if src0 - 0.02 <= s <= src1 + 0.02:
            return o + min(max(s, src0), src1) - src0
    return None


def caption_groups(words: list[dict], highlight: set[str]) -> list[dict]:
    """One to three words per caption, broken at punctuation; times are output times."""
    groups, cur = [], []
    def flush():
        if cur:
            groups.append(cur[:])
            cur.clear()
    for w in words:
        text = " ".join(shown(x["w"]) for x in cur + [w])
        if cur and (len(cur) >= 3 or len(text) > 14 or bare(w["w"]) in highlight):
            flush()
        cur.append(w)
        if w["w"][-1] in ".,?!;:" or bare(w["w"]) in highlight or w.get("join"):
            flush()
    flush()
    merged = []
    for g in groups:  # a lone small word ("THE", "YOU") joins the next caption
        if merged and len(merged[-1]) == 1 and bare(merged[-1][0]["w"]) in SMALL and not merged[-1][0].get("join"):
            merged[-1] = merged[-1] + g
        else:
            merged.append(g)
    groups = merged
    out = []
    for i, g in enumerate(groups):
        nxt = groups[i + 1][0]["t"] if i + 1 < len(groups) else g[-1]["t"] + 0.8
        out.append({"start": g[0]["t"], "end": min(nxt, g[-1]["t"] + 1.2),
                    "words": [{"w": shown(x["w"]), "t": round(x["t"], 3), "hot": bare(x["w"]) in highlight} for x in g]})
    return out


def hook_lines(words: list[dict], highlight: set[str]) -> list[dict]:
    """The hook, stacked a line at a time: up to three words a line, a new page every three lines or
    sentence, and each highlight word with the word before it on a line of its own, big and yellow."""
    lines, cur = [], []
    def flush(hot=False):
        if cur:
            lines.append({"hot": hot, "words": cur[:]})
            cur.clear()
    for k, w in enumerate(words):
        is_hot = bare(w["w"]) in highlight
        if is_hot:
            lead = cur.pop() if cur and bare(cur[-1]["w"]) in SMALL else None
            flush()
            cur.extend([lead, w] if lead else [w])
            flush(True)
            continue
        if cur and (len(cur) >= 3 or len(" ".join(shown(x["w"]) for x in cur + [w])) > 14):
            flush()
        cur.append(w)
        if w["w"][-1] in ".?!":
            flush()
            if lines:
                lines[-1]["end"] = True
    flush()
    out, page, n = [], 0, 0
    for line in lines:
        if n == 3:
            page, n = page + 1, 0
        out.append({"hot": line["hot"], "page": page,
                    "words": [{"w": shown(x["w"]), "t": round(x["t"], 3)} for x in line["words"]]})
        n += 1
        if line.get("end"):
            page, n = page + 1, 0
    return out


# ------------------------------------------------------------------- camera


def grade(img: np.ndarray, clahe) -> np.ndarray:
    """Lift a dim room: local contrast on lightness, a little colour, a little sharpness."""
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    out = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    hsv = cv2.cvtColor(out, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.14, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    soft = cv2.GaussianBlur(out, (0, 0), 1.6)
    return cv2.addWeighted(out, 1.55, soft, -0.55, 0)


def render_camera(video: pathlib.Path, spans, shots, fx, fy, face_h, sw, sh, out: pathlib.Path) -> None:
    clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(6, 6))
    sizes = {"room": float(sh), "wide": float(np.clip(face_h * 7.0, sh * 0.45, sh * 0.66)), "close": float(np.clip(face_h * 5.6, sh * 0.4, sh * 0.62)),
             "tight": float(np.clip(face_h * 3.8, sh * 0.3, sh * 0.46))}
    total = int(round((spans[-1][2] + spans[-1][1] - spans[-1][0]) * FPS))
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                            "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    size = sw * sh * 3
    written, img = 0, None
    for src0, src1, o in spans:
        f0, f1 = int(round(o * FPS)), int(round((o + src1 - src0) * FPS))
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{src0:.3f}", "-i", str(video), "-t", f"{src1 - src0 + 0.2:.3f}",
                                "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        for i in range(f0, f1):
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
            t = i / FPS
            s = src0 + (t - o)
            k = max(j for j, shot in enumerate(shots) if shot[0] <= t + 1e-6)
            t0, framing = shots[k]
            t1 = shots[k + 1][0] if k + 1 < len(shots) else total / FPS
            push = 1 - 0.06 * (t - t0) / max(0.1, t1 - t0)
            ch = sizes[framing] * push
            cw = ch * W / H
            top = {"tight": 0.30, "room": 0.5}.get(framing, 0.33)
            cx = float(np.clip(fx(s) - cw / 2, 0, sw - cw))
            cy = float(np.clip(fy(s) - ch * top, 0, sh - ch))
            crop = np.ascontiguousarray(frame[int(cy):int(cy + ch), int(cx):int(cx + cw)])
            img = cv2.resize(grade(crop, clahe), (W, H), interpolation=cv2.INTER_CUBIC)
            enc.stdin.write(img.tobytes())
            written += 1
        dec.kill()
        dec.wait()
    while written < total and img is not None:  # rounding: hold the last frame
        enc.stdin.write(img.tobytes())
        written += 1
    enc.stdin.close()
    if enc.wait():
        die("ffmpeg could not encode the camera track")


def render_voice(video: pathlib.Path, spans, out: pathlib.Path) -> np.ndarray:
    lo, hi = min(s for s, _, _ in spans), max(e for _, e, _ in spans)
    x = pcm(video, lo, hi + 0.1, SR, 2)
    fade = int(0.008 * SR)
    parts = []
    for s, e, _ in spans:
        seg = x[int((s - lo) * SR):int((e - lo) * SR)].copy()
        if len(seg) > 2 * fade:
            ramp = np.linspace(0, 1, fade)[:, None]
            seg[:fade] *= ramp
            seg[-fade:] *= ramp[::-1]
        parts.append(seg)
    voice = np.concatenate(parts)
    sfx.write_wav(out, voice)
    return voice


# --------------------------------------------------------------------- plan


def plan_shots(cut_points: list[float], stops: list[float], hot: list[float], drop: float, end: float) -> list[tuple[float, str]]:
    """Framings for the whole clip: a change at every join, sentence end and hot word, never more than MAX_SHOT apart."""
    cycle_hook, cycle_body = ["tight", "close"], ["close", "wide", "tight", "close", "tight", "wide"]
    marks = sorted(set([0.0, drop] + cut_points + stops + hot))
    times, last = [], -9.0
    for m in marks:
        if m in (0.0, drop) or (m - last >= MIN_SHOT and abs(m - drop) >= MIN_SHOT / 2):
            times.append(m)
            last = m
    filled = []
    for i, t in enumerate(times):
        filled.append(t)
        nxt = times[i + 1] if i + 1 < len(times) else end
        while nxt - filled[-1] > MAX_SHOT:
            gap = nxt - filled[-1]
            filled.append(filled[-1] + (gap / 2 if gap < 2 * MAX_SHOT else MAX_SHOT * 0.8))
    shots, hi, bi = [], 0, 0
    for t in sorted(set(round(x, 3) for x in filled)):
        if t < drop:
            shots.append((t, cycle_hook[hi % 2]))
            hi += 1
        else:
            shots.append((t, cycle_body[bi % len(cycle_body)]))
            bi += 1
    # One look at the room early in the body (it says "this was live"), held no more than 1.4 s.
    k = next((i for i, (t, _) in enumerate(shots) if t > drop + 1.0), None)
    if k is not None:
        t = shots[k][0]
        shots[k] = (t, "room")
        if k + 1 >= len(shots) or shots[k + 1][0] - t > 1.4:
            shots.insert(k + 1, (round(t + 1.3, 3), "close"))
    # The last shot matches the first, so the loop reads as a cut.
    shots[-1] = (shots[-1][0], shots[0][1])
    return shots


def render(event: pathlib.Path, talk: pathlib.Path, spec_path: pathlib.Path, only: str) -> None:
    spec = json.loads(spec_path.read_text())
    clip = next((c for c in spec["clips"] if c["id"] == only), None) or die(f"no clip {only!r} in {spec_path}")
    video = source(event, talk)
    sw, sh, _ = probe(video)
    a, b, words = body_words(event, talk, video, clip, spec_path, spec)
    highlight = {w.lower() for w in clip.get("highlight", [])}
    hk = clip.get("hook") or die("clip has no hook: name its first and last words")
    i0 = find_phrase(words, hk["from"])
    i1 = find_phrase(words, hk["to"], i0) + len(hk["to"].split()) - 1
    hs = first_pause(video, words[i0]["s"] - 0.45, words[i0]["s"] + 0.15, last=True) or words[i0]["s"] - 0.08
    he = first_pause(video, words[i1]["e"] - 0.35, words[i1]["e"] + 0.7) or words[i1]["e"] + 0.05

    hook_spans = keep_spans(loudness(video, hs, he), hs, he)
    body_spans, kept, joins_after = [], set(), set()
    ranges = keep_ranges(video, words, clip.get("keep"), a, b)
    # A keep entry marked "same sentence" continues the one before: its caption runs on across the join.
    glued = [isinstance(k, dict) and k.get("same sentence") or (isinstance(k, list) and "same sentence" in k[2:])
             for k in (clip.get("keep") or [None])]
    for n, (lo, hi, i, j) in enumerate(ranges):
        body_spans += keep_spans(loudness(video, lo, hi), lo, hi)
        kept.update(range(i, j + 1))
        if not (n + 1 < len(glued) and glued[n + 1]):
            joins_after.add(j)
    spans = timeline(hook_spans + body_spans)
    nh = len(hook_spans)
    drop = spans[nh][2]
    duration = spans[-1][2] + spans[-1][1] - spans[-1][0]

    hook_w = [dict(w, t=to_out(spans, w["s"], 0, nh)) for w in words[i0:i1 + 1]]
    hook_w = [w for w in hook_w if w["t"] is not None]
    # Only the kept words are captioned, and a caption never runs across a join.
    body_w = [dict(w, t=to_out(spans, w["s"], nh), join=k in joins_after) for k, w in enumerate(words) if k in kept]
    body_w = [w for w in body_w if w["t"] is not None]
    groups = caption_groups(body_w, highlight)
    lines = hook_lines(hook_w, highlight)

    joins = [o for _, _, o in spans[1:] if abs(o - drop) > 0.05]
    stops = [w["t"] + 0.05 for w in body_w if w["w"][-1] in ".?!"]
    hot_t = [w["t"] for w in body_w if bare(w["w"]) in highlight]
    shots = plan_shots(joins, stops, hot_t, drop, duration)

    out_dir = common.media_dir(event) / "shorts" / f"{talk.name}.{clip['id']}"
    (out_dir / "emoji").mkdir(parents=True, exist_ok=True)

    def at(phrase: str) -> float:
        k = find_phrase(words, phrase)
        t = to_out(spans, words[k]["s"], nh)
        return t if t is not None else die(f"{phrase!r} is not in the body")

    inserts = []
    for x in sorted(clip.get("inserts", []), key=lambda x: at(x["on"])):
        t = at(x["on"])
        dur = min(float(x.get("for", 1.8)), duration - 0.6 - t)
        if inserts and t < inserts[-1]["t"] + inserts[-1]["dur"] + 0.8:
            die(f"inserts at {x['on']!r} and the one before are less than 0.8 s apart")
        src = generate(x["image"], "full", out_dir / "gen")
        inserts.append({"t": round(t, 3), "dur": round(dur, 3), "src": f"gen/{src.name}"})
    tones = [{"t": round(at(x["on"]), 3), "dur": float(x.get("for", 1.4))} for x in clip.get("tones", [])]
    covered = lambda t, hold=0.0: any(i["t"] - 0.3 <= t + hold and t <= i["t"] + i["dur"] for i in inserts)

    stickers, last, used = [], -9.0, set()
    for w in body_w:
        val = clip.get("stickers", {}).get(bare(w["w"]))
        if not val or w["t"] - last < 0.4 or covered(w["t"] - 0.05) or json.dumps(val) in used:
            continue
        nxt = min([i["t"] for i in inserts if i["t"] > w["t"]] + [duration])
        hold = min(1.5, nxt - w["t"])
        if hold < 0.7:
            continue
        if isinstance(val, dict) and "logo" in val:
            src = f"logos/{logo(val['logo'], out_dir / 'logos').name}"
        elif isinstance(val, dict):
            src = f"gen/{generate(val['icon'], 'icon', out_dir / 'gen').name}"
        else:
            shutil.copy(emoji(val), out_dir / "emoji" / f"{val}.png")
            src = f"emoji/{val}.png"
        x = 380 + (len(stickers) % 3 - 1) * 230
        stickers.append({"t": round(w["t"] - 0.05, 3), "src": src, "x": x, "y": 220, "hold": round(hold, 3)})
        used.add(json.dumps(val))
        last = w["t"]
    pulses = [{"t": round(t, 3), "from": 1.07, "hold": 0.3} for t, _ in shots[1:] if abs(t - drop) > 0.05]
    pulses += [{"t": round(t, 3), "from": 1.16, "hold": 0.45} for t in hot_t
               if all(abs(t - p["t"]) > 0.35 for p in pulses)]
    pulses.sort(key=lambda p: p["t"])
    big_cuts = [t for t, f in shots if f in ("wide", "room") and t > drop + 0.5]
    flashes = [{"t": round(drop, 3), "peak": 0.95, "decay": 0.3}] + [{"t": round(t, 3), "peak": 0.5, "decay": 0.16} for t in big_cuts]
    plan = {"duration": round(duration, 3), "drop": round(drop, 3), "hook": {"lines": lines}, "groups": groups,
            "pulses": pulses, "shakes": [round(drop, 3)], "flashes": flashes,
            "leaks": [round(drop, 3)] + [round(t, 3) for t in big_cuts[1::2]], "stickers": stickers,
            "inserts": inserts, "tones": tones}
    shutil.copy(asset(MONTSERRAT), out_dir / "Montserrat-Italic.ttf")
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=1))
    page = (HERE / "short.html").read_text().replace("__DUR__", f"{duration:.3f}")
    (out_dir / "index.html").write_text(page.replace("/*PLAN*/null", json.dumps(plan).replace("</", "<\\/")))
    print(f"  {len(spans)} spans, {duration:.1f}s, drop at {drop:.2f}s, {len(shots)} shots, {len(groups)} captions, "
          f"{len(stickers)} stickers, {len(inserts)} cutaways, {len(tones)} tones")

    fxf, fyf, face_h = track(video, min(hs, a), max(he, b), sw, sh, clip.get("face"))
    render_camera(video, spans, shots, fxf, fyf, face_h, sw, sh, out_dir / "camera.mp4")
    voice = render_voice(video, spans, out_dir / "voice.wav")
    print("  camera and voice done; rendering the motion layer")

    r = subprocess.run(["npx", "-y", "hyperframes", "render", str(out_dir), "--output", str(out_dir / "visual.mp4"),
                        "--quality", "high", "--fps", str(FPS)], capture_output=True, text=True)
    if r.returncode or not (out_dir / "visual.mp4").is_file():
        die(f"hyperframes render failed:\n{(r.stdout + r.stderr)[-1500:]}")

    track_path, meta = music_track(clip.get("music", "getting-it-done"))
    body_cuts = [(t, f) for t, f in shots if t > drop + 0.3]
    events = {"riser": [drop], "boom": [drop], "ding": [drop],
              "whoosh": [t for t, _ in body_cuts if not covered(t)] + [i["t"] + i["dur"] for i in inserts],
              "whoosh_big": [drop - 0.26] + [i["t"] for i in inserts],
              "pop": [s["t"] for s in stickers],
              "hit": [p["t"] for p in pulses if p["from"] > 1.1]}
    final = common.media_dir(event) / "shorts" / f"{talk.name}.{clip['id']}.mp4"
    placed = sfx.mix(out_dir / "visual.mp4", voice, track_path, drop, duration, events, final, out_dir)
    (out_dir / "sounds.json").write_text(json.dumps(placed, indent=1))
    print("  sounds: " + ", ".join(f"{len(v)} {k}" for k, v in placed.items()))
    final.with_suffix(".srt").write_text("".join(
        f"{i}\n{ts(g['start'])} --> {ts(g['end'])}\n{' '.join(x['w'] for x in g['words']).capitalize()}\n\n"
        for i, g in enumerate(groups, 1)))
    print(f"  {final}\n  music: {meta.get('credit', meta.get('title'))}")


def ts(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def frames(event: pathlib.Path, talk: pathlib.Path, clip_id: str) -> None:
    """Eighteen frames of the finished clip on one sheet."""
    out = common.media_dir(event) / "shorts" / f"{talk.name}.{clip_id}.mp4"
    if not out.is_file():
        die(f"{out} does not exist: render it first")
    _, _, length = probe(out)
    sheet = out.with_suffix(".frames.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf",
                    f"fps={18 / length:.4f},scale=240:-1,tile=9x2", "-frames:v", "1", "-q:v", "3", str(sheet)], check=True)
    print(f"  {sheet}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("source", "words", "render", "frames"):
        s = sub.add_parser(name)
        s.add_argument("event")
        s.add_argument("talk")
        if name != "source":
            s.add_argument("--id", required=True, help="the clip's id in clips.json")
    args = p.parse_args()
    event = common.event_dir(args.event)
    talk = find_talk(event, args.talk)
    if args.cmd == "source":
        print(source(event, talk))
        return
    if args.cmd == "frames":
        frames(event, talk, args.id)
        return
    spec_path = talk / "clips.json"
    if not spec_path.is_file():
        die(f"{spec_path.relative_to(common.ROOT)} does not exist: write it first (see --help)")
    if args.cmd == "words":
        spec = json.loads(spec_path.read_text())
        clip = next((c for c in spec["clips"] if c["id"] == args.id), None) or die(f"no clip {args.id!r}")
        _, _, words = body_words(event, talk, source(event, talk), clip, spec_path, spec)
        line, out = [], []
        for w in words:
            if not line:
                line.append(f"[{hm(w['s'])}.{int(w['s'] % 1 * 10)}]")
            line.append(w["w"])
            if w["w"][-1] in ".?!":
                out.append(" ".join(line))
                line = []
        print("\n".join(out + ([" ".join(line)] if line else [])))
        return
    render(event, talk, spec_path, args.id)


if __name__ == "__main__":
    main()
