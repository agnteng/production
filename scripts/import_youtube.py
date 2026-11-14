#!/usr/bin/env python3
"""Bring talks that are already on YouTube into content/<date>/.

    mise exec -- python3 scripts/import_youtube.py <event> ID [ID …] [--recap URL] [--transcribe]

Ids in talk order (the order of the event's Substack recap). Each talk folder
gets youtube.json, talk.json, description.md (from the YouTube description;
an existing one only has its VIDEO_URL and <LABEL>_URL placeholders filled),
youtube.md and thumbnail.jpg; the event gets a README.md if it has none.
--recap fills speaker and mentioned links the YouTube description lacks.
--transcribe downloads the audio to the media folder and runs the 60s and 30s
passes; it exits 1 if any chunk is SUSPECT, for a 10s re-run before publishing.
A talk that already has a transcript.md is left alone.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path

import talk_transcript
import transcribe_chunks
import youtube_md
from common import WEBSITE_CONTENT, die, event_dir, media_dir, work_dir

LINK_LINE = re.compile(r"^-?\s*([^:]+?):\s*(https?://\S+)\s*$")
PLACEHOLDER = re.compile(r"\[([^\]]+)\]\(([A-Z_]+_URL)\)")
UA = {"User-Agent": "agnteng-production"}


def slugify(name: str) -> str:
    """ASCII folder names: "Jean-Loïc Mugnier" → jean-loic-mugnier."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s.replace("'", "")).strip("-") or "talk"


def yt_dlp(*args: str) -> str:
    if not shutil.which("yt-dlp"):
        die("yt-dlp not found: run this under `mise exec --` (mise.toml pins it)")
    r = subprocess.run(["yt-dlp", "--no-warnings", *args], capture_output=True, text=True)
    if r.returncode:
        die(f"yt-dlp {' '.join(args)}: {r.stderr.strip()[-400:]}")
    return r.stdout


def parse_description(text: str) -> dict:
    """The house format as YouTube shows it: summary, takeaways, then link blocks.

    A line is a link when it reads `Label: https://…`; any other `- ` line is a
    takeaway. A link block headed "Mentioned…", or any after the first, holds
    mentioned links.
    """
    blocks = [b.strip() for b in text.strip().split("\n\n") if b.strip()]
    out = {"summary": blocks[0] if blocks else "", "takeaways": [], "speakerLinks": [], "mentioned": []}
    for block in blocks[1:]:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        links = [{"label": m[1], "url": m[2]} for ln in lines if (m := LINK_LINE.match(ln))]
        out["takeaways"] += [ln[2:].strip() for ln in lines if ln.startswith("- ") and not LINK_LINE.match(ln)]
        if links:
            mentioned = "mentioned" in lines[0].lower() or bool(out["speakerLinks"])
            out["mentioned" if mentioned else "speakerLinks"] += links
    return out


def recap_links(page: str, vid: str) -> dict:
    """The speaker's and mentioned links under this video's heading in a recap."""
    out = {"speakerLinks": [], "mentioned": []}
    i = page.find(f'href="https://www.youtube.com/watch?v={vid}"')
    if i < 0:
        i = page.find(f'href="https://youtu.be/{vid}"')
    if i < 0:
        return out
    # The talk's section ends at the next heading or embedded video (the next talk).
    section = re.split(r"<h[1-6][ >]|native-video-embed|VideoEmbedPlayer|youtube2",
                       page[i:], maxsplit=1)[0]
    for para in re.findall(r"<p>(.*?)</p>", section, re.S):
        text = html.unescape(re.sub(r"<[^>]+>", "", para))
        links = [{"label": html.unescape(re.sub(r"<[^>]+>", "", l)), "url": html.unescape(u)}
                 for u, l in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', para, re.S)]
        if text.startswith("Mentioned"):
            out["mentioned"] = links
        elif re.match(r"^[\w' .-]+[’']s ", text) and links:
            out["speakerLinks"] = links
    return out


def speaker_of(folder: Path | None, meta: dict, summary: str, event_json: dict) -> tuple[str, str]:
    """(speaker, title). The speaker is talk.json's, else the event speaker the
    title or summary names, else the "Title - Speaker" suffix."""
    title = meta["title"]
    speaker = None
    if folder and (folder / "talk.json").exists():
        speaker = json.loads((folder / "talk.json").read_text())["speaker"]
    for sp in event_json.get("speakers", []):
        if not speaker and (sp["name"] in title or sp["name"] in summary):
            speaker = sp["name"]
    if " - " in title:
        t, _, suffix = title.rpartition(" - ")
        if not speaker or suffix.strip() == speaker:
            speaker, title = speaker or suffix.strip(), t.strip()
    if not speaker:
        die(f"{meta['id']}: can't tell who the speaker is; add speakers to event.json")
    return speaker, title


def house_format(title: str, url: str, speaker: str, d: dict) -> str:
    """description.md as the agentic-engineering-description skill writes it."""
    parts = [f"### [{title}]({url})", d["summary"]]
    if d["takeaways"]:
        parts.append("**Main Takeaways**\n\n" + "\n".join(f"*   {k}" for k in d["takeaways"]))
    if d["speakerLinks"]:
        parts.append(f"{speaker.split()[0]}'s " + ", ".join(f"[{l['label']}]({l['url']})" for l in d["speakerLinks"]))
    if d["mentioned"]:
        parts.append("Mentioned: " + ", ".join(f"[{l['label']}]({l['url']})" for l in d["mentioned"]))
    return "\n\n".join(parts) + "\n"


def fill_placeholders(md: str, url: str, links: list[dict]) -> str:
    md = md.replace("(VIDEO_URL)", f"({url})")
    by_label = {l["label"].lower(): l["url"] for l in links}
    return PLACEHOLDER.sub(lambda m: f"[{m.group(1)}]({by_label[m.group(1).lower()]})"
                           if m.group(1).lower() in by_label else m.group(0), md)


def transcribe(event: Path, folder: Path, url: str, title: str, speaker: str) -> list[str]:
    """Write transcript.md; return the SUSPECT lines."""
    audio = media_dir(event) / f"{folder.name}.mp3"
    if not audio.exists():
        print(f"  downloading audio → {audio}")
        yt_dlp("-x", "--audio-format", "mp3", "-o", str(audio.with_suffix(".%(ext)s")), url)
    end = transcribe_chunks.duration(audio)
    coarse = transcribe_chunks.transcribe(audio, 0, end, 60)
    transcribe_chunks.write(coarse, work_dir(event) / f"{folder.name}_coarse.json")
    fine = transcribe_chunks.transcribe(audio, 0, end, 30)
    transcribe_chunks.write(fine, work_dir(event) / f"{folder.name}.json")
    (folder / "transcript.md").write_text(talk_transcript.render(fine, 0, title, speaker, checked=False))
    print(f"  wrote {folder / 'transcript.md'} ({len(fine)} chunks)")
    found = transcribe_chunks.suspects(fine, coarse)
    for line in found:
        print(f"  {line}")
    return found


def fetch_thumbnail(vid: str, dest: Path) -> None:
    for name in ("maxresdefault", "hqdefault"):
        try:
            data = urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{name}.jpg", timeout=30).read()
        except OSError:
            continue
        dest.write_bytes(data)
        return


def event_readme(ev: dict, talks: list[tuple[Path, str, str, dict]]) -> str:
    """README for an event whose talks came from YouTube: what's here and what isn't."""
    when = dt.date.fromisoformat(ev["date"]).strftime("%-d %B %Y")
    lines = [f"# Agentic Engineering {ev['city']} #{ev['number']}, {when}", "",
             f"{ev['venue']}. City, venue, Luma ids and speakers are in the website's `event.json`."]
    if ev.get("luma"):
        lines += ["", f"Luma: [{ev['luma']['url'].removeprefix('https://')}]({ev['luma']['url']})"]
    if ev.get("recap"):
        lines += ["", f"Recap on Substack: [{ev['recap'].removeprefix('https://')}]({ev['recap']})"]
    lines += ["", "## What's here", "", "| Path | What |", "|---|---|",
              "| `NN-<speaker>/` | One folder per talk, imported from YouTube with `scripts/import_youtube.py`: "
              "`description.md`, `transcript.md`, `youtube.md`, `youtube.json`, `talk.json`, `thumbnail.jpg`. |",
              f"| `$AGNTENG_MEDIA/{ev['date']}/` | Outside the repo: each talk's audio, downloaded from YouTube, and the chunk transcripts. |",
              "", "## The talks", "", "| | Talk | Speaker | Length |", "|---|---|---|---|"]
    for folder, title, speaker, meta in talks:
        m, sec = divmod(int(meta.get("duration") or 0), 60)
        lines.append(f"| {folder.name[:2]} | [{title}]({meta['webpage_url']}) | {speaker} | {m}:{sec:02d} |")
    known = {sp["name"] for sp in ev.get("speakers", [])}
    no_role = [sp for _, _, sp, _ in talks if sp not in known]
    no_photo = [sp["name"] for sp in ev.get("speakers", []) if not sp.get("photo")]
    lines += ["", "## Still missing", "",
              "- **No camera files.** The talks were imported from YouTube, so there is no raw "
              "footage and no Q&A recording.",
              "- **Transcripts are unchecked** against the slides: names and products may be misheard."]
    if no_role:
        lines.append(f"- **No role in `event.json`** for {', '.join(no_role)}.")
    if no_photo:
        lines.append(f"- **No photo** for {', '.join(no_photo)}.")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event")
    ap.add_argument("ids", nargs="+", help="YouTube video ids, in talk order")
    ap.add_argument("--recap", help="the event's Substack recap URL")
    ap.add_argument("--transcribe", action="store_true")
    args = ap.parse_args()
    event = event_dir(args.event)
    event_json = json.loads((WEBSITE_CONTENT / event.name / "event.json").read_text())
    recap = ""
    if args.recap:
        recap = urllib.request.urlopen(urllib.request.Request(args.recap, headers=UA), timeout=30).read().decode()

    imported, suspect = [], False
    for n, vid in enumerate(args.ids, 1):
        url = f"https://www.youtube.com/watch?v={vid}"
        meta = json.loads(yt_dlp("-j", "--skip-download", url))
        d = parse_description(meta["description"])
        if recap:
            r = recap_links(recap, vid)
            for k in ("speakerLinks", "mentioned"):
                d[k] = d[k] or r[k]
        existing = sorted(event.glob(f"{n:02d}-*"))
        speaker, title = speaker_of(existing[0] if existing else None, meta, d["summary"], event_json)
        folder = event / f"{n:02d}-{slugify(speaker)}"
        if existing and existing[0] != folder:
            die(f"{existing[0].name} exists, but video {n} is {speaker}: check the order of the ids")
        folder.mkdir(exist_ok=True)
        print(f"{folder.name}: {title} ({speaker})")

        tags = meta.get("tags") or []
        (folder / "youtube.json").write_text(json.dumps({
            "title": meta["title"], "description": meta["description"], "tags": tags, "video_id": vid, "url": url,
        }, indent=1, ensure_ascii=False) + "\n")
        if not (folder / "talk.json").exists():
            (folder / "talk.json").write_text(json.dumps({"speaker": speaker, "tags": tags}, indent=1, ensure_ascii=False) + "\n")
        md = folder / "description.md"
        md.write_text(fill_placeholders(md.read_text(), url, d["speakerLinks"]) if md.exists()
                      else house_format(title, url, speaker, d))
        if d["takeaways"] or "**Main Takeaways**" in md.read_text():
            (folder / "youtube.md").write_text(youtube_md.for_talk(folder))
        else:
            print(f"  no takeaways in {md}: add them, then run scripts/youtube_md.py", file=sys.stderr)
        if not (folder / "thumbnail.jpg").exists():
            fetch_thumbnail(vid, folder / "thumbnail.jpg")
        imported.append((folder, title, speaker, meta))
        if args.transcribe and not (folder / "transcript.md").exists():
            suspect |= bool(transcribe(event, folder, url, title, speaker))

    readme = event / "README.md"
    if not readme.exists():
        readme.write_text(event_readme(event_json, imported))
        print(f"wrote {readme}")
    if suspect:
        die("SUSPECT chunks above: re-run each span with transcribe_chunks.py --seconds 10, "
            "then talk_transcript.py --unchecked, before publishing")


if __name__ == "__main__":
    main()
