---
name: talk-clip
description: Cut a short-form vertical clip (YouTube Shorts, X, LinkedIn) from a published meetup talk - cold-open hook, beat drop, face-tracked cuts and punch-ins, animated word captions, emoji pops, effects and sound design. Use when the user asks for a clip, a Short, a teaser or a social video from a talk, or a content calendar names a talk clip that has no file yet.
---

# Talk → short

The benchmark (user, 2026-11-16) is top-tier podcast Shorts: a hook in the
first second that pulls you into the content, suspense, a cut or visual
change every one to three seconds, sound effects on every transition, a music
bed, and animated captions with the key words big and coloured. A clip that
is only the speaker plus subtitles was rejected as amateur.

`scripts/talk_clip.py` builds it (`--help` has the format): Python cuts,
tightens pauses, tracks the face, frames and grades; `scripts/short.html`,
rendered by HyperFrames, adds the motion; `scripts/sfx.py` mixes. Run as
`mise exec -- uv run scripts/talk_clip.py …`. Talks from 2026-11-11 on have
local 1080p50 footage; older ones come from YouTube and look soft up close.
HyperFrames is used only to render: never `hyperframes init` or `transcribe`,
which run Whisper (transcription is OpenRouter only).

## 1. Choose the moment and the hook

```sh
mise exec -- uv run scripts/talk_clip.py words <date> <talk> --id <id>
```

prints the clip's words once `clips.json` has its `start` and `end`.

- **Body**: one idea in 25 to 40 seconds after tightening. It opens on a line
  that stands alone and ends on its payoff. Nothing points at the slides.
- **Hook**: the strongest line inside the body, 2 to 4 seconds: a claim that
  sounds wrong, a number, a question. It plays first, then the drop. Name its
  first and last words in `hook` exactly as `words` prints them.
- **highlight**: three to five words that carry the idea; they turn yellow
  and punch the camera in. Never a word said ten times.
- **stickers**: two to four words with a Noto 3D emoji code point each
  (`1f914` thinking, `1f916` robot, `1f9e0` brain, `1f4dd` memo, `1f4b8`
  money, `1f525` fire, `1f4a5` boom, `26a0` warning, `2705`/`274c` yes/no).

## 2. Render

```sh
mise exec -- uv run scripts/talk_clip.py render <date> <talk> --id <id>
mise exec -- uv run scripts/talk_clip.py frames <date> <talk> --id <id>
```

## 3. Check before calling it done

On the output, never assumed:

- The frame sheet: the hook builds line by line and fits the frame; the
  speaker's face is in every frame; no shot is so wide the speaker is small.
- The `.srt` next to the clip: every caption is what was said. Fix misheard
  words in `work/clips/<talk>.<id>.json` (kept while the cut stays) and render
  again.
- The sound: the hook ends on its last word, not the next one; the effects
  are audible. You cannot listen, so put the clip through an audio model
  (OpenRouter, `input_audio`) and ask for every sound effect with its time;
  compare with the events the render placed.

Hand over the `.mp4`, the `.srt`, the YouTube title (the hook as a claim) and
the music credit the render prints, which goes in every post's description.
