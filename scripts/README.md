# Video pipeline

Standard-library Python 3.10+, no packages to install. Needs `ffmpeg`,
`ffprobe` and `zbarimg` on PATH, and Chrome or Chromium for `thumbnail.py`. Credentials come from the environment or the
repo-root `.env`: `OPENROUTER_API_KEY` for transcription and `thumbnail.py --enhance`, `YOUTUBE_CLIENT_ID`
and `YOUTUBE_CLIENT_SECRET` for uploads, and optionally `LUMA_API_KEY`, which
`luma_event.py` uses for the venue Luma hides from the public page. News Shorts also need `ELEVENLABS_API_KEY`
and `NEWS_VOICE_ID` (the channel's news voice) for `tts.py`. The order to run them in, and why, is
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
| `talk_clip.py` | Vertical Shorts from a talk: edit, face-tracked framing, captions, imagery, sound, end card (`talk-clip` skill) |
| `news_short.py` | Vertical news Shorts from a spec: brand scenes, receipts, numbers that move, captions, sound, end card; pre-render checks gate the render (`news-short` skill) |
| `tts.py` | A news Short's voice: ElevenLabs read, checked word for word against the script and re-recorded until it matches, then sped up |
| `receipt.py` | Screenshots an article's headline and the exact sentence a line rests on, with its line boxes for the highlight |
| `news_assets.py` | People as brand-duotone cut-outs, photos cropped 9:16 (duotone or as shot), and realistic generated news photos |
| `short_checks.py` | The house-rule checks every Short runs: clipping, holds, voice against script, legibility sheet |
| `captions.py`, `endcard.py` | What every Short shares: caption rules, the photo style, the end card (`endcard.html`) |
| `align.py` | Word timings by local forced alignment of a transcript to its audio (ADR 0006) |
| `shorts_upload.py` | Uploads rendered Shorts to YouTube from a schedule file, scheduled or at once ("now"); a talk clip's description is composed from the event, a news Short carries its own; `--check` lists Shorts not public after their time |
| `grammar.py` | Corrects the grammar of text written from audio, never its wording, and puts currency signs on money (ADR 0007); `python3 scripts/grammar.py FILE …` for transcripts |
| `youtube_md.py` | Renders each `youtube.md` from `description.md` + `talk.json` |
| `youtube_upload.py` | Uploads the talks as private videos into the event's playlist; `--update` sets title, description and tags on talks already uploaded |
| `thumbnail.py` | Renders a talk's `thumbnail.jpg` from a speaker photo and a hook (`thumbnail.html`, headless Chrome); `--upload` sets it on the video |
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

Every script takes `--help`. Scripts that need packages pin them inline (`photos.py`, `event_photos.py`,
`talk_clip.py`, `news_short.py`, `tts.py`, `receipt.py`, `news_assets.py`, `short_checks.py`): run them with
`mise exec -- uv run`. The browser checks drive the installed Chrome or Chromium (`CHROME_BIN` to choose one); the
hyperframes render uses its own unless `HYPERFRAMES_BROWSER_PATH` names one.
