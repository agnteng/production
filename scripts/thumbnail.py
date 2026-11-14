#!/usr/bin/env python3
"""Make a talk's YouTube thumbnail from a photo of the speaker, and set it.

    python3 scripts/thumbnail.py <event> <talk> --photo speaker.jpg --face 598,312,58 \\
            --hook "81% Written|by Agents"
    python3 scripts/thumbnail.py <event> <talk> --enhance   # sharpen a soft speaker with AI
    python3 scripts/thumbnail.py <event>                    # re-render every talk that has one
    python3 scripts/thumbnail.py <event> --upload           # ...and set them on the videos

The design is scripts/thumbnail.html. Its inputs are recorded under "thumbnail"
in the talk's talk.json, so a thumbnail can be rendered again:

    photo   the speaker photo, copied to <media>/<date>/thumbnails/ (never in git)
    face    x,y,h in that copy's pixels: the centre of the face and the head's
            height, chin to top of hair. Look at the photo to find them.
    hook    one to three short lines, "|" between them, five words at most:
            what the talk is about, readable with no title beside it. Short
            lines are set larger. The yellow block goes on the last line,
            or on what you mark: a line starting with *, or a *phrase* in one.
            Break lines at phrase boundaries and keep them of similar length.

--enhance sends a crop of the speaker (never the name or the talk) to an image
model and uses the result for the speaker only. The model invents detail:
compare <media>/<date>/thumbnails/<talk>-enhanced.png with the photo before it
goes on a video (docs/adr/0003). --no-enhance goes back to the photo.

Needs Chrome or Chromium (CHROME_BIN, else the usual places) and the network
for the fonts.
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
import urllib.error
import urllib.request

import common
from common import die

TEMPLATE = pathlib.Path(__file__).resolve().parent / "thumbnail.html"
# The logo is the brand's, in the website repository: read, never copied.
MARK = common.ROOT.parent / "website/apps/branding/public/assets/logo/ae-mark-white.svg"
LIMIT = 2 * 1024 * 1024  # thumbnails.set refuses more
MIME = {".jpg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml"}
ENHANCE_MODEL = "google/gemini-3.1-flash-image"  # docs/adr/0003
ENHANCE_PROMPT = (
    "Restore this photo: increase its resolution and sharpness and remove compression noise and blur. "
    "This is a real person at a real event. Keep their identity, facial features, expression, gaze, pose, "
    "hair, clothing, the microphone and the background exactly as they are. Do not beautify, restyle, "
    "relight dramatically, add or remove anything, or change the framing. Return only the restored image.")
CHROMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "/Applications/Chromium.app/Contents/MacOS/Chromium")


def chrome(*args: str) -> str:
    """Run headless Chrome and return its stdout."""
    binary = next(filter(None, (shutil.which(c) for c in (os.environ.get("CHROME_BIN"), *CHROMES) if c)), None)
    if not binary:
        die("no Chrome or Chromium found: install one or set CHROME_BIN")
    with tempfile.TemporaryDirectory() as profile:
        try:
            return subprocess.run(
                [binary, "--headless=new", "--hide-scrollbars", "--window-size=1280,720",
                 "--force-device-scale-factor=1", "--virtual-time-budget=8000",
                 f"--user-data-dir={profile}", *args],
                check=False, capture_output=True, text=True, timeout=120).stdout
        except subprocess.TimeoutExpired:
            die("Chrome did not finish within two minutes")


def data_uri(p: pathlib.Path) -> str:
    return f"data:{MIME[p.suffix]};base64,{base64.b64encode(p.read_bytes()).decode()}"


def size(image: pathlib.Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", str(image)],
                         check=True, capture_output=True, text=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def talks(event: pathlib.Path, name: str | None) -> list[pathlib.Path]:
    found = sorted(d for d in event.glob("[0-9][0-9]-*") if (d / "talk.json").is_file())
    if name:
        found = [d for d in found if name in (d.name, d.name[:2], d.name[3:])]
        if len(found) != 1:
            die(f"{name!r} matches {len(found)} talk folders in {event}")
    return found


def take_photo(src: pathlib.Path, dest: pathlib.Path) -> None:
    """Copy the photo as an upright JPEG with no metadata, so the pixels the
    face is measured in are the pixels ffmpeg crops and Chrome draws."""
    if not src.is_file():
        die(f"no photo at {src}")
    dest.parent.mkdir(exist_ok=True)
    made = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-frames:v", "1",
                           "-map_metadata", "-1", "-q:v", "1", str(dest)], capture_output=True, text=True)
    if made.returncode:
        die(f"{src.name}: ffmpeg could not read it as a photo ({made.stderr.strip()[:200]})")


def enhance(photo: pathlib.Path, face: list[int], dest: pathlib.Path) -> dict:
    """A sharper speaker from the image model, saved at dest. Returns what
    talk.json keeps: the file and the box of the photo it replaces."""
    x, y, h = face
    pw, ph = size(photo)
    # Head, shoulders and hands: about three head-heights each side, five below.
    left, top = max(0, round(x - 3.2 * h)), max(0, round(y - 1.6 * h))
    w, hh = min(pw - left, round(6.4 * h)), min(ph - top, round(6.6 * h))
    with tempfile.TemporaryDirectory() as tmp:
        crop = pathlib.Path(tmp) / "crop.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(photo), "-vf",
                        f"crop={w}:{hh}:{left}:{top}", str(crop)], check=True)
        body = {"model": ENHANCE_MODEL, "modalities": ["image", "text"], "messages": [{"role": "user", "content": [
            {"type": "text", "text": ENHANCE_PROMPT},
            {"type": "image_url", "image_url": {"url": data_uri(crop)}}]}]}
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {common.openrouter_key()}", "Content-Type": "application/json"})
    try:
        reply = json.loads(urllib.request.urlopen(req, timeout=300).read())
        image = reply["choices"][0]["message"]["images"][0]["image_url"]["url"]
    except urllib.error.HTTPError as e:
        die(f"{ENHANCE_MODEL}: HTTP {e.code} {e.read().decode(errors='replace')[:300]}")
    except (OSError, KeyError, IndexError, TypeError, ValueError) as e:
        die(f"{ENHANCE_MODEL} returned no image ({type(e).__name__}: {e})")
    dest.write_bytes(base64.b64decode(image.split(",", 1)[1]))
    print(f"  speaker enhanced: compare {dest} with {photo} before using it", file=sys.stderr)
    return {"file": dest.name, "box": [left, top, w, hh]}


def record(talk: pathlib.Path, args: argparse.Namespace, shots: pathlib.Path) -> None:
    """Merge the flags into talk.json's "thumbnail"."""
    meta = json.loads((talk / "talk.json").read_text())
    t = meta.get("thumbnail", {})
    if args.photo:
        t["photo"] = f"{talk.name}.jpg"
        take_photo(pathlib.Path(args.photo).expanduser(), shots / t["photo"])
    if args.face:
        if not re.fullmatch(r"\d+,\d+,[1-9]\d*", args.face):
            die("--face is x,y,h in the photo's pixels, e.g. 598,312,58")
        t["face"] = [int(v) for v in args.face.split(",")]
    if args.hook:
        lines = [l.strip() for l in args.hook.split("|") if l.strip()]
        if not 1 <= len(lines) <= 3:
            die("--hook is one to three lines, with | between them")
        if len(" ".join(lines).replace("*", "").split()) > 5:
            die(f"--hook {args.hook!r} is over five words: it will not read at feed size")
        t["hook"] = lines
        widths = [len(l.replace("*", "")) for l in lines]
        if min(widths) * 2.5 < max(widths):
            print(f"  warning: {min(lines, key=len)!r} is a stray short line beside a long one; "
                  "rebalance the breaks", file=sys.stderr)
    if args.photo or args.face or args.no_enhance:
        t.pop("enhanced", None)  # it was made from the old photo or face
    if args.enhance:
        if not t.get("photo") or not t.get("face"):
            die(f"{talk.name}: --enhance needs the talk's --photo and --face first")
        pw, ph = size(shots / t["photo"])
        if not (t["face"][0] < pw and t["face"][1] < ph):
            die(f"{talk.name}: face {t['face'][:2]} is outside the {pw}x{ph} photo")
        t["enhanced"] = enhance(shots / t["photo"], t["face"], shots / f"{talk.name}-enhanced.png")
    meta["thumbnail"] = t
    (talk / "talk.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")


def render(talk: pathlib.Path, shots: pathlib.Path) -> pathlib.Path | None:
    """Write the talk's thumbnail.jpg, or say why not and return None."""
    t = json.loads((talk / "talk.json").read_text()).get("thumbnail") or {}
    missing = [k for k in ("photo", "face", "hook") if not t.get(k)]
    if not missing and not (shots / t["photo"]).is_file():
        missing = [f"photo file ({shots / t['photo']})"]
    if missing:
        if t:
            print(f"  {talk.name}: no {', '.join(missing)}, skipped", file=sys.stderr)
        return None
    x, y, h = t["face"]
    cfg = {"photo": data_uri(shots / t["photo"]), "mark": data_uri(MARK),
           "hook": t["hook"], "face": {"x": x, "y": y, "h": h}}
    sharp = t.get("enhanced")
    if sharp and (shots / sharp["file"]).is_file():
        cfg["sharp"] = {"src": data_uri(shots / sharp["file"]), "box": sharp["box"]}
    out = talk / "thumbnail.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        page, png = pathlib.Path(tmp) / "page.html", pathlib.Path(tmp) / "shot.png"
        # "</" would end the script block the JSON sits in.
        page.write_text(TEMPLATE.read_text().replace("/*CFG*/null", json.dumps(cfg).replace("</", "<\\/")))
        # Chrome screenshots whatever is there when time runs out, so ask the
        # page first whether it finished: it sets its title to "ready".
        title = re.search(r"<title>(.*?)</title>", chrome("--dump-dom", page.as_uri()), re.S)
        if not title or title.group(1) != "ready":
            die(f"{talk.name}: the page did not render ({title.group(1) if title else 'no title'})")
        chrome(f"--screenshot={png}", page.as_uri())
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
    ap.add_argument("--hook", help='one to three lines, e.g. "81%% Written|by Agents"')
    ap.add_argument("--enhance", action="store_true", help="sharpen the speaker with an image model")
    ap.add_argument("--no-enhance", action="store_true", help="go back to the photo as it is")
    ap.add_argument("--upload", action="store_true", help="set the thumbnails on the YouTube videos")
    args = ap.parse_args()
    edits = args.photo or args.face or args.hook or args.enhance or args.no_enhance
    if edits and not args.talk:
        ap.error("--photo, --face, --hook and --enhance belong to one talk: name it")

    event = common.event_dir(args.event)
    shots = common.media_dir(event) / "thumbnails"
    found = talks(event, args.talk)
    if edits:
        record(found[0], args, shots)
    done = [(d, out) for d in found if (out := render(d, shots))]
    if not done:
        die("nothing rendered: a talk needs its --photo, --face and --hook")
    if args.upload:
        upload(done)


if __name__ == "__main__":
    main()
