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
                "keep": [["Every time", "the decision."], {"from": "So we", "to": "the code.", "skip": ["like"]}],
                "highlight": ["weird decisions", "context"],
                "stickers": {"agent": "1f916", "context": {"icon": "a stack of glowing documents"}},
                "inserts": [{"on": "Every time", "for": 1.8, "image": "a scene"}],
                "tones": [{"on": "Back then", "for": 1.3}]}]}

`start`/`end` (from 0:00 of the talk) is the span the clip is cut from;
`hook`, `keep`, `highlight`, `stickers`, `inserts`, `tones` and `music` are
described in the talk-clip skill. `words` prints the timed words to choose
them from; `text` prints what the viewer reads.

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
import grammar
import sfx
from common import die, hm, parse_ts
from talk_transcript import NOISE, SEG, tidy

HERE = pathlib.Path(__file__).resolve().parent
W, H, FPS, SR = 1080, 1920, 30, 48000
SNAP = 1.5
CHUNK = 4
HOP = 0.02
CACHE = pathlib.Path.home() / ".cache" / "agnteng"
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
MUSIC_DEFAULT = "fs-352409"  # CC0 trap beat with deep bass
SIMPLE_ICONS = "16.30.0"  # CC0 brand marks; a product named on stage pops in as its logo
GAP_MAX, GAP_KEEP = 0.28, 0.10   # pauses longer than this shrink to this
MIN_SHOT, MAX_SHOT = 1.4, 3.0    # seconds between framing changes
END, PRESS = 2.6, 0.75           # the end card's length, and when on it the like button is pressed
LOGOS = common.ROOT.parent / "website" / "apps" / "branding" / "public" / "assets" / "logo"
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
        i = next(k for k, w in enumerate(words) if w["e"] > a + 0.05)
        j = max(k for k, w in enumerate(words) if w["s"] < b - 0.05)
        return [(edge_before(video, words, i), edge_after(video, words, j), i, j, False)]
    out, after = [], 0
    for k in keep:
        if isinstance(k, dict):
            first, last, glue, skip = k["from"], k["to"], bool(k.get("same sentence")), k.get("skip", [])
        else:
            first, last, glue, skip = k[0], k[1], "same sentence" in k[2:], []
        i = find_phrase(words, first, after)
        j = find_phrase(words, last, i) + len(last.split()) - 1
        # `skip`: words dropped from inside the phrase ("What can be go wrong" without "be"), in order.
        gone, at = set(), i
        for word in skip:
            g = find_phrase(words, word, at)
            if g > j:
                die(f"skip {word!r} is not inside {first!r} … {last!r}")
            gone.update(range(g, g + len(word.split())))
            at = g + len(word.split())
        start, first_part = None, True
        for n in range(i, j + 2):
            if n <= j and n not in gone:
                start = n if start is None else start
            elif start is not None:
                # Only the first part keeps the entry's own glue; the parts after a skipped word continue it.
                out.append((edge_before(video, words, start), edge_after(video, words, n - 1), start, n - 1,
                            glue if first_part else True))
                start, first_part = None, False
        after = j + 1
    return out


def edge_before(video: pathlib.Path, words: list[dict], i: int) -> float:
    """Where to cut in before word i: the quietest instant between the previous word and this one, never
    inside either, so a clip or a join never opens on half a word."""
    s = words[i]["s"]
    prev_e = words[i].get("pe", words[i - 1]["e"] if i else s - 0.4)
    lo = max(prev_e + 0.02, s - 0.3)
    return quietest(video, lo, s - 0.02) if s - 0.02 - lo > 0.03 else max(lo, s - 0.03)


def edge_after(video: pathlib.Path, words: list[dict], j: int) -> float:
    """Where to cut out after word j: past its decay (the aligner ends a word on its last letter, a little
    before the sound dies away), on the quietest instant before the next word."""
    e = words[j]["e"]
    nxt = words[j].get("ns", words[j + 1]["s"] if j + 1 < len(words) else e + 0.5)
    lo, hi = e + 0.08, min(nxt - 0.02, e + 0.4)
    return quietest(video, lo, hi) if hi - lo > 0.03 else max(e + 0.03, min(hi, (e + nxt) / 2))


def gap_spans(ws: list[dict], lo: float, hi: float) -> list[tuple[float, float]]:
    """[lo, hi] without its long pauses, judged by the gaps between aligned words rather than by loudness, so a
    quietly spoken word is never taken for silence: a gap over GAP_MAX shrinks to about GAP_KEEP, with a little
    air kept after the last word and before the next."""
    spans, cur = [], lo
    for prev, nxt in zip(ws, ws[1:]):
        if nxt["s"] - prev["e"] > GAP_MAX:
            spans.append((cur, prev["e"] + 0.1))
            cur = nxt["s"] - 0.06
    spans.append((cur, hi))
    return [(a, b) for a, b in spans if b - a > 0.05]


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
    cut = clip.get("cut")
    if not cut or abs(cut[0] - parse_ts(clip["start"])) > SNAP or abs(cut[1] - parse_ts(clip["end"])) > SNAP:
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
    if (not kept or abs(kept[0]["start"] - a) > 0.05 or kept[-1]["end"] < b - 0.5
            or any("TRANSCRIPTION FAILED" in c["text"] for c in kept)):
        subprocess.run([sys.executable, str(HERE / "transcribe_chunks.py"), str(audio), "--out", str(words_file),
                        "--seconds", str(CHUNK), "--start", f"{a:.2f}", "--end", f"{b:.2f}"],
                       check=True, stdout=subprocess.DEVNULL)
    chunks = json.loads(words_file.read_text())
    span_end = max(b, max(c["end"] for c in chunks))
    # Every word up to the end of the transcribed span: the words after the cut tell where the last one ends.
    return a, b, timed_words(video, chunks, a, span_end)


def timed_words(video: pathlib.Path, chunks: list[dict], a: float, b: float) -> list[dict]:
    """The tidied transcript's words, timed by forced alignment (ADR 0006) of the raw transcript, so fillers and
    repeats keep their own time. Each word carries `pe`/`ns` (end of the spoken word before, start of the one
    after) so a cut never lands inside an uncaptioned word. Falls back to `word_times` if alignment fails."""
    import difflib
    said = [" ".join(NOISE.sub("", SEG.sub("", c["text"])).split()) for c in chunks]
    texts = [w for t in said for w in tidy(t).split() if not re.fullmatch(r"\w{1,3}-[,.]?", w)]
    raw = [w for t in said for w in re.sub(r"\[[^\]]*\]", " ", t).split() if re.search(r"[A-Za-z0-9]", w)]
    try:
        spans = align.align(pcm(video, a, b), raw)
        if sum(sp is not None for sp in spans) < len(raw) / 2:
            raise ValueError(f"placed {sum(sp is not None for sp in spans)} of {len(raw)} words")
    except Exception as e:  # noqa: BLE001 - the estimate is a usable fallback
        print(f"  forced alignment failed ({e}); estimating word times", file=sys.stderr)
        return word_times(chunks, a, loudness(video, a, b))
    timed = [(a + sp[0], a + sp[1]) if sp else None for sp in spans]
    for i, sp in enumerate(timed):  # a raw word with no letters to align sits between its neighbours
        if sp is None:
            prev = next((x[1] for x in reversed(timed[:i]) if x), a)
            nxt = next((x[0] for x in timed[i + 1:] if x), b)
            timed[i] = (prev, max(prev + 0.05, nxt))
    match = {}
    sm = difflib.SequenceMatcher(None, [bare(w) for w in raw], [bare(w) for w in texts], autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            match[blk.b + k] = blk.a + k
    out = []
    for n, w in enumerate(texts):
        r = match.get(n)
        if r is None:  # tidying changed the word: place it after the last placed one
            prev = out[-1] if out else None
            s0 = prev["e"] if prev else a
            out.append({"w": w, "s": s0, "e": s0 + 0.05, "pe": s0, "ns": s0 + 0.05})
            continue
        out.append({"w": w, "s": timed[r][0], "e": timed[r][1],
                    "pe": timed[r - 1][1] if r > 0 else timed[r][0] - 0.4,
                    "ns": timed[r + 1][0] if r + 1 < len(timed) else timed[r][1] + 0.5})
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
    xs, ys, hs, lost = [], [], [], 0
    for f in frames:
        _, faces = det.detect(f)
        pick = None
        if faces is not None and len(faces):
            cands = [(x + w / 2, y + h / 2, h) for x, y, w, h in faces[:, :4] if y + h < dh * 0.85]
            if cands:
                if prev:
                    near = min(cands, key=lambda c: (c[0] - prev[0]) ** 2 + (c[1] - prev[1]) ** 2)
                    pick = near if abs(near[0] - prev[0]) < dw * 0.2 else None
                    lost = 0 if pick else lost + 1
                if not prev or (lost * step >= 1.0 and not hint):  # first sight, or the speaker moved: the biggest face
                    pick, lost = max(cands, key=lambda c: c[2]), 0
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


def written(clip: dict, spec_path: pathlib.Path, spec: dict, hook_w: list[dict], body_w: list[dict]):
    """What the captions show: each sentence corrected for grammar and currency (ADR 0007), word by word, while
    every word keeps the time it was said. Corrections are kept in clips.json under `grammar` (as said → as
    written), so they are visible and the same on every render; delete an entry to ask again."""
    units, cur = [hook_w], []
    for w in body_w:
        cur.append(w)
        if w.get("join"):
            units.append(cur)
            cur = []
    if cur:
        units.append(cur)
    units = [u for u in units if u]
    said = [" ".join(w["w"] for w in u) for u in units]
    cache = clip.setdefault("grammar", {})
    missing = list(dict.fromkeys(x for x in said if x not in cache))
    if missing:
        fixed, refused = grammar.correct(missing)
        cache.update(zip(missing, fixed))
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n")
        for old, new in refused:
            print(f"  grammar: refused a rewrite, kept as said: {old}", file=sys.stderr)
    for u, line in zip(units, said):
        import difflib
        a, b = [w["w"] for w in u], cache[line].split()
        for w in u:
            w["d"] = w["w"]
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if op == "replace":
                n, m = i2 - i1, j2 - j1
                for k in range(n):
                    u[i1 + k]["d"] = (b[j1 + k] if k < n - 1 else " ".join(b[j1 + k:j2])) if k < m else ""
            elif op == "delete":
                for k in range(i1, i2):
                    u[k]["d"] = ""
            elif op == "insert":
                extra = " ".join(b[j1:j2])
                if i1 > 0:
                    u[i1 - 1]["d"] = (u[i1 - 1]["d"] + " " + extra).strip()
                else:
                    u[0]["d"] = extra + " " + u[0]["d"]
    def visible(ws):
        out = []
        for w in ws:
            if w["d"]:
                out.append(w)
            elif w.get("join") and out:
                out[-1] = dict(out[-1], join=True)
        return out
    return visible(hook_w), visible(body_w)


def mark_hot(words: list[dict], entries: list[str]) -> None:
    """Give each emphasised phrase an id (`ph`) on its words. An entry is a word or a phrase: a modifier is
    emphasised with the noun it modifies ("main thing", not "main"). A number always is, with the word after
    it unless that is a small word: "47 tools", "55%"."""
    for w in words:
        w["ph"] = None
    pid = 0
    for entry in entries:
        toks = [bare(t) for t in entry.split()]
        for i in range(len(words) - len(toks) + 1):
            if [bare(words[i + k]["w"]) for k in range(len(toks))] == toks and all(words[i + k]["ph"] is None for k in range(len(toks))):
                for k in range(len(toks)):
                    words[i + k]["ph"] = pid
                pid += 1
    for i, w in enumerate(words):
        if w["ph"] is None and any(ch.isdigit() for ch in w["w"]):
            w["ph"] = pid
            if i + 1 < len(words) and words[i + 1]["ph"] is None and bare(words[i + 1]["w"]) not in SMALL and w["w"][-1] not in ".,?!;:":
                words[i + 1]["ph"] = pid
            pid += 1


def caption_groups(words: list[dict]) -> list[dict]:
    """One to three words per caption, broken at punctuation; an emphasised phrase is one caption of its own,
    never split. Times are output times."""
    groups, cur = [], []
    def flush():
        if cur:
            groups.append(cur[:])
            cur.clear()
    for n, w in enumerate(words):
        text = " ".join(shown(x.get("d", x["w"])) for x in cur + [w])
        ph = w.get("ph")
        inside = cur and ph is not None and cur[-1].get("ph") == ph
        if cur and not inside and (len(cur) >= 3 or len(text) > 14 or ph is not None or cur[-1].get("ph") is not None):
            flush()
        cur.append(w)
        ends_phrase = ph is not None and (n + 1 == len(words) or words[n + 1].get("ph") != ph)
        if ends_phrase or w.get("join") or (w["w"][-1] in ".,?!;:" and ph is None):
            flush()
    flush()
    merged = []
    for g in groups:  # a lone small word ("THE", "YOU") joins the next caption, within its sentence
        lone = merged[-1][0] if merged and len(merged[-1]) == 1 else None
        if (lone and bare(lone["w"]) in SMALL and not lone.get("join") and lone.get("ph") is None
                and lone["w"][-1] not in ".,?!;:" and len(g) < 3):
            merged[-1] = merged[-1] + g
        else:
            merged.append(g)
    groups = merged
    out = []
    for i, g in enumerate(groups):
        nxt = groups[i + 1][0]["t"] if i + 1 < len(groups) else g[-1]["t"] + 0.8
        out.append({"start": g[0]["t"], "end": min(nxt, g[-1]["t"] + 1.2),
                    "said": " ".join(x.get("d", x["w"]) for x in g),
                    "words": [{"w": shown(x.get("d", x["w"])), "t": round(x["t"], 3), "hot": x.get("ph") is not None} for x in g]})
    return out


def hook_lines(words: list[dict]) -> list[dict]:
    """The hook, stacked a line at a time: up to three words a line, a new page every three lines or
    sentence, and each highlight word with the word before it on a line of its own, big and yellow."""
    lines, cur = [], []
    def flush(hot=False):
        if cur:
            lines.append({"hot": hot, "words": cur[:]})
            cur.clear()
    k = 0
    while k < len(words):
        w = words[k]
        if w.get("ph") is not None:  # the whole phrase, with a small word before it, on a line of its own
            lead = cur.pop() if cur and bare(cur[-1]["w"]) in SMALL else None
            flush()
            phrase = [x for x in words[k:] if x.get("ph") == w["ph"]]
            cur.extend(([lead] if lead else []) + phrase)
            flush(True)
            k += len(phrase)
            continue
        if cur and (len(cur) >= 3 or len(" ".join(shown(x.get("d", x["w"])) for x in cur + [w])) > 14):
            flush()
        cur.append(w)
        if w["w"][-1] in ".?!":
            flush()
            if lines:
                lines[-1]["end"] = True
        k += 1
    flush()
    out, page, n = [], 0, 0
    for line in lines:
        if n == 3:
            page, n = page + 1, 0
        out.append({"hot": line["hot"], "page": page,
                    "words": [{"w": shown(x.get("d", x["w"])), "t": round(x["t"], 3)} for x in line["words"]]})
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
    """Framings for the whole clip: a change at every join (none closer than MIN_SHOT / 2), and at sentence ends
    and hot words at least MIN_SHOT from any other; never more than MAX_SHOT apart."""
    cycle_hook, cycle_body = ["tight", "close"], ["close", "wide", "tight", "close", "tight", "wide"]
    times = [0.0, drop]
    for m in sorted(cut_points):  # a join is hidden by a new framing, unless that would leave a sliver of a shot
        if all(abs(m - t) >= MIN_SHOT / 2 for t in times):
            times.append(m)
    for m in sorted(set(stops + hot)):
        if all(abs(m - t) >= MIN_SHOT for t in times) and abs(m - drop) >= MIN_SHOT / 2:
            times.append(m)
    times.sort()
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
        if k + 1 >= len(shots) or shots[k + 1][0] - t > 1.3 + MIN_SHOT / 2:
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
    mark_hot(words, clip.get("highlight", []))
    hk = clip.get("hook") or die("clip has no hook: name its first and last words")
    # The hook may skip words too.
    hook_keep = [{"from": hk["from"], "to": hk["to"], "skip": hk.get("skip", [])}]
    hook_ranges = keep_ranges(video, words, hook_keep, a, b)
    hook_idx = {n for _, _, i, j, _ in hook_ranges for n in range(i, j + 1)}
    hs, he = min(r[0] for r in hook_ranges), max(r[1] for r in hook_ranges)
    hook_spans = [sp for lo, hi, i, j, _ in hook_ranges for sp in gap_spans(words[i:j + 1], lo, hi)]
    body_spans, kept, joins_after = [], set(), set()
    ranges = keep_ranges(video, words, clip.get("keep"), a, b)
    # A range that continues the sentence before it ("same sentence", or the rest of a phrase after a
    # skipped word) lets its caption run on across the join.
    for n, (lo, hi, i, j, _) in enumerate(ranges):
        body_spans += gap_spans(words[i:j + 1], lo, hi)
        kept.update(range(i, j + 1))
        if not (n + 1 < len(ranges) and ranges[n + 1][4]):
            joins_after.add(j)
    spans = timeline(hook_spans + body_spans)
    nh = len(hook_spans)
    drop = spans[nh][2]
    duration = spans[-1][2] + spans[-1][1] - spans[-1][0]

    hook_w = [dict(w, t=to_out(spans, w["s"], 0, nh)) for n, w in enumerate(words) if n in hook_idx]
    hook_w = [w for w in hook_w if w["t"] is not None]
    # Only the kept words are captioned, and a caption never runs across a join.
    body_w = [dict(w, t=to_out(spans, w["s"], nh), join=k in joins_after) for k, w in enumerate(words) if k in kept]
    body_w = [w for w in body_w if w["t"] is not None]
    hook_w, body_w = written(clip, spec_path, spec, hook_w, body_w)
    groups = caption_groups(body_w)
    lines = hook_lines(hook_w)

    joins = [o for _, _, o in spans[1:] if abs(o - drop) > 0.05]
    stops = [w["t"] + 0.05 for w in body_w if w["w"][-1] in ".?!"]
    hot_t = [w["t"] for n, w in enumerate(body_w) if w.get("ph") is not None and (n == 0 or body_w[n - 1].get("ph") != w["ph"])]
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
    plan = {"duration": round(duration + END, 3), "drop": round(drop, 3), "hook": {"lines": lines}, "groups": groups,
            "pulses": pulses, "shakes": [round(drop, 3)], "flashes": flashes,
            "leaks": [round(drop, 3)] + [round(t, 3) for t in big_cuts[1::2]], "stickers": stickers,
            "inserts": inserts, "tones": tones, "end": {"t": round(duration, 3), "dur": END, "press": PRESS}}
    camera_length, duration = duration, duration + END  # the end card plays after the last word
    shutil.copy(asset(MONTSERRAT), out_dir / "Montserrat-Italic.ttf")
    shutil.copy(LOGOS / "ae-mark-white.svg", out_dir / "mark.svg")
    shutil.copy(LOGOS / "ae-wordmark-line-white.svg", out_dir / "wordline.svg")
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=1))
    page = (HERE / "short.html").read_text().replace("__DUR__", f"{duration:.3f}").replace("__CAM__", f"{camera_length:.3f}")
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

    track_path, meta = music_track(clip.get("music", MUSIC_DEFAULT))
    # Effects mark real changes: the drop, cutaways in and out, the room and the wide shots, stickers and the
    # first punch-ins on key phrases. Ordinary reframes are silent.
    big = [t for t, f in shots if t > drop + 0.3 and f in ("wide", "room") and not covered(t)]
    events = {"riser": [drop], "boom": [drop], "ding": [drop],
              "whoosh": big + [i["t"] + i["dur"] for i in inserts],
              "whoosh_big": [i["t"] for i in inserts],
              "pop": [s["t"] for s in stickers],
              "hit": [p["t"] for p in pulses if p["from"] > 1.1][:3]}
    # The end card: in on a whoosh, and the like button rings when it is pressed.
    events["whoosh_big"].append(camera_length)
    events["ding"].append(camera_length + PRESS)
    final = common.media_dir(event) / "shorts" / f"{talk.name}.{clip['id']}.mp4"
    placed = sfx.mix(out_dir / "visual.mp4", voice, track_path, drop, duration, events, final, out_dir)
    (out_dir / "sounds.json").write_text(json.dumps(placed, indent=1))
    print("  sounds: " + ", ".join(f"{len(v)} {k}" for k, v in placed.items()))
    cues = [(0.0, drop, " ".join(w.get("d", w["w"]) for w in hook_w))] + [(g["start"], g["end"], g["said"]) for g in groups]
    cues = [(s0, s1, t[:1].upper() + t[1:] if i == 0 or cues[i - 1][2][-1:] in ".?!" or i == 1 else t)
            for i, (s0, s1, t) in enumerate(cues)]
    final.with_suffix(".srt").write_text("".join(
        f"{i}\n{ts(s0)} --> {ts(s1)}\n{text}\n\n" for i, (s0, s1, text) in enumerate(cues, 1)))
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
    for name in ("source", "words", "text", "render", "remix", "frames"):
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
    if args.cmd == "remix":  # new music on a rendered clip: the visuals, voice and effects stay
        spec = json.loads(spec_path.read_text())
        clip = next((c for c in spec["clips"] if c["id"] == args.id), None) or die(f"no clip {args.id!r}")
        out_dir = common.media_dir(event) / "shorts" / f"{talk.name}.{clip['id']}"
        plan = json.loads((out_dir / "plan.json").read_text())
        track_path, meta = music_track(clip.get("music", MUSIC_DEFAULT))
        final = common.media_dir(event) / "shorts" / f"{talk.name}.{clip['id']}.mp4"
        sfx.mix(out_dir / "visual.mp4", sfx.read_audio(out_dir / "voice.wav"), track_path, plan["drop"], plan["duration"],
                json.loads((out_dir / "sounds.json").read_text()), final, out_dir)
        print(f"  {final}\n  music: {meta.get('credit', meta.get('title'))}")
        return
    if args.cmd == "text":
        spec = json.loads(spec_path.read_text())
        clip = next((c for c in spec["clips"] if c["id"] == args.id), None) or die(f"no clip {args.id!r}")
        video = source(event, talk)
        a, b, words = body_words(event, talk, video, clip, spec_path, spec)
        hk = clip.get("hook")
        if hk:
            hook_keep = [{"from": hk["from"], "to": hk["to"], "skip": hk.get("skip", [])}]
            print("HOOK  " + " … ".join(" ".join(w["w"] for w in words[i:j + 1])
                                        for _, _, i, j, _ in keep_ranges(video, words, hook_keep, a, b)))
        body = []
        for lo, hi, i, j, glue in keep_ranges(video, words, clip.get("keep"), a, b):
            part = " ".join(w["w"] for w in words[i:j + 1])
            body.append(("… " if glue else "\n") + part)
        print("BODY" + "".join(body).replace("\n", "\n  ", 1).replace("\n", "\n  "))
        return
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
