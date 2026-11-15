# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==12.3.0", "rembg==2.0.86", "onnxruntime==1.31.1", "opencv-python-headless==4.11.0.86"]
# ///
"""Person mask and face position per headshot.

    uv run scripts/speaker_masks.py ../website/apps/branding/public/assets/speakers/<slug>.jpg …

Writes speaker-masks/<slug>.png beside speakers/: the person in the alpha
channel (white throughout), edge feathered, no metadata. sources.json records each headshot's sha256,
size and face ([x, y, height] fractions, or null); the website frames
speakers by it. Models: rembg (~/.u2net) and YuNet (~/.cache/agnteng, pinned
SHA-256). Separate from photos.py so photos don't pull them in.
"""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import cv2
from PIL import Image, ImageFilter
from rembg import new_session, remove

MODEL = "birefnet-portrait"  # keeps hair, glasses and caps
FEATHER = 1.5
FACE_URL = "https://github.com/opencv/opencv_zoo/raw/f12e12798e8314f7c074a6656816c048dcc95b7a/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
FACE_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
FACE_MODEL = Path.home() / ".cache" / "agnteng" / "face_detection_yunet_2023mar.onnx"


def face_model() -> str:
    if not FACE_MODEL.exists():
        FACE_MODEL.parent.mkdir(parents=True, exist_ok=True)
        part = FACE_MODEL.with_suffix(".part")
        urllib.request.urlretrieve(FACE_URL, part)
        if hashlib.sha256(part.read_bytes()).hexdigest() != FACE_SHA256:
            part.unlink()
            raise SystemExit(f"{FACE_URL}: unexpected checksum; not using it")
        part.replace(FACE_MODEL)
    return str(FACE_MODEL)


def face(src: Path, model: str) -> list[float] | None:
    """The largest face: [centre x, centre y, height], as fractions of the photo."""
    img = cv2.imread(str(src))
    h, w = img.shape[:2]
    _, faces = cv2.FaceDetectorYN.create(model, "", (w, h), 0.6).detect(img)
    if faces is None or not len(faces):
        return None
    x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])[:4]
    return [round(float((x + fw / 2) / w), 3), round(float((y + fh / 2) / h), 3), round(float(fh / h), 3)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("headshots", nargs="+", type=Path)
    ap.add_argument("--model", default=MODEL, help="a rembg model, e.g. u2net_human_seg")
    args = ap.parse_args()
    session, faces = new_session(args.model), face_model()
    for src in args.headshots:
        out = src.parent.parent / "speaker-masks" / f"{src.stem}.png"
        alpha = remove(Image.open(src).convert("RGB"), session=session, only_mask=True).convert("L")
        alpha = alpha.filter(ImageFilter.GaussianBlur(FEATHER))
        out.parent.mkdir(parents=True, exist_ok=True)
        # The person is the alpha channel: iOS reads a luminance mask as alpha.
        # A merged image carries no metadata from the source.
        Image.merge("LA", (Image.new("L", alpha.size, 255), alpha)).save(out, "PNG", optimize=True)
        found = face(src, faces)
        print(f"{out}  {out.stat().st_size // 1024} KB  face {found}")
        manifest = out.parent / "sources.json"
        sources = json.loads(manifest.read_text()) if manifest.exists() else {}
        sources[src.name] = {"sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                             "size": list(alpha.size), "face": found}
        manifest.write_text(json.dumps(dict(sorted(sources.items())), indent=2) + "\n")


if __name__ == "__main__":
    main()
