# 0003. `youtube.md` is generated from `description.md`

- Status: Accepted
- Date: 2026-11-13

## Context
Each talk had a Substack description and a YouTube description written by
hand with the same content. They drifted: a missing full stop, a detail on
YouTube only, a different link label.

## Decision
`description.md` is the source. `scripts/youtube_md.py` renders `youtube.md`
from it plus `talk.json` (speaker and tags), and the upload script regenerates
it before every upload. Nobody edits `youtube.md`.

## Consequences
Anything YouTube should show goes into `description.md`. The fitness check
fails when a `youtube.md` is stale.
