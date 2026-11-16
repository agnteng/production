# Video pipeline

Standard-library Python 3.10+, no packages to install. Needs `ffmpeg`,
`ffprobe` and `zbarimg` on PATH, and Chrome or Chromium for `thumbnail.py`. Credentials come from the environment or the
repo-root `.env`: `OPENROUTER_API_KEY` for transcription and `thumbnail.py --enhance`, `YOUTUBE_CLIENT_ID`
and `YOUTUBE_CLIENT_SECRET` for uploads, and optionally `LUMA_API_KEY`, which
`luma_event.py` uses for the venue Luma hides from the public page. The order to run them in, and why, is
the `meetup-video` skill (`.claude/skills/meetup-video/SKILL.md`).

The scripts take an event as `content/<date>`, `<date>` or its Luma slug. Its media (camera
files, audio, frames, chunk transcripts, clips) lives outside the repository in
`$AGNTENG_MEDIA/<date>/`, the workspace's `media/` unless `AGNTENG_MEDIA` points
elsewhere, such as an external disk.

| Script | Does |
|---|---|
| `meetup_video.py` | `probe`, `audio`, `frames`, `cut`, `splice`, and `talk` (cut + transcribe + `transcript.md` for one talk) |
| `transcribe_chunks.py` | Chunked transcription with exact timings, a chunk cache, and SUSPECT checks |
| `detect_talks.py` | Finds the talk boundaries from the coarse pass, then refines each to the second |
| `talk_transcript.py` | Renders `transcript.md` from chunk files, later files patching earlier ones |
| `youtube_md.py` | Renders each `youtube.md` from `description.md` + `talk.json` |
| `youtube_upload.py` | Uploads the talks as private videos into the event's playlist; `--update` sets title, description and tags on talks already uploaded |
| `thumbnail.py` | Renders a talk's `thumbnail.jpg` from a speaker photo and a hook (`thumbnail.html`, headless Chrome); `--upload` sets it on the video |
| `talk_clip.py` | Cuts a vertical clip from a published talk for Shorts, X and LinkedIn: the speaker full screen, word-by-word captions, `.srt`. Run with `uv run` (`talk-clip` skill) |
| `speaker_cards.py` | Renders an event's speaker announcement (JPG, GIF, MP4) from the speakers in the website's `event.json` (`speaker-cards` skill) |
| `recap_cover.py` | Renders the cover image of an event's Substack recap from the gallery's cover photo (`recap-cover` skill) |
| `import_youtube.py` | Brings talks already on YouTube into `content/<date>/`, links from the Substack recap, and with `--transcribe` their transcripts |
| `photos.py` | Web copies of every photo on the site: `web`, `optimize`, `preview` (org ADR 0009) |
| `event_photos.py` | Publishes an event's gallery through `photos.py` (org ADR 0008) |
| `publish_talks.py` | Writes the talks, the Q&A and the event's main takeaways (`takeaways.md`) into the website's `content/<date>/`; asks YouTube (yt-dlp) for each video's publish date and length |
| `luma_event.py` | An event's date, city, number, venue, speakers and time zone from its Luma page; `--write` fills the website's `event.json` |
| `fitness.py` | Fitness checks: internal names, media, generated text |
| `bench_transcription.py` | Scores transcription models against trusted references (`bench/<date>.json`) |
| `common.py` | Shared: credentials, timecodes, the event folder, Luma slugs |

Every script takes `--help`. `photos.py` and `event_photos.py` pin their packages inline: run them with `uv run`.
