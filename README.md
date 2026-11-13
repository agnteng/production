# Agentic Engineering: production

The tooling and write-ups for the Agentic Engineering meetups: everything that
happens around an event rather than on the website. A recording goes in; one
clip, transcript, Substack description and YouTube upload per talk come out,
plus the Q&A for the newsletter. Shared so other meetups can borrow it.

The website, the decks and each event's identity (`content/<date>/event.json`)
live in [agnteng/website](https://github.com/agnteng/website), checked out
next to this repository as `../website/`. This repository reads that file and
never copies it.

This repository is public. Credentials live in `.env` (ignored); never commit
one. Every push and pull request is scanned by gitleaks. For the same scan
locally before each commit, run once per clone:

```sh
git config core.hooksPath .githooks   # needs: brew install gitleaks
```

## Layout

| Path | What |
|---|---|
| `content/<date>/` | One event's write-ups: `README.md` (the cut, QR codes, what's missing), one folder per talk (`transcript.md`, `description.md`, `talk.json`, `youtube.md`, `thumbnail.jpg`) and the Q&A folder. |
| `scripts/` | The video pipeline (cut, transcribe, write up, upload) `luma_event.py` (an event's facts from Luma) and `publish_talks.py` (the talks, onto the website). See `scripts/README.md`. |
| `.claude/skills/` | `meetup-video` (recording → published talks) and `agentic-engineering-description` (the house format for a talk description). |
| `docs/adr/` | Decisions about this repository, and why. |

## Media

Camera files, audio, frames, chunk transcripts and clips are never in the
repository. They live in `$AGNTENG_MEDIA/<date>/` (`raw/`, `work/`, one `.mp4`
per talk), the workspace's `media/` unless pointed elsewhere, such as an
external disk. `python3 scripts/meetup_video.py media <date>` prints the
folder.

## Develop

```sh
mise install            # python, gitleaks
mise run fitness        # the repository checks CI runs
mise run bench          # transcription benchmark
```

The scripts also need `ffmpeg`, `ffprobe` and `zbarimg` on PATH.
