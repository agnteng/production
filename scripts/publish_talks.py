#!/usr/bin/env python3
"""Write an event's talks and Q&A into ../website/content/<date>/.

    python3 scripts/publish_talks.py <event>     content/<date>, <date> or a Luma slug

talks/<NN-speaker>.json from each talk folder, questions.json from the Q&A
folder. Files there that no longer have a source here are deleted. Re-run
after any write-up or upload change (org ADR 0007).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import WEBSITE_CONTENT, event_dir

LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
PLACEHOLDER = re.compile(r"^[A-Z_]+_URL$")
YOUTUBE_ID = re.compile(r"(?:v=|youtu\.be/)([\w-]{11})")


def links(text: str) -> list[dict]:
    return [{"label": label, "url": url} for label, url in LINK.findall(text)
            if not PLACEHOLDER.match(url)]


def parse_description(md: str) -> dict:
    lines = [ln.rstrip() for ln in md.strip().splitlines()]
    head = LINK.search(lines[0])
    title = head.group(1) if head else lines[0].lstrip("# ").strip()
    url = head.group(2) if head and not PLACEHOLDER.match(head.group(2)) else None
    paras = [p.strip() for p in "\n".join(lines[1:]).split("\n\n") if p.strip()]
    out = {"title": title, "summary": "", "takeaways": [], "speakerLinks": [],
           "mentioned": [], "videoUrl": url}
    for p in paras:
        if p.startswith("**Main Takeaways**"):
            p = p.removeprefix("**Main Takeaways**")
        if p.lstrip().startswith("* "):
            out["takeaways"] += [re.sub(r"^\*\s+", "", ln.strip())
                                 for ln in p.splitlines() if ln.strip().startswith("*")]
        elif not p.strip():
            continue
        elif p.startswith("Mentioned:"):
            out["mentioned"] = links(p)
        elif not out["summary"]:
            out["summary"] = p
        elif LINK.search(p):
            out["speakerLinks"] = links(p)
    return out


def speaker_name(folder: Path, event_json: dict) -> str:
    """talk.json's speaker, else the event's NNth speaker, else the folder name."""
    talk = folder / "talk.json"
    if talk.exists():
        return json.loads(talk.read_text())["speaker"]
    speakers = event_json.get("speakers", [])
    n = int(folder.name[:2])
    if 0 < n <= len(speakers):
        return speakers[n - 1]["name"]
    return folder.name.split("-", 1)[1].replace("-", " ").title()


def video(folder: Path, video_url: str | None) -> dict | None:
    yt = folder / "youtube.json"
    if yt.exists():
        d = json.loads(yt.read_text())
        if d.get("video_id"):
            return {"youtubeId": d["video_id"], "url": d["url"]}
    m = YOUTUBE_ID.search(video_url or "")
    return {"youtubeId": m.group(1), "url": video_url} if m else None


def transcript(folder: Path) -> str | None:
    t = folder / "transcript.md"
    if not t.exists():
        return None
    # Drop the heading and the provenance note; keep the timestamped paragraphs.
    body = t.read_text().split("\n\n")
    return "\n\n".join(p for p in body if p.startswith("**[")) or None


def parse_questions(md: str) -> list[dict]:
    """`#### question` sections, each answered by `**Name:** text` paragraphs."""
    out = []
    for block in md.split("\n#### ")[1:]:
        question, _, body = block.partition("\n")
        answers = []
        for para in body.strip().split("\n\n"):
            para = " ".join(para.split())
            m = re.match(r"\*\*(.+?):\*\*\s*(.*)", para)
            if m:
                answers.append({"speaker": m.group(1), "text": m.group(2)})
            elif answers and para and not para.startswith("---"):
                answers[-1]["text"] += "\n\n" + para
        out.append({"question": question.strip(), "answers": answers})
    return out


def write(path: Path, data) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if not path.exists() or path.read_text() != text:
        path.write_text(text)
        print(f"  wrote {path.relative_to(WEBSITE_CONTENT.parent)}")


def remove(path: Path) -> None:
    path.unlink()
    print(f"  removed {path.relative_to(WEBSITE_CONTENT.parent)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("event")
    args = ap.parse_args()
    event = event_dir(args.event)
    date = event.name
    event_json = json.loads((WEBSITE_CONTENT / date / "event.json").read_text())
    out_dir = WEBSITE_CONTENT / date / "talks"
    talks = sorted(p for p in event.iterdir()
                   if p.is_dir() and p.name[:2].isdigit() and (p / "description.md").exists()
                   and not p.name.endswith("-qa"))
    out_dir.mkdir(exist_ok=True)
    for folder in talks:
        d = parse_description((folder / "description.md").read_text())
        talk = {
            "slug": folder.name[3:],
            "order": int(folder.name[:2]),
            "title": d["title"],
            "speaker": speaker_name(folder, event_json),
            "summary": d["summary"],
            "takeaways": d["takeaways"],
            "speakerLinks": d["speakerLinks"],
            "mentioned": d["mentioned"],
            "video": video(folder, d["videoUrl"]),
            "transcript": transcript(folder),
        }
        write(out_dir / f"{folder.name}.json", talk)
    for stale in set(out_dir.glob("*.json")) - {out_dir / f"{f.name}.json" for f in talks}:
        remove(stale)
    if not any(out_dir.iterdir()):
        out_dir.rmdir()
    qa = next((p / "questions.md" for p in event.iterdir()
               if p.name.endswith("-qa") and (p / "questions.md").exists()), None)
    questions = WEBSITE_CONTENT / date / "questions.json"
    if qa:
        write(questions, parse_questions(qa.read_text()))
    elif questions.exists():
        remove(questions)
    print(f"{date}: {len(talks)} talks{', Q&A' if qa else ''}")


if __name__ == "__main__":
    main()
