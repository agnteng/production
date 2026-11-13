# Video pipeline

Standard-library Python 3.10+, no packages to install. Needs `ffmpeg`,
`ffprobe` and `zbarimg` on PATH. Credentials come from the environment or the
repo-root `.env`: `OPENROUTER_API_KEY` for transcription, `YOUTUBE_CLIENT_ID`
and `YOUTUBE_CLIENT_SECRET` for uploads. The order to run them in, and why, is
the `meetup-video` skill (`.claude/skills/meetup-video/SKILL.md`).

The scripts take an event as `content/<date>` or `<date>`. Its media (camera
files, audio, frames, chunk transcripts, clips) lives outside the repository in
`~/agnteng-media/<date>/`; set `AGNTENG_MEDIA` to put it elsewhere, such as an
external disk.

| Script | Does |
|---|---|
| `meetup_video.py` | `probe`, `audio`, `frames`, `cut`, `splice`, and `talk` (cut + transcribe + `transcript.md` for one talk) |
| `transcribe_chunks.py` | Chunked transcription with exact timings, a chunk cache, and SUSPECT checks |
| `detect_talks.py` | Finds the talk boundaries from the coarse pass, then refines each to the second |
| `talk_transcript.py` | Renders `transcript.md` from chunk files, later files patching earlier ones |
| `youtube_md.py` | Renders each `youtube.md` from `description.md` + `talk.json` |
| `youtube_upload.py` | Uploads the talks as private videos into the event's playlist |
| `common.py` | Shared: credentials, timecodes, the event folder |

Every script takes `--help`.
