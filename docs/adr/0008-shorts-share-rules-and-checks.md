# 0008. Every Short shares one set of rules and machine checks; news Shorts are built from a spec

- Status: Accepted; amended by org ADR 0021
- Amends: 0005 (a TTS voice check's comparison transcript is not bound by the default-prompt rule), 0006 (a TTS voice is aligned against its script)
- Date: 2026-11-17

## Context
Talk Shorts (`talk_clip.py`) were joined by news Shorts: 30 to 40 s explainers on the week's AI news, voiced by
text-to-speech and built from screenshots, photos and animated numbers. A day of owner feedback on the first
news Shorts produced rules that apply to every Short (captions in sync and readable on every frame, nothing
leaving the frame, no picture held past 2 s, numbers that only ever show true values, the end card), and found
defects a person missed but a machine catches: a TTS take that dropped a word, captions half a second off
because the voice service's own timestamps drift, a label running off the screen, two receipts in a row. The
two pipelines had copied each other's end card and caption rules, and the talk render ran none of the checks.

## Decision
- **One rulebook.** `.claude/skills/short-critic/references/house-rules.md` holds every rule, in three parts:
  every Short, talk Shorts, news Shorts. Skills point to it rather than restating it.
- **Shared code.** `captions.py` (caption rules and the generated-photo style), `endcard.py` + `endcard.html`
  (the end card, spliced into each Short's page) and `short_checks.py` (fit, holds, the legibility sheet, and for a TTS
  voice the voice against its script) are used by both builders.
- **Machine checks before people.** A build runs the checks; a pre-render failure stops a news Short unless
  forced; `short-critic` runs on every render before the owner sees it.
- **News Shorts are built from a spec** (`news_short.py`, a `spec.py` per Short in its media folder): scenes
  bound to the moment their words are said. The voice (`tts.py`) is ElevenLabs, transcribed and compared word
  for word with the script, recorded again until it matches; caption times come from forced alignment of that
  voice (ADR 0006), never the service's timestamps. The transcript in that check is a comparison, not a
  published transcript, so ADR 0005's default-prompt rule does not apply to it.
- **One schedule.** News Shorts go through `shorts_upload.py` and `content/shorts.json` with their own video
  path and description, scheduled or published at once.
- **Generated pictures** in every Short look like a realistic news photograph of a real, ordinary place or
  object, with no people and no on-screen tag.

## Consequences
A rule added after a review lands in one file and reaches both formats. Talk renders now print the shared checks
and leave a legibility sheet; their cutaways change from a stylised 3D look to realistic photos, and their
framing changes at most every 2 s. News Shorts need `ELEVENLABS_API_KEY` and `NEWS_VOICE_ID`, Chrome or Chromium
for the receipts and the fit check, and Playwright (pinned inline, driving the installed browser).
