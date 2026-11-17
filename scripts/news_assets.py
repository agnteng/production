# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==12.3.0", "numpy==2.3.5", "rembg==2.0.86", "onnxruntime==1.31.1"]
# ///
"""Pictures for a news Short, in the brand's treatment.

    mise exec -- uv run scripts/news_assets.py person <dir> <name> <photo>        cut-out in brand duotone + silhouette
    mise exec -- uv run scripts/news_assets.py photo  <dir> <name> <photo> [fx fy zoom]   9:16, brand duotone
    mise exec -- uv run scripts/news_assets.py raw    <dir> <name> <photo> [fx fy zoom]   9:16, colours kept
    mise exec -- uv run scripts/news_assets.py generate <dir> <name> "<scene>"            a realistic news photo

`person` writes `<dir>/people/<name>.png` (navy to white) and `<name>-sil.png`; the others write `<dir>/<name>.jpg`
(`generate` writes `<name>.png`, then crop it with `raw`). fx, fy (0..1) centre the 9:16 crop; zoom crops tighter.
Every picture must read on its own (house rules): check the crop shows what it is about. Generated pictures follow
captions.PHOTO_STYLE: a realistic news photo of a real, ordinary place or object, no people, no tag on screen.
"""
from __future__ import annotations

import base64
import json
import pathlib
import sys
import urllib.request

import numpy as np
from PIL import Image

import captions
import common
from common import die

NAVY, BLUE, WHITE = np.array([5, 7, 30]), np.array([30, 43, 230]), np.array([244, 245, 255])
IMAGE_MODEL = "google/gemini-3-pro-image"


def crop916(im: Image.Image, fx: float = 0.5, fy: float = 0.5, zoom: float = 1.0) -> Image.Image:
    h = im.height / zoom
    w = h * 9 / 16
    if w > im.width:
        w = im.width / zoom
        h = w * 16 / 9
    x0 = min(max(0, im.width * fx - w / 2), im.width - w)
    y0 = min(max(0, im.height * fy - h / 2), im.height - h)
    return im.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((1080, 1920), Image.LANCZOS)


def person(d: pathlib.Path, name: str, src: pathlib.Path) -> None:
    from rembg import new_session, remove
    rgb = Image.open(src).convert("RGB")
    if rgb.height > 2200:
        rgb = rgb.resize((round(rgb.width * 2200 / rgb.height), 2200), Image.LANCZOS)
    cut = remove(rgb, session=new_session("birefnet-portrait"))
    alpha = np.asarray(cut)[:, :, 3]
    cut = cut.crop(Image.fromarray(alpha).point(lambda v: 255 if v > 24 else 0).getbbox())
    rgbf = np.asarray(cut.convert("RGB")).astype(np.float32) / 255
    al = np.asarray(cut)[:, :, 3]
    lum = rgbf @ np.array([0.299, 0.587, 0.114])
    lo, hi = np.percentile(lum[al > 128], [3, 98])
    t = (np.clip((lum - lo) / (hi - lo), 0, 1) ** 0.9)[..., None]
    mid = NAVY + (BLUE - NAVY) * 0.18
    col = np.where(t < 0.45, NAVY + (mid - NAVY) * (t / 0.45), mid + (WHITE - mid) * ((t - 0.45) / 0.55))
    (d / "people").mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([np.clip(col, 0, 255).astype(np.uint8), al]), "RGBA").save(d / "people" / f"{name}.png")
    sil = np.zeros((*al.shape, 4), np.uint8)
    sil[..., :3], sil[..., 3] = NAVY, al
    Image.fromarray(sil, "RGBA").save(d / "people" / f"{name}-sil.png")


def photo(d: pathlib.Path, name: str, src: pathlib.Path, fx: float, fy: float, zoom: float, duotone: bool) -> None:
    im = crop916(Image.open(src).convert("RGB"), fx, fy, zoom)
    if duotone:
        lum = np.asarray(im).astype(np.float32) / 255 @ np.array([0.299, 0.587, 0.114])
        lo, hi = np.percentile(lum, [2, 99])
        t = np.clip((lum - lo) / (hi - lo), 0, 1)[..., None]
        col = np.where(t < 0.5, NAVY + (BLUE - NAVY) * (t / 0.5), BLUE + (WHITE - BLUE) * ((t - 0.5) / 0.5))
        im = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))
    im.save(d / f"{name}.jpg", quality=92)


def generate(d: pathlib.Path, name: str, scene: str) -> None:
    body = {"model": IMAGE_MODEL, "modalities": ["image", "text"], "image_config": {"aspect_ratio": "9:16"},
            "messages": [{"role": "user", "content": f"{captions.picture_prompt(scene)}. {captions.PHOTO_STYLE}"}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {common.openrouter_key()}", "Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    images = r["choices"][0]["message"].get("images") or die(f"{IMAGE_MODEL} returned no image for {scene!r}")
    (d / f"{name}.png").write_bytes(base64.b64decode(images[0]["image_url"]["url"].split(",", 1)[1]))


def main() -> None:
    if len(sys.argv) < 5:
        die(__doc__.split("\n\n")[1])
    kind, d, name, arg = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    if kind == "generate":  # the scene, quoted or not
        arg, sys.argv[5:] = " ".join(sys.argv[4:]), []
    fx, fy, zoom = (float(x) for x in (sys.argv[5:8] + ["0.5", "0.5", "1"][len(sys.argv[5:8]):]))
    if kind == "person":
        person(d, name, pathlib.Path(arg))
    elif kind in ("photo", "raw"):
        photo(d, name, pathlib.Path(arg), fx, fy, zoom, kind == "photo")
    elif kind == "generate":
        generate(d, name, arg)
    else:
        die(f"unknown kind {kind!r}: person, photo, raw or generate")
    print(f"  {kind} {name}: done; look at it: it must read on its own")


if __name__ == "__main__":
    main()
