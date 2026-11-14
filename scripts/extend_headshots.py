# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==11.3.0", "pillow-heif==1.1.0", "numpy==2.2.6"]
# ///
"""Extend speaker headshots that are too tight to fill their tile.

    uv run scripts/extend_headshots.py ../website/apps/branding/public/assets/speakers/<slug>.jpg …
    uv run scripts/speaker_masks.py   ../website/apps/branding/public/assets/speakers/<slug>.jpg …

The website frames every speaker by their face (website
apps/site/src/speaker-framing.json, faces from speaker_masks.py). A photo
cropped close around the face would then end inside the tile. This places it
on a larger canvas and has an image model (OpenRouter, MODEL) paint only the
new area: shoulders, clothing, background. The model's image is lined up
with the original (it may shift it a little) and the original pasted back
over it, so the person stays exactly as photographed; an answer that leaves
grey unfilled or won't line up is asked for again. The unextended web copy is kept as
$AGNTENG_MEDIA/speakers/<slug>.jpg and every later run extends from it; the
result goes through photos.web like any headshot. Re-run speaker_masks.py
afterwards: the face moved within the larger photo.
"""

import argparse
import base64
import hashlib
import io
import json
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import photos
from common import MEDIA_ROOT, ROOT, die, openrouter_key

MODEL = "google/gemini-3-pro-image"
FRAMING = json.loads((ROOT.parent / "website" / "apps" / "site" / "src" / "speaker-framing.json").read_text())
MARGIN = 0.04  # of the tile, so rounding never leaves a sliver
MIN_BOTTOM = 0.12  # of the photo's height: a thin strip gives the model too little room to continue the body
SEAM = 14  # px the pasted-back original is inset from each extended edge
TRIES = 3
PROMPT = (
    "This is a photo of a person placed on a larger canvas; the flat grey areas around it are empty. "
    "Outpaint: fill ONLY the grey areas so the photo continues naturally: extend the person's shoulders, "
    "torso and clothing downward and the same background around them, matching lighting, focus and colour. "
    "The person's body and clothing must continue all the way to the bottom edge, with no gap or cut line. "
    "Do not change the existing photo or the face, and add no text, frame or border. "
    "Return the full image at the same framing."
)


def needed(size: tuple[int, int], face: list[float]) -> tuple[int, int, int, int]:
    """Pixels to add on top, bottom, left and right so the photo covers its tile."""
    (w, h), (cx, cy, fh) = size, face
    k = h * fh / FRAMING["face"]  # photo px per tile height
    half = FRAMING["tile"] * k / 2 + MARGIN * k
    edges = (FRAMING["at"] * k + MARGIN * k - cy * h, cy * h + (1 - FRAMING["at"] + MARGIN) * k - h,
             half - cx * w, cx * w + half - w)
    t, b, l, r = (max(0, round(e)) for e in edges)
    return t, (max(b, round(MIN_BOTTOM * h)) if b else 0), l, r


def ask(canvas: Image.Image) -> Image.Image:
    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    body = {"model": MODEL, "modalities": ["image", "text"], "messages": [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}}]}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {openrouter_key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        images = json.load(resp)["choices"][0]["message"].get("images") or []
    if not images:
        raise ValueError("no image in the answer")
    data = base64.b64decode(images[0]["image_url"]["url"].split(",", 1)[1])
    return Image.open(io.BytesIO(data)).convert("RGB").resize(canvas.size, Image.LANCZOS)


def offset(a: np.ndarray, b: np.ndarray) -> tuple[int, int]:
    """How far a is shifted from b (rows, columns), by phase correlation."""
    f = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    peak = np.unravel_index(np.argmax(np.abs(np.fft.ifft2(f / (np.abs(f) + 1e-9)))), a.shape)
    return tuple(int(p - n if p > n // 2 else p) for p, n in zip(peak, a.shape))


def outpaint(img: Image.Image, t: int, b: int, l: int, r: int) -> Image.Image:
    w, h = img.size
    canvas = Image.new("RGB", (w + l + r, h + t + b), (128, 128, 128))
    canvas.paste(img, (l, t))
    new = np.ones(canvas.size[::-1], bool)
    new[t:t + h, l:l + w] = False
    for _ in range(TRIES):
        try:
            out = ask(canvas)
        except urllib.error.HTTPError as e:
            if e.code in (401, 402, 403):
                die(f"OpenRouter refused the request (HTTP {e.code}); check the key and credits")
            print(f"  HTTP {e.code}; asking again")
            continue
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as e:
            print(f"  no usable answer ({type(e).__name__}); asking again")
            continue
        px = np.asarray(out, np.int16)
        if (np.abs(px - 128).max(axis=2) < 6)[new].mean() > 0.02:
            print("  grey left unfilled; asking again")
            continue
        # Line the model's image up with the original, then paste the original back.
        dy, dx = offset(np.asarray(img.convert("L"), float), np.asarray(out.convert("L"), float)[t:t + h, l:l + w])
        if abs(dy) > h / 10 or abs(dx) > w / 10:
            print(f"  shifted {dy, dx} px; asking again")
            continue
        # Shift by edge replication, so no black border comes in from outside the image.
        out = Image.fromarray(np.roll(np.pad(px.astype(np.uint8), ((abs(dy),) * 2, (abs(dx),) * 2, (0, 0)), mode="edge"), (dy, dx), (0, 1))[abs(dy):abs(dy) + out.height, abs(dx):abs(dx) + out.width])
        keep = Image.new("L", canvas.size, 0)
        keep.paste(255, (l + (SEAM if l else 0), t + (SEAM if t else 0), l + w - (SEAM if r else 0), t + h - (SEAM if b else 0)))
        out.paste(canvas, (0, 0), keep.filter(ImageFilter.GaussianBlur(SEAM / 3)))
        return out
    die(f"{MODEL}: no usable image after {TRIES} tries")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("headshots", nargs="+", type=Path)
    args = ap.parse_args()
    if MEDIA_ROOT is None:
        die("no media folder: set AGNTENG_MEDIA, or run `mise run bootstrap` in the workspace")
    sources = json.loads((args.headshots[0].parent.parent / "speaker-masks" / "sources.json").read_text())
    for src in args.headshots:
        kept = MEDIA_ROOT / "speakers" / src.name
        if not kept.exists():
            kept.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, kept)
        if hashlib.sha256(src.read_bytes()).digest() != hashlib.sha256(kept.read_bytes()).digest():
            print(f"{src.name}: already extended (to redo, copy {kept} back and re-run speaker_masks.py first)")
            continue
        img = Image.open(kept).convert("RGB")
        entry = sources.get(src.name) or {}
        if entry.get("size") != list(img.size):
            die(f"{src.name}: sources.json is out of date; run speaker_masks.py first")
        if not entry.get("face"):
            print(f"{src.name}: no face found; left as is")
            continue
        pad = needed(img.size, entry["face"])
        if not any(pad):
            print(f"{src.name}: already fills its tile")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "extended.png"
            outpaint(img, *pad).save(raw)
            photos.web(raw, src, do_enhance=False, max_edge=800)
        print(f"{src.name}: +{pad} px (top, bottom, left, right)")


if __name__ == "__main__":
    main()
