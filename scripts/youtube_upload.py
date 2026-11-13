#!/usr/bin/env python3
"""Upload the event's talk videos to YouTube.

Raw HTTP against the resumable upload protocol — no google-api-python-client,
because the dependency buys nothing here and this way the whole flow is visible
in one file.

Videos land as **private**. That is not a choice: the Data API locks every
upload from an unverified API project to private, silently. `privacyStatus:
public` is accepted and ignored, the call succeeds, and an email arrives later
saying the video was locked. Flip them to public by hand in YouTube Studio.

Credentials, one time:

  1. console.cloud.google.com → new project
  2. APIs & Services → Library → enable "YouTube Data API v3"
  3. APIs & Services → Credentials → Create credentials → OAuth client ID
     → Application type: **Desktop app**
  4. Put the two values in .env:
         YOUTUBE_CLIENT_ID=...
         YOUTUBE_CLIENT_SECRET=...
  5. Run this script. It prints a URL, you approve in the browser, and the
     refresh token is cached at ~/.config/agnteng/youtube-token.json (mode 600)
     so step 5 never repeats.

Quota: an upload costs 1600 units against a 10,000/day default, so six videos a
day. Three is fine.
"""

from __future__ import annotations

import argparse
import http.server
import json
import pathlib
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

import common
import youtube_md
from common import die
from common import secret as env

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"
THUMB = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
SCOPE = "https://www.googleapis.com/auth/youtube"  # upload + playlists + thumbnails

TOKEN_FILE = pathlib.Path.home() / ".config" / "agnteng" / "youtube-token.json"
CHUNK = 8 * 1024 * 1024  # 8 MiB per resumable chunk


def post_form(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type":
                                          "application/x-www-form-urlencoded"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        die(f"{url} returned HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def consent(client_id: str, client_secret: str) -> dict:
    """Loopback OAuth. A desktop client cannot keep a secret, so Google's own
    flow for it is exactly this: open a browser, catch the redirect locally."""
    port = free_port()
    redirect = f"http://127.0.0.1:{port}"
    got: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            ok = "code" in got
            self.wfile.write(
                b"<h2>Done - close this tab and go back to the terminal.</h2>"
                if ok else b"<h2>No code returned. Check the terminal.</h2>")

        def log_message(self, *a):  # silence the default stderr logging
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.handle_request, daemon=True).start()

    url = AUTH + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect,
        "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent"})
    print("\nOpen this and approve:\n")
    print(f"  {url}\n")
    print("waiting for the redirect…", file=sys.stderr)
    import time
    for _ in range(600):
        if got:
            break
        time.sleep(0.5)
    if "code" not in got:
        die(f"no authorization code received ({got or 'timed out'})")

    tok = post_form(TOKEN, {
        "code": got["code"], "client_id": client_id,
        "client_secret": client_secret, "redirect_uri": redirect,
        "grant_type": "authorization_code"})
    if "refresh_token" not in tok:
        die("Google did not return a refresh token — revoke the app's access "
            "at myaccount.google.com/permissions and run this again")
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({"refresh_token": tok["refresh_token"]}))
    TOKEN_FILE.chmod(0o600)
    print(f"stored refresh token at {TOKEN_FILE}", file=sys.stderr)
    return tok


def access_token(client_id: str, client_secret: str) -> str:
    if TOKEN_FILE.exists():
        rt = json.loads(TOKEN_FILE.read_text()).get("refresh_token")
        if rt:
            tok = post_form(TOKEN, {
                "refresh_token": rt, "client_id": client_id,
                "client_secret": client_secret, "grant_type": "refresh_token"})
            return tok["access_token"]
    return consent(client_id, client_secret)["access_token"]


def upload(path: pathlib.Path, meta: dict, token: str) -> str:
    size = path.stat().st_size
    body = json.dumps({
        "snippet": {"title": meta["title"], "description": meta["description"],
                    "tags": meta.get("tags", []),
                    "categoryId": meta.get("category", "22")},  # People & Blogs, as published,
        # Locked private regardless by an unverified project — stated, not implied.
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }).encode()

    req = urllib.request.Request(
        UPLOAD + "?" + urllib.parse.urlencode(
            {"uploadType": "resumable", "part": "snippet,status"}),
        data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(size),
                 "X-Upload-Content-Type": "video/mp4"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            session = r.headers["Location"]
    except urllib.error.HTTPError as e:
        die(f"could not start the upload: HTTP {e.code} "
            f"{e.read().decode(errors='replace')[:300]}")

    sent = 0
    with path.open("rb") as fh:
        while sent < size:
            chunk = fh.read(CHUNK)
            last = sent + len(chunk)
            r = urllib.request.Request(
                session, data=chunk, method="PUT",
                headers={"Content-Length": str(len(chunk)),
                         "Content-Range": f"bytes {sent}-{last-1}/{size}"})
            try:
                with urllib.request.urlopen(r, timeout=600) as resp:
                    done = json.loads(resp.read())
                    print("    100%", file=sys.stderr)
                    return done["id"]
            except urllib.error.HTTPError as e:
                if e.code != 308:  # 308 = resume incomplete, keep going
                    die(f"upload failed at {sent}: HTTP {e.code} "
                        f"{e.read().decode(errors='replace')[:300]}")
                rng = e.headers.get("Range")
                sent = int(rng.split("-")[1]) + 1 if rng else last
                print(f"    {sent*100//size:3d}%", end="\r", file=sys.stderr)
    die("upload ended without an id")


def api(method: str, path: str, token: str, params: dict | None = None,
        body: dict | None = None) -> dict:
    url = f"{API}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(
        url, method=method, data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        die(f"{method} {path} returned HTTP {e.code}: "
            f"{e.read().decode(errors='replace')[:300]}")


def my_playlists(token: str) -> list[dict]:
    out, page = [], None
    while True:
        params = {"part": "snippet,status", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        r = api("GET", "playlists", token, params)
        out += r.get("items", [])
        page = r.get("nextPageToken")
        if not page:
            return out


def ensure_playlist(token: str, title: str, description: str) -> str:
    """Reuse a playlist with exactly this title, else create it private.
    Reuse is what makes a re-run safe."""
    for pl in my_playlists(token):
        if pl["snippet"]["title"] == title:
            print(f"playlist exists: {title}  ({pl['id']})", file=sys.stderr)
            return pl["id"]
    pl = api("POST", "playlists", token, {"part": "snippet,status"}, {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": "private"}})
    print(f"created playlist: {title}  ({pl['id']})", file=sys.stderr)
    return pl["id"]


def add_to_playlist(token: str, playlist: str, video: str, position: int) -> None:
    have = api("GET", "playlistItems", token,
               {"part": "snippet", "playlistId": playlist, "maxResults": 50})
    if any(i["snippet"]["resourceId"].get("videoId") == video
           for i in have.get("items", [])):
        return
    api("POST", "playlistItems", token, {"part": "snippet"}, {
        "snippet": {"playlistId": playlist, "position": position,
                    "resourceId": {"kind": "youtube#video", "videoId": video}}})


def set_thumbnail(token: str, video: str, image: pathlib.Path) -> None:
    """thumbnails.set: a 16:9 jpg/png under 2 MB, ideally 1280x720. Needs a
    phone-verified channel; without it YouTube answers 403."""
    data = image.read_bytes()
    if len(data) > 2 * 1024 * 1024:
        die(f"{image}: {len(data)/1e6:.1f} MB, YouTube's thumbnail limit is 2 MB")
    ctype = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    req = urllib.request.Request(
        THUMB + "?" + urllib.parse.urlencode({"videoId": video}),
        data=data, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": ctype})
    try:
        urllib.request.urlopen(req, timeout=120).read()
    except urllib.error.HTTPError as e:
        die(f"thumbnail for {video} failed: HTTP {e.code} "
            f"{e.read().decode(errors='replace')[:300]}")


def from_event(event: pathlib.Path) -> list[dict]:
    """One item per talk folder, read from its youtube.md (regenerated first
    when the folder has a talk.json):
    a `Title:` first line, the description, and a trailing `Tags:` line."""
    items = []
    for d in sorted(p for p in event.iterdir() if p.is_dir() and p.name[:2].isdigit()):
        md = d / "youtube.md"
        vid = common.clip_path(event, d.name)
        # youtube.md is generated from description.md + talk.json; rebuild it
        # here so an edit to the description can never upload stale text.
        want = youtube_md.for_talk(d)
        if want is not None and (not md.exists() or md.read_text() != want):
            md.write_text(want)
            print(f"regenerated {md} from description.md", file=sys.stderr)
        if not md.exists():
            # e.g. NN-qa/: the Q&A is for the newsletter, never YouTube.
            print(f"skipping {d.name}: no youtube.md", file=sys.stderr)
            continue
        lines = md.read_text().strip().splitlines()
        if not lines[0].startswith("Title:"):
            die(f"{md}: first line must be 'Title: …'")
        title = lines[0].split(":", 1)[1].strip()
        tags: list[str] = []
        if lines[-1].startswith("Tags:"):
            tags = [t.strip() for t in lines[-1].split(":", 1)[1].split(",") if t.strip()]
            lines = lines[:-1]
        desc = "\n".join(lines[1:]).strip()
        if "agentic engineering" in title.lower():
            die(f"{md}: keep 'Agentic Engineering' out of the title; "
                f"it's 'Talk Title - Speaker', and the playlist carries the event")
        if len(title) > 100:
            die(f"{md}: title is {len(title)} chars, YouTube's limit is 100")
        if len(desc.encode()) > 5000:
            die(f"{md}: description is over YouTube's 5000-byte limit")
        if "<" in desc or ">" in desc:
            die(f"{md}: YouTube rejects < and > in descriptions")
        items.append({"dir": str(d), "file": str(vid), "title": title,
                      "description": desc, "tags": tags})
    if not items:
        die(f"no NN-* talk folders in {event}")
    return items


def link_markdown(d: pathlib.Path, url: str) -> None:
    """Put the video URL on each talk title: VIDEO_URL in description.md, and
    the h1 of transcript.md becomes a link."""
    desc = d / "description.md"
    if desc.exists():
        desc.write_text(desc.read_text().replace("(VIDEO_URL)", f"({url})"))
    tr = d / "transcript.md"
    if tr.exists():
        lines = tr.read_text().splitlines()
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            if title.startswith("[") and "](" in title:
                title = title[1:title.index("](")]
            lines[0] = f"# [{title}]({url})"
            tr.write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("metadata", nargs="?",
                    help="JSON file [{file, title, description, tags}], or an event "
                         "folder (content/<date>) to read each NN-*/youtube.md")
    ap.add_argument("--playlist", help="playlist title to create or reuse, e.g. 'Lisbon #5'")
    ap.add_argument("--playlist-description", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--login", action="store_true",
                    help="run the browser consent and cache the refresh token, then exit")
    args = ap.parse_args()

    if args.login:
        consent(env("YOUTUBE_CLIENT_ID"), env("YOUTUBE_CLIENT_SECRET"))
        return
    if not args.metadata:
        ap.error("metadata is required unless --login")

    src = pathlib.Path(args.metadata)
    event = src if src.is_dir() else None
    items = from_event(src) if event else json.loads(src.read_text())
    for it in items:
        p = pathlib.Path(it["file"])
        if not p.exists():
            die(f"missing video: {p}")
        print(f"  {p.name}  ({p.stat().st_size/1e6:.0f} MB)  →  {it['title']}")
    if args.playlist:
        print(f"  playlist: {args.playlist}")
    if args.dry_run:
        print("\n(dry run, nothing uploaded)")
        return

    cid, secret = env("YOUTUBE_CLIENT_ID"), env("YOUTUBE_CLIENT_SECRET")
    token = access_token(cid, secret)
    playlist = (ensure_playlist(token, args.playlist, args.playlist_description)
                if args.playlist else None)

    out = []
    for it in items:
        p = pathlib.Path(it["file"])
        # A per-talk youtube.json means this talk is already up: never upload
        # it twice, a re-run only fills in what is missing.
        done = pathlib.Path(it["dir"]) / "youtube.json" if it.get("dir") else None
        if done and done.exists():
            vid = json.loads(done.read_text())["video_id"]
            print(f"\n{p.name} already uploaded: {vid}", file=sys.stderr)
        else:
            print(f"\nuploading {p.name}…", file=sys.stderr)
            vid = upload(p, it, token)
        url = f"https://www.youtube.com/watch?v={vid}"
        rec = {**it, "video_id": vid, "url": url, "playlist_id": playlist}
        if done:
            done.write_text(json.dumps(rec, indent=1) + "\n")
        thumb = pathlib.Path(it["dir"]) / "thumbnail.jpg" if it.get("dir") else None
        if thumb and thumb.exists():
            set_thumbnail(token, vid, thumb)
            print(f"  thumbnail set from {thumb}", file=sys.stderr)
        if playlist:
            # Prepend: the channel's playlists list the last talk first.
            add_to_playlist(token, playlist, vid, 0)
        if it.get("dir"):
            link_markdown(pathlib.Path(it["dir"]), url)
        print(f"  {url}  (private)")
        out.append(rec)

    res = (event / "youtube.json") if event else src.with_name("youtube.json")
    res.write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nwrote {res}")
    if playlist:
        print(f"playlist: https://www.youtube.com/playlist?list={playlist}  (private)")
    print("All private: review and publish them in YouTube Studio.")


if __name__ == "__main__":
    main()
