# Video pipeline

Standard-library Python 3.10+, no packages to install. Needs `ffmpeg`,
`ffprobe` and `zbarimg` on PATH. Credentials come from the environment or the
repo-root `.env`: `OPENROUTER_API_KEY` for transcription, `YOUTUBE_CLIENT_ID`
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
| `youtube_upload.py` | Uploads the talks as private videos into the event's playlist |
| `import_youtube.py` | Brings talks already on YouTube into `content/<date>/`, links from the Substack recap, and with `--transcribe` their transcripts |
| `publish_talks.py` | Writes the talks and Q&A into the website's `content/<date>/` |
| `luma_event.py` | An event's date, city, number, venue and speakers from its Luma page; `--write` fills the website's `event.json` |
| `fitness.py` | Fitness checks: internal names, media, generated text |
| `bench_transcription.py` | Scores transcription models against trusted references (`bench/<date>.json`) |
| `common.py` | Shared: credentials, timecodes, the event folder, Luma slugs |

Every script takes `--help`.
