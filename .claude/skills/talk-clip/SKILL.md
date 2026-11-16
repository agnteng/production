---
name: talk-clip
description: Cut a vertical clip (YouTube Short, X, LinkedIn) from a published meetup talk - the moment, the crop, the hook, burned-in captions and an .srt. Use when the user asks for a clip, a Short, a teaser or a social video from a talk, or a content calendar names a talk clip that has no file yet.
---

# Talk → vertical clip

One talk, one moment, one file that works on all three platforms: 1080x1920
MP4, 3 to 140 seconds, captions burned in and also written as `.srt`. The
tool is `scripts/talk_clip.py` (`--help` has the layout and the file format).
Run it under `mise exec --` so `yt-dlp` is on PATH.

## 1. Choose the moment

Read the talk's `transcript.md`. A clip is one claim with its proof, said
in one go, 45 to 75 seconds:

- It opens on the claim or the number, not on "so" or a slide change.
- It is understood without the rest of the talk: no "as I said", no "this
  one" pointing at a slide the viewer cannot read.
- It ends on a full stop the speaker meant: the payoff, not the next topic.
- Prefer numbers, a before and after, a mistake and its fix, a strong
  opinion. The talk's own takeaways in `description.md` point at them.

Write down `start` and `end` from the transcript's 30-second marks, a few
seconds wide.

## 2. Choose the boxes

```sh
mise exec -- python3 scripts/talk_clip.py sheet <date> <talk> --span 7:00-8:10
```

It downloads the talk from YouTube when there is no local video, and writes
`shorts/<talk>.sheet.png` in the event's media folder: five frames across the
span with a grid labelled in source pixels. Read it, then pick:

- `slide`: the projected screen, edge to edge (`[x, y, w, h]`).
- `speaker`: one box that holds the speaker's head and torso in every frame.
  Speakers walk; widen the box rather than lose them.

## 3. Write the hook and render

Add the clip to the talk folder's `clips.json` (create it if needed):

```json
{"clips": [{"id": "cost", "start": "7:04", "end": "8:11",
            "hook": ["$1 a support chat,", "now 5 to 15 cents"],
            "slide": [470, 40, 1110, 700], "speaker": [1150, 100, 750, 562]}]}
```

The hook is two short lines, the first white, the second yellow. It states
what the speaker said, with their numbers; it never claims more than the
talk does. Then:

```sh
mise exec -- python3 scripts/talk_clip.py render <date> <talk> --id cost
```

`render` moves each end to the nearest pause and writes it back as `cut`.

## 4. Check before calling it done

Done means all of these hold, checked on the rendered file, not assumed:

- The first caption in the `.srt` starts a sentence and the last one ends
  one. If either is cut mid-word, measure the pauses near that end
  (`silencedetect` on `work/clips/<talk>.mp3`) and set `cut` by hand.
- Three frames (start, middle, end) show the speaker inside the lower box
  and the slide readable in the upper one. Grab them with ffmpeg and look.
- No caption shows a misheard name or product. Fix a misheard word in the
  cached chunk file (`work/clips/<talk>.<id>.json`) and render again; the
  chunks are not re-requested.

Then hand over the two paths: the `.mp4` to post and the `.srt` to upload as
captions where the platform takes one.
