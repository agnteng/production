---
name: meetup-video
description: Turn an Agentic Engineering meetup recording into one folder per talk (clip, transcript, Substack and YouTube descriptions) plus a Q&A folder (clip, transcript, newsletter questions), then upload the talks to YouTube as private drafts in the event's playlist. Use when camera footage for an event turns up, or the user asks to cut, transcribe or write up an event's talks, or to upload them.
---

# Meetup video → per-talk folders

A camera recording of the evening, sometimes split across several files: the
host's opening, then ~3 talks of ~10 minutes, each possibly followed by its own
Q&A, or one Q&A for all speakers at the end. The job: find each talk, cut it
without the Q&A, cut the Q&A as its own clip, and produce everything needed to
publish both.

Every rule below came from a real failure; `references/traps.md` has the
evidence. Output formats for the Q&A file, YouTube and the upload are in
`references/formats.md`.

## What gets produced

Two places. The repository holds only what gets published; the media never
enters it.

```
content/<date>/             in the repo: tracked
  event.json                city, venue, Luma ids, speakers; shared with the deck
  README.md                 the cut, titles, QR codes, speakers' links, what's missing
  NN-<speaker-slug>/
    transcript.md           timestamped from 0:00 of the clip
    description.md          Substack-ready; the source for youtube.md
    talk.json               {"speaker", "tags"}: what YouTube needs beyond the description
    youtube.md              generated from the two above
    youtube.json            video and playlist ids, written by the upload
    thumbnail.jpg           1280x720, set on the video
  NN-qa/                    newsletter only, never YouTube (no talk.json)
    transcript.md  questions.md

$AGNTENG_MEDIA/<date>/      outside the repo: the workspace's media/, gitignored
  raw/C0084.MP4 C0085.MP4   camera files, untouched; one timeline in filename order
  NN-<speaker-slug>.mp4     each talk's clip, no Q&A, 50 fps; NN-qa.mp4 likewise
  work/                     audio, chunk transcripts, frames, cache: scratch
```

The scripts take the event as `content/<date>` (or just `<date>`) and find its
media themselves.

The Q&A folder takes the next number after the last talk.

## Setup, once

`ffmpeg`, `ffprobe` and `zbarimg` (`brew install zbar`; then check ffmpeg still
runs). `OPENROUTER_API_KEY` in the environment or the repo-root `.env`.

Transcription is OpenRouter only (`google/gemini-3.8-flash` with an
`input_audio` block, about $0.016 per 90 seconds). When OpenRouter returns 401
("User not found" means the key was revoked) or runs out of credit, stop and
tell the user the key needs replacing; the scripts exit on 401 and 402 for this
reason. Whisper and local speech-to-text stay out of it entirely. The model is
part of the chunk cache key, so re-running an event transcribed with another
model pays for every chunk again.

## Steps

`E=content/<date>`, `W=$(python3 scripts/meetup_video.py media $E)/work`. Timecodes everywhere are M:SS or H:MM:SS on the joined
timeline.

1. **Probe and extract audio.**
   `python3 scripts/meetup_video.py probe $E` then `… audio $E`.
   Done when probe lists every file in `raw/` and their creation times line up
   end to end (a gap would shift every later timecode).

2. **Coarse pass and frames.**
   `python3 scripts/transcribe_chunks.py $W/audio.mp3 --out $W/coarse.json --seconds 60`
   and `python3 scripts/meetup_video.py frames $E --span 0:00-<end> --tag all --every 4`.

3. **Find the boundaries.** `python3 scripts/detect_talks.py $E --talks 3`
   writes `work/talks.json`; then read `work/coarse.txt` around every boundary
   yourself. Done when each talk has a start, an end and a Q&A span you have
   confirmed in the text, and each talk is near ten minutes: a talk far off ten
   minutes is a wrong boundary, so go back and read.
   - **Start** at the speaker's first word, two seconds of air before.
   - **End** after the closing line and the applause, three seconds after,
     before anyone opens questions. When the applause only comes after the
     Q&A, end on the closing line plus two seconds.
   - **Q&A** runs from the host opening questions to the applause that closes
     them, before the host's wrap-up.
   - Where unsure, refine with 5s chunks over a 90s window. In a boundary
     dispute the fine pass wins over the coarse one.

4. **Each talk, and the Q&A.** One command per clip:

   ```sh
   python3 scripts/meetup_video.py talk $E --n 1 --talk 'Andy Nikulin@8:36-21:28' \
     --title "…" --speaker "Andy Nikulin"
   python3 scripts/meetup_video.py talk $E --n 4 --talk 'QA@42:10-66:14' \
     --title "Q&A: …" --speaker "All three speakers, with audience questions"
   ```

   It cuts the clip, transcribes 30s chunks with the plain default prompt,
   prints SUSPECT for chunks that look invented or empty (against their
   neighbours and against `coarse.json`), and writes `transcript.md`. For every
   SUSPECT, re-run with `--fix START-END` (10s chunks over that span, patched
   in) and read the result against the coarse pass. Done when the command
   prints no SUSPECT, or each remaining one is explained in the event README.
   - Leave `--prompt` at its default: a prompt with names or terms produces
     whole invented passages. Names get fixed afterwards, from the slides.
   - The Q&A is where hallucinations cluster; read every Q&A chunk.
   - A talk that isn't contiguous (a demo shown later, dead air) is built with
     `meetup_video.py splice $E --out NN-name --span … --span … --dry-run`,
     then transcribed with `transcribe_chunks.py` per span and rendered with
     `talk_transcript.py`. Append late material after the closing applause
     rather than injecting it, and read what the speaker says around each join.
   - Several Q&A sessions (one per talk) are spliced into one `NN-qa.mp4`.

5. **Titles, names and links.** Done when every talk has its title, its
   speaker's name as on their slides, and every link the talk mentions or
   shows, each resolved.
   - **Title**: the first slide after the talk's start on
     `work/frames/all/sheet-NN.jpg` (times in `sheet-NN.txt`), read from the
     full frame `tNNNNN.jpg`, cropped if small:
     `ffmpeg -i tNNNNN.jpg -vf crop=1040:620:500:20 out.jpg`. Propose a title
     only when no slide shows one, and say it's proposed.
   - **Name and role**: `content/<date>/event.json` (written with the deck,
     which reads it), checked against the speaker's own slides; the slides win (rename the folder to
     match). Who actually spoke comes from the transcript.
   - **Socials**: web search on name + company; accept a profile only when it
     matches the company or the talk, and note where it was confirmed. A
     placeholder plus a note beats a wrong handle.
   - **Links**: from the transcript (products, "it's on GitHub"), the slides,
     and `work/frames/all/qr.txt`. A QR on a sheet that qr.txt missed: crop,
     upscale and retry
     (`ffmpeg -i tNNNNN.jpg -vf "crop=…,scale=iw*3:-1" q.png && zbarimg q.png`),
     and report any still unread. Resolve each to its canonical URL with a web
     search, and record the QR table in the event README, since `work/` is
     not committed.

6. **Write.** Invoke the `agentic-engineering-description` skill for each
   `description.md` (it owns the format, with `(VIDEO_URL)` as the link until
   upload). Write each `talk.json` and `NN-qa/questions.md` as in
   `references/formats.md`, then `python3 scripts/youtube_md.py $E`.
   Attribute every Q&A answer from what it says, never from the model's
   speaker labels. Done when `youtube_md.py $E --check` passes and the event
   `README.md` lists the cut table and everything still missing.

7. **Upload** as in `references/formats.md`: dry run, then the real run with
   `--playlist "<City> Meetup #N"`, then thumbnails. Done when every talk has a
   `youtube.json`, `description.md` carries the watch URL, and the user knows
   the videos are private drafts to publish in YouTube Studio.

## Ground rules

- `raw/` is read-only. Camera files dropped anywhere else (the repo, the
  date folder) get `mv`'d into `$(python3 scripts/meetup_video.py media $E)/raw/` (same disk,
  instant), keeping their original names so a clip traces back to its source.
- Nothing from the media folder is ever committed. What's worth keeping from
  `work/` (QR targets, the cut) goes into the event README.
- Clips are 50 fps (`--fps 50`, the default): half the camera's 100, and normal
  speed in QuickTime, which otherwise plays 100 fps footage as slow-motion.
- The user runs the YouTube `--login` consent in their own browser.
