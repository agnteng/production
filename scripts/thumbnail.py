#!/usr/bin/env python3
"""Make a talk's YouTube thumbnail from a photo of the speaker, and set it.

    python3 scripts/thumbnail.py <event> <talk> --photo speaker.jpg --face 598,312,58 \\
            --hook "81% Written|by Agents"
    python3 scripts/thumbnail.py <event> <talk> --enhance   # sharpen a soft speaker with AI
    python3 scripts/thumbnail.py <event>             # re-render every talk that has one
    python3 scripts/thumbnail.py <event> --upload    # ...and set them on the videos

The design is scripts/thumbnail.html, drawn in headless Chrome: the photo fills
the frame with the room blurred and darkened, the speaker stays sharp on their
own side, and the hook sits on the other side with its last line on the yellow
block. What a thumbnail needs is recorded under "thumbnail" in the talk's
talk.json, so it can be rendered again:

    photo   the speaker photo, copied to <media>/<date>/thumbnails/ (never in git)
    face    x,y,h in the photo's pixels: the centre of the face and the head's
            height, chin to top of hair. Look at the photo to find them.
    hook    one or two short lines, "|" between them. Five words at most, and
            something the video title does not already say. The last line gets
            the yellow block; start the other with * to give it that instead
            ("*81%|Written by Agents").

`--enhance` is for a photo where the speaker is small and soft. It sends a crop
of the speaker (never the name or the talk) to an image model on OpenRouter
and uses what comes back for the speaker only; the room still comes from the
photo. The model invents the detail it adds, so the result is a likeness, not
a record: compare `<media>/<date>/thumbnails/<talk>-enhanced.png` with the
photo, and let someone who knows the speaker decide, before it goes on a video.
`--no-enhance` goes back to the photo.

Run the `thumbnail-critic` skill on the result before `--upload`.

Needs Chrome or Chromium (CHROME_BIN, else the usual places), ffmpeg, and the
network for the brand fonts. `--enhance` needs OPENROUTER_API_KEY. `--upload` needs the YouTube credentials of
youtube_upload.py and a talk that is already uploaded (youtube.json).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

import common
from common import die

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "thumbnail.html"
# The logo is the brand's, in the website repository: read, never copied.
MARK = common.ROOT.parent / "website/apps/branding/public/assets/logo/ae-mark-white.svg"
SIZE = (1280, 720)
LIMIT = 2 * 1024 * 1024  # thumbnails.set refuses more
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".svg": "image/svg+xml"}
# Kept closest to the photo in a side-by-side of the image models (2026-11).
ENHANCE_MODEL = "google/gemini-3.1-flash-image"
ENHANCE_PROMPT = (
    "Restore this photo: increase its resolution and sharpness and remove compression noise and blur. "
    "This is a real person at a real event. Keep their identity, facial features, expression, gaze, pose, "
    "hair, clothing, the microphone and the background exactly as they are. Do not beautify, restyle, "
    "relight dramatically, add or remove anything, or change the framing. Return only the restored image.")
CHROMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "/Applications/Chromium.app/Contents/MacOS/Chromium")


def chrome() -> str:
    for c in filter(None, (os.environ.get("CHROME_BIN"), *CHROMES)):
        found = shutil.which(c)
        if found:
            return found
    die("no Chrome or Chromium found: install one or set CHROME_BIN")


def data_uri(p: pathlib.Path) -> str:
    mime = MIME.get(p.suffix.lower())
    if not mime:
        die(f"{p.name}: use a jpg, png or webp photo")
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def tag(event: pathlib.Path) -> str:
    """'Lisbon #4', from the website's event.json."""
    f = common.WEBSITE_CONTENT / event.name / "event.json"
    if not f.is_file():
        die(f"no {f}: the event tag comes from it")
    e = json.loads(f.read_text())
    return f"{e['city']} #{e['number']}"


def talks(event: pathlib.Path, name: str | None) -> list[pathlib.Path]:
    found = sorted(d for d in event.glob("[0-9][0-9]-*") if (d / "talk.json").is_file())
    if name:
        found = [d for d in found if d.name == name or d.name.split("-", 1)[-1] == name
                 or d.name.startswith(name + "-")]
        if len(found) != 1:
            die(f"{name!r} matches {len(found)} talk folders in {event}")
    return found


def record(talk: pathlib.Path, args: argparse.Namespace, media: pathlib.Path) -> None:
    """Merge --photo, --face and --hook into talk.json's "thumbnail"."""
    meta = json.loads((talk / "talk.json").read_text())
    t = meta.get("thumbnail", {})
    if args.photo:
        src = pathlib.Path(args.photo).expanduser()
        if not src.is_file():
            die(f"no photo at {src}")
        dest = media / "thumbnails" / f"{talk.name}{src.suffix.lower()}"
        dest.parent.mkdir(exist_ok=True)
        if src.resolve() != dest.resolve():
            shutil.copyfile(src, dest)
        t["photo"] = dest.name
    if args.face:
        try:
            x, y, h = (int(v) for v in args.face.split(","))
        except ValueError:
            die("--face is x,y,h in the photo's pixels, e.g. 598,312,58")
        t["face"] = [x, y, h]
    if args.hook:
        lines = [l.strip() for l in args.hook.split("|") if l.strip()]
        if not 1 <= len(lines) <= 2:
            die("--hook is one or two lines, with | between them")
        if len(" ".join(lines).replace("*", "").split()) > 5:
            die(f"--hook {args.hook!r} is over five words: it will not read at feed size")
        t["hook"] = lines
    if args.photo or args.face or args.no_enhance:
        t.pop("enhanced", None)  # it was made from the old photo or face
    meta["thumbnail"] = t
    (talk / "talk.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")


def enhance(talk: pathlib.Path, media: pathlib.Path, model: str) -> None:
    """A sharper speaker from an image model, saved beside the photo and noted
    in talk.json with the box of the photo it replaces."""
    meta = json.loads((talk / "talk.json").read_text())
    t = meta.get("thumbnail", {})
    if not t.get("photo") or not t.get("face"):
        die(f"{talk.name}: --enhance needs the talk's --photo and --face first")
    photo = media / "thumbnails" / t["photo"]
    x, y, h = t["face"]
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(photo)],
                           check=True, capture_output=True, text=True).stdout.strip().split(",")
    pw, ph = int(probe[0]), int(probe[1])
    # Head, shoulders and hands: about three head-heights each side, five below.
    left, top = max(0, round(x - 3.2 * h)), max(0, round(y - 1.6 * h))
    w, hh = min(pw - left, round(6.4 * h)), min(ph - top, round(6.6 * h))
    with tempfile.TemporaryDirectory() as tmp:
        crop = pathlib.Path(tmp) / "crop.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(photo), "-vf",
                        f"crop={w}:{hh}:{left}:{top}", str(crop)], check=True)
        body = {"model": model, "modalities": ["image", "text"], "messages": [{"role": "user", "content": [
            {"type": "text", "text": ENHANCE_PROMPT},
            {"type": "image_url", "image_url": {"url": data_uri(crop)}}]}]}
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {common.openrouter_key()}", "Content-Type": "application/json"})
    try:
        reply = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        die(f"{model}: HTTP {e.code} {e.read().decode(errors='replace')[:300]}")
    images = reply["choices"][0]["message"].get("images") or []
    if not images:
        die(f"{model} returned no image for {talk.name}")
    dest = media / "thumbnails" / f"{talk.name}-enhanced.png"
    dest.write_bytes(base64.b64decode(images[0]["image_url"]["url"].split(",", 1)[1]))
    t["enhanced"] = {"file": dest.name, "box": [left, top, w, hh], "model": model}
    meta["thumbnail"] = t
    (talk / "talk.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
    print(f"  {talk.name}: speaker enhanced by {model}. Compare {dest} with {photo} before using it.",
          file=sys.stderr)


def render(talk: pathlib.Path, event: pathlib.Path, media: pathlib.Path) -> pathlib.Path | None:
    t = json.loads((talk / "talk.json").read_text()).get("thumbnail")
    if not t:
        return None
    missing = [k for k in ("photo", "face", "hook") if not t.get(k)]
    if missing:
        print(f"  {talk.name}: no {', '.join(missing)} yet, skipped", file=sys.stderr)
        return None
    photo = media / "thumbnails" / t["photo"]
    if not photo.is_file():
        die(f"{talk.name}: {photo} is gone; pass --photo again")
    x, y, h = t["face"]
    cfg = {"photo": data_uri(photo), "mark": data_uri(MARK), "tag": tag(event),
           "hook": t["hook"], "face": {"x": x, "y": y, "h": h}}
    sharp = t.get("enhanced")
    if sharp and (media / "thumbnails" / sharp["file"]).is_file():
        cfg["sharp"] = {"src": data_uri(media / "thumbnails" / sharp["file"]), "box": sharp["box"]}
    out = talk / "thumbnail.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        page, png = pathlib.Path(tmp) / "page.html", pathlib.Path(tmp) / "shot.png"
        page.write_text(TEMPLATE.read_text().replace("__CFG__", json.dumps(cfg)))
        # Twice the size, so the type stays sharp wherever YouTube shows it large.
        subprocess.run(
            [chrome(), "--headless=new", "--hide-scrollbars", f"--window-size={SIZE[0]},{SIZE[1]}",
             "--force-device-scale-factor=2", "--virtual-time-budget=8000",
             f"--user-data-dir={tmp}/profile", f"--screenshot={png}", page.as_uri()],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        if not png.is_file():
            die(f"{talk.name}: Chrome made no screenshot")
        for q in (2, 4, 6, 9):  # the first quality that fits under the limit
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-q:v", str(q), str(out)], check=True)
            if out.stat().st_size <= LIMIT:
                break
        else:
            die(f"{out}: still over 2 MB at the lowest quality")
    print(f"  {out.relative_to(common.ROOT)}  ({out.stat().st_size / 1e3:.0f} kB)  {' / '.join(t['hook'])}")
    return out


def upload(done: list[tuple[pathlib.Path, pathlib.Path]]) -> None:
    import youtube_upload as yt
    token = yt.access_token(common.secret("YOUTUBE_CLIENT_ID"), common.secret("YOUTUBE_CLIENT_SECRET"))
    for talk, image in done:
        y = talk / "youtube.json"
        if not y.is_file():
            print(f"  {talk.name}: not on YouTube yet (no youtube.json), not set", file=sys.stderr)
            continue
        vid = json.loads(y.read_text())["video_id"]
        yt.set_thumbnail(token, vid, image)
        print(f"  set on https://www.youtube.com/watch?v={vid}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("event", help="content/<date>, <date> or the Luma slug")
    ap.add_argument("talk", nargs="?", help="talk folder (02-david-mihal), its number (02) or its name (david-mihal)")
    ap.add_argument("--photo", help="photo of the speaker")
    ap.add_argument("--face", help="x,y,h in the photo's pixels: face centre and head height")
    ap.add_argument("--hook", help='one or two lines, e.g. "81%% Written|by Agents"')
    ap.add_argument("--enhance", nargs="?", const=ENHANCE_MODEL, metavar="MODEL",
                    help=f"sharpen the speaker with an image model (default {ENHANCE_MODEL})")
    ap.add_argument("--no-enhance", action="store_true", help="go back to the photo as it is")
    ap.add_argument("--upload", action="store_true", help="set the thumbnails on the YouTube videos")
    args = ap.parse_args()
    if (args.photo or args.face or args.hook or args.enhance or args.no_enhance) and not args.talk:
        ap.error("--photo, --face, --hook and --enhance belong to one talk: name it")

    event = common.event_dir(args.event)
    media = common.media_dir(event)
    found = talks(event, args.talk)
    if args.talk:
        record(found[0], args, media)
        if args.enhance:
            enhance(found[0], media, args.enhance)
    done = [(d, out) for d in found if (out := render(d, event, media))]
    if not done and not args.talk:
        die("nothing rendered: give a talk its --photo, --face and --hook")
    if args.upload:
        upload(done)


if __name__ == "__main__":
    main()
