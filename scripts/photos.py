# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==11.3.0", "pillow-heif==1.1.0"]
# ///
"""Every photo that goes on the website comes through here.

    uv run scripts/photos.py web SRC DEST [--no-enhance] [--max-edge 1600]
    uv run scripts/photos.py optimize FILE …                rewrite in place
    uv run scripts/photos.py preview SRC OUT.jpg            before | after, side by side

`web` and `optimize` turn the photo upright (EXIF orientation), convert its
colour profile to sRGB (phone photos are Display P3), auto-enhance it, cap the
long edge, sharpen lightly after the resize, and save an optimized
progressive JPEG with no metadata at all: no EXIF, GPS, XMP or ICC.

The enhancement is mild by design, so a good photo stays as it was: levels
stretched per channel (which also pulls out a colour cast), blended in at
ENHANCE_MIX, then a touch of saturation. Use --no-enhance for headshots,
screenshots, slides and anything in brand colours. Re-encoding loses a
little each time: optimize a photo once, not on a schedule.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageCms, ImageEnhance, ImageFilter, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

QUALITY = 75
MAX_EDGE = 1600
ENHANCE_MIX = 0.6
SATURATION = 1.06
SRGB = ImageCms.createProfile("sRGB")


def load(path: Path) -> Image.Image:
    """Upright and in sRGB. Transparency goes onto white."""
    img = ImageOps.exif_transpose(Image.open(path))
    icc = img.info.get("icc_profile")
    if img.mode == "P":
        img = img.convert("RGBA")
    if img.mode in ("RGBA", "LA", "PA"):
        rgba = img.convert("RGBA")
        img = Image.new("RGB", img.size, "white")
        img.paste(rgba, mask=rgba.getchannel("A"))
    elif img.mode.startswith("I"):  # 16- or 32-bit greyscale: scale, don't clip
        img = img.convert("I").point(lambda v: v / 256).convert("L")
    if icc:
        try:  # the profile's own colour space (CMYK, grey, P3) to sRGB
            img = ImageCms.profileToProfile(img, ImageCms.ImageCmsProfile(io.BytesIO(icc)), SRGB, outputMode="RGB")
        except (OSError, ImageCms.PyCMSError):
            pass  # unreadable or mismatched profile: treat the pixels as sRGB
    return img.convert("RGB")


def taken(path: Path) -> str | None:
    """When the photo was taken (EXIF DateTimeOriginal, else DateTime), as YYYY:MM:DD HH:MM:SS."""
    exif = Image.open(path).getexif()
    return exif.get_ifd(0x8769).get(36867) or exif.get(306)


def enhance(img: Image.Image) -> Image.Image:
    levelled = ImageOps.autocontrast(img, cutoff=0.5)
    img = Image.blend(img, levelled, ENHANCE_MIX)
    return ImageEnhance.Color(img).enhance(SATURATION)


def resize(img: Image.Image, max_edge: int) -> Image.Image:
    if max(img.size) <= max_edge:
        return img
    img = ImageOps.contain(img, (max_edge, max_edge), Image.Resampling.LANCZOS)
    return img.filter(ImageFilter.UnsharpMask(radius=0.8, percent=40, threshold=2))


def save(img: Image.Image, dest: Path) -> None:
    if dest.suffix != ".jpg":
        sys.exit(f"{dest}: web copies are .jpg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".partial")
    img.info.clear()  # no comment, EXIF or profile carried over
    img.save(tmp, "JPEG", quality=QUALITY, optimize=True, progressive=True, subsampling="4:2:0")
    tmp.replace(dest)


def web(src: Path, dest: Path, *, do_enhance: bool = True, max_edge: int = MAX_EDGE) -> None:
    img = load(src)
    if do_enhance:
        img = enhance(img)
    save(resize(img, max_edge), dest)


def preview(src: Path, out: Path) -> None:
    img = load(src)
    before, after = resize(img, 800), resize(enhance(img), 800)
    sheet = Image.new("RGB", (before.width * 2 + 8, before.height), "white")
    sheet.paste(before, (0, 0))
    sheet.paste(after, (before.width + 8, 0))
    save(sheet, out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    opts = argparse.ArgumentParser(add_help=False)
    opts.add_argument("--no-enhance", action="store_true")
    opts.add_argument("--max-edge", type=int, default=MAX_EDGE)
    w = sub.add_parser("web", parents=[opts], help="SRC → an optimized, enhanced web copy at DEST (.jpg)")
    w.add_argument("src", type=Path)
    w.add_argument("dest", type=Path)
    o = sub.add_parser("optimize", parents=[opts], help="rewrite .jpg photos already on the site, in place")
    o.add_argument("files", nargs="+", type=Path)
    p = sub.add_parser("preview", help="before and after, side by side")
    p.add_argument("src", type=Path)
    p.add_argument("out", type=Path)
    args = ap.parse_args()

    if args.cmd == "web":
        web(args.src, args.dest, do_enhance=not args.no_enhance, max_edge=args.max_edge)
        print(f"{args.dest}  {args.dest.stat().st_size // 1024} KB")
    elif args.cmd == "optimize":
        for f in args.files:
            if f.suffix != ".jpg":
                sys.exit(f"{f}: optimize rewrites .jpg files in place; convert others with `web`")
            before = f.stat().st_size
            web(f, f, do_enhance=not args.no_enhance, max_edge=args.max_edge)
            print(f"{f}  {before // 1024} → {f.stat().st_size // 1024} KB")
    else:
        preview(args.src, args.out)
        print(args.out)


if __name__ == "__main__":
    main()
