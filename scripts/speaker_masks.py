# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==12.3.0", "rembg==2.0.86", "onnxruntime==1.31.1"]
# ///
"""Person mask per headshot.

    uv run scripts/speaker_masks.py ../website/apps/branding/public/assets/speakers/<slug>.jpg …

Writes speaker-masks/<slug>.png beside speakers/: greyscale, person white,
edge feathered, no metadata. speaker-masks/sources.json records the SHA-256
of each headshot a mask was made from, so the website can tell a stale mask. A local rembg model (weights in ~/.u2net);
separate from photos.py so photos don't pull it in.
"""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageFilter
from rembg import new_session, remove

MODEL = "birefnet-portrait"  # keeps hair, glasses and caps
FEATHER = 1.5


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("headshots", nargs="+", type=Path)
    ap.add_argument("--model", default=MODEL, help="a rembg model, e.g. u2net_human_seg")
    args = ap.parse_args()
    session = new_session(args.model)
    for src in args.headshots:
        out = src.parent.parent / "speaker-masks" / f"{src.stem}.png"
        alpha = remove(Image.open(src).convert("RGB"), session=session, only_mask=True).convert("L")
        alpha = alpha.filter(ImageFilter.GaussianBlur(FEATHER))
        out.parent.mkdir(parents=True, exist_ok=True)
        # A fresh image carries no metadata from the source.
        Image.frombytes("L", alpha.size, alpha.tobytes()).save(out, "PNG", optimize=True)
        print(f"{out}  {out.stat().st_size // 1024} KB")
        manifest = out.parent / "sources.json"
        sources = json.loads(manifest.read_text()) if manifest.exists() else {}
        sources[src.name] = hashlib.sha256(src.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(dict(sorted(sources.items())), indent=2) + "\n")


if __name__ == "__main__":
    main()
