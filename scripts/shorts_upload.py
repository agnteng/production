#!/usr/bin/env python3
"""Upload talk clips to YouTube as Shorts, each scheduled to go public at its time.

    python3 scripts/shorts_upload.py SCHEDULE.json             every entry with no video yet, earliest first
    python3 scripts/shorts_upload.py SCHEDULE.json --dry-run   what would go up, with each description
    python3 scripts/shorts_upload.py SCHEDULE.json --update    re-send the text of entries already up
    python3 scripts/shorts_upload.py SCHEDULE.json --limit 1   only the first

The schedule is an unpublished plan, so it is kept with the content calendar,
not in this repository: a JSON list of

    {"clip": "2026-11-11/02-david-mihal/why", "publish_at": "2026-11-20T09:00:00Z",
     "title": "…", "summary": "…", "hashtags": ["#AIAgents"]}

`clip` is `<date>/<talk>/<id>` of a clip in `content/<date>/<talk>/clips.json`,
rendered as `<talk>.<id>.mp4` in the event's media folder. Each upload is
private with `publishAt`, so YouTube makes it public then, and its id is
written back into the schedule as `video_id`, so a re-run never uploads it
twice. An entry whose title is already among the channel's uploads takes that
video's id instead (an upload whose answer was lost).

The description is composed here and never stored: the summary, the speaker
and their role as the website's event.json gives them (org ADR 0006), the
event, the full talk's link from the talk's youtube.json, agnteng.com, and the
hashtags; the talk's tags go with it. `--update` changes the title,
description and tags, and the time only while the video is still scheduled.

An entry that isn't ready (no render, no full talk, a time already past) is
reported and skipped. Quota: an upload costs 1600 of the 10,000 units a day,
so six a day; on quotaExceeded the run stops, and the next day's run carries on.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re

import common
import youtube_upload as yt
from common import ROOT, WEBSITE_CONTENT, die
from common import secret as env


def future(at: str) -> bool:
    t = datetime.datetime.fromisoformat(at.replace("Z", "+00:00"))
    return t > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)


def parts(e: dict) -> tuple[pathlib.Path, str]:
    date, talk, cid = e["clip"].split("/")
    return ROOT / "content" / date / talk, cid


def description(talk: pathlib.Path, e: dict) -> str:
    ev = json.loads((WEBSITE_CONTENT / talk.parent.name / "event.json").read_text())
    n = int(talk.name[:2])
    if not 0 < n <= len(ev["speakers"]):
        raise ValueError(f"event.json has no speaker {n}")
    speaker = ev["speakers"][n - 1]
    if not set(talk.name[3:].split("-")) & set(re.findall(r"[a-z]+", speaker["name"].lower())):
        raise ValueError(f"speaker {n} in event.json is {speaker['name']}, not {talk.name}")
    full = json.loads((talk / "youtube.json").read_text())["url"]
    when = datetime.date.fromisoformat(ev["date"]).strftime("%B %Y")
    who = f"{speaker['name']} ({speaker['title']})" if speaker.get("title") else speaker["name"]
    text = (f"{e['summary']}\n\n{who} at Agentic Engineering {ev['city']} #{ev['number']}, {when}.\n"
            f"Full talk: {full}\n\nMore talks and the next meetup: https://agnteng.com")
    return text + ("\n\n" + " ".join(e["hashtags"]) if e.get("hashtags") else "")


def ready(e: dict) -> tuple[pathlib.Path, str, list[str]] | str:
    """(video file, description, tags), or why the entry can't go up."""
    talk, cid = parts(e)
    video = common.media_dir(talk.parent) / "shorts" / f"{talk.name}.{cid}.mp4"
    if not video.is_file():
        return f"no render at {video}"
    try:
        text = description(talk, e)
    except (OSError, KeyError, ValueError) as err:
        return f"no description: {err}"
    if len(e["title"]) > 60:  # the talk-clip skill's limit, under YouTube's 100
        return f"title is {len(e['title'])} characters, over 60"
    if re.search(r"[<>]", e["title"] + text) or len(text.encode()) > 5000:
        return "title or description YouTube would refuse (< or >, or over 5000 bytes)"
    return video, text, json.loads((talk / "talk.json").read_text()).get("tags", [])


def record(path: pathlib.Path, clip: str, video_id: str) -> None:
    """Write one entry's id into the schedule as it is now, not as it was when the run began."""
    entries = json.loads(path.read_text())
    next(x for x in entries if x["clip"] == clip)["video_id"] = video_id
    path.write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n")


def uploaded(token: str) -> dict[str, str]:
    """Title → id of every video on the channel, private and scheduled ones included."""
    ch = yt.api("GET", "channels", token, {"part": "contentDetails", "mine": "true"})
    playlist = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    out, page = {}, None
    while True:
        r = yt.api("GET", "playlistItems", token, {"part": "snippet", "playlistId": playlist, "maxResults": 50,
                                                    **({"pageToken": page} if page else {})})
        out.update({i["snippet"]["title"]: i["snippet"]["resourceId"]["videoId"] for i in r["items"]})
        page = r.get("nextPageToken")
        if not page:
            return out


def update(e: dict, text: str, tags: list[str], token: str) -> None:
    """New title, description and tags; the time too while the video is still scheduled. Every other field as it is."""
    v = yt.api("GET", "videos", token, {"part": "snippet,status", "id": e["video_id"]})["items"][0]
    snippet = {**v["snippet"], "title": e["title"], "description": text, "tags": tags}
    body, part = {"id": e["video_id"], "snippet": snippet}, "snippet"
    if v["status"].get("publishAt") and v["status"]["privacyStatus"] == "private" and future(e["publish_at"]):
        body["status"], part = {**v["status"], "publishAt": e["publish_at"]}, "snippet,status"
    yt.api("PUT", "videos", token, {"part": part}, body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("schedule", type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    entries = sorted(json.loads(args.schedule.read_text()), key=lambda x: x["publish_at"])
    todo = [x for x in entries if bool(x.get("video_id")) == args.update]
    token = None if args.dry_run else yt.access_token(env("YOUTUBE_CLIENT_ID"), env("YOUTUBE_CLIENT_SECRET"))
    have = uploaded(token) if token and not args.update else {}
    done = 0
    for e in todo:
        got = ready(e)
        if isinstance(got, str) or (not args.update and not future(e["publish_at"])):
            print(f"skip {e['clip']}: {got if isinstance(got, str) else 'its time ' + e['publish_at'] + ' has passed'}")
            continue
        if args.limit and done >= args.limit:
            break
        done += 1
        video, text, tags = got
        print(f"{e['publish_at']}  {e['clip']}  {e['title']}")
        if args.dry_run:
            print("    " + text.replace("\n", "\n    ") + "\n")
        elif args.update:
            update(e, text, tags, token)
        elif e["title"] in have:
            record(args.schedule, e["clip"], have[e["title"]])
            print(f"    already on the channel as {have[e['title']]}: recorded, not uploaded again")
        else:
            vid = yt.upload(video, {"title": e["title"], "description": text, "tags": tags}, token, e["publish_at"])
            record(args.schedule, e["clip"], vid)
            s = yt.api("GET", "videos", token, {"part": "status", "id": vid})["items"][0]["status"]
            print(f"    https://youtube.com/shorts/{vid}  {s['privacyStatus']}, publishAt {s.get('publishAt', 'NOT SET')}")
    if not done:
        print("nothing to do")


if __name__ == "__main__":
    main()
