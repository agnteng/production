# 0009. Every render of a Short is kept, with what made it

- Status: Accepted
- Date: 2026-11-18

## Context
A Short is rendered several times before it is passed: the critics' fixes, a new voice take, a recut. Each
render overwrote the last, so the owner couldn't compare versions or say which change made a Short better or
worse.

## Decision
- `news_short.py` copies each render's video, subtitles and legibility sheet, with the `spec.py` and `script.txt`
  that made them, into the Short's `versions/v<n>/`. `talk_clip.py` does the same on every render and remix, with
  the clip's spec, plan and sounds, in `shorts/<talk>.<id>.versions/v<n>/`. A render is kept even when a check
  after it fails. The top-level files stay the latest render, which is what gets scheduled.
- `short-critic`'s report on a version is saved beside it, as `critic.md`.
- Versions are media: they stay in the media folder, never in git (org ADR 0002), and aren't copied to where
  the upload runs.

## Consequences
The owner can watch every version and read why each changed. Each version is a full copy, about 45 MB for a news
Short, so the media folder grows with every round.
