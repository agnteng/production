---
name: talk-clip
description: Cut a vertical clip (YouTube Short, X, LinkedIn) from a published meetup talk - the moment, the speaker framed full screen, big word-by-word captions and an .srt. Use when the user asks for a clip, a Short, a teaser or a social video from a talk, or a content calendar names a talk clip that has no file yet.
---

# Talk → vertical clip

One talk, one moment, one 1080x1920 MP4 that works on YouTube Shorts, X and
LinkedIn. The look is set (user, 2026-11-16, after studying a podcast's
Shorts): the speaker full screen, the camera following their face and cutting
between a wide and a close shot at sentence ends, and big captions of one to
three words. No title band, no name, no slide panel; the hook goes in the
post's text and the YouTube title.

The tool is `scripts/talk_clip.py`; `--help` has the file format. Run it as
`mise exec -- uv run scripts/talk_clip.py …` (`uv` for its packages, `mise`
for `yt-dlp`). Prefer talks from 2026-11-11 on: their local 1080p50 footage
holds up in the close shot; older talks come from YouTube and look soft.

## 1. Choose the moment

Read the talk's `transcript.md`. A clip is one idea said in one go, 25 to 45
seconds:

- It opens on a line that stands alone: a question, a claim, a number. Not
  "so", not "this slide".
- Nothing in it points at the screen: the viewer cannot see the slides.
- It ends on the payoff sentence, before the next topic.

## 2. Write the clip and render

Add it to the talk folder's `clips.json`:

```json
{"clips": [{"id": "why", "start": "3:50", "end": "4:28",
            "highlight": ["why", "weird", "decisions", "context"]}]}
```

`highlight` lists the words shown in yellow: the two or three that carry the
idea. Numbers are yellow anyway. Then:

```sh
mise exec -- uv run scripts/talk_clip.py render <date> <talk> --id why
mise exec -- uv run scripts/talk_clip.py frames <date> <talk> --id why
```

`render` moves the ends to the nearest pause and writes them back as `cut`.

## 3. Check before calling it done

Done means all of these hold, checked on the output, not assumed:

- The `.srt`'s first caption starts a sentence and its last ends one. If not,
  set `cut` by hand (seconds in the talk video) and render again.
- Every caption in the `.srt` is what the speaker said. The captions come
  from a fast pass and mishear names and half-words ("you're the co-").
  Correct the text in `work/clips/<talk>.<id>.json` in the event's media
  folder and render again; that file is kept as long as the cut stays.
- The frame sheet (`frames`) shows the speaker's face in every frame, and
  the close shots are not blurred past recognition.

Hand over the `.mp4` path and the YouTube title you propose for it: a short
hook, the idea of the clip in the speaker's own terms.
