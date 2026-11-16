---
name: talk-clip
description: Cut a short-form vertical clip (YouTube Shorts, X, LinkedIn) from a published meetup talk - cold-open hook, beat drop, face-tracked cuts and punch-ins, animated word captions, icons, logos, generated cutaways, sound design and an end card. Use when the user asks for a clip, a Short, a teaser or a social video from a talk, or a content calendar names a talk clip that has no file yet.
---

# Talk → short

The benchmark is top-tier podcast Shorts: a hook in the first second that
pulls you into the content, a visual change every one to three seconds,
sound on the real transitions, a music bed, and big animated captions with
the key phrases coloured. A clip that is the speaker plus subtitles is not a
short.

`scripts/talk_clip.py` builds it (`--help` has the format): Python cuts at the
word, tracks the face, frames and grades; `scripts/short.html`, rendered by
HyperFrames, adds the motion and the end card; `scripts/sfx.py` mixes. Run as
`mise exec -- uv run scripts/talk_clip.py …`. Talks with local footage use
it; the rest are downloaded from YouTube and look soft up close.
HyperFrames only renders: never `hyperframes init` or `transcribe`, which run
Whisper. Transcription is OpenRouter only; word times come from the local
aligner (ADR 0006).

## 1. Choose the moment and write the edit

`words` prints the timed words of the span in `start`/`end`; `text` prints
the clip as the viewer will read it, hook first, a line per kept phrase.

- **Body**: one idea in 25 to 40 seconds. It opens on a line that stands alone
  and ends on its payoff, a claim or a number, never a trailing remark.
  Nothing points at the slides.
- **keep**: the phrases to keep, in order, `[first words, last words]` as
  `words` prints them, or `{"from", "to", "skip": [words], "same sentence":
  true}`. `skip` drops words inside a phrase; `same sentence` lets the caption
  run on across the join. Only the speaker's own words, in their order.
- **Hook**: the strongest line, 2 to 4 seconds, from inside the body: a claim
  that sounds wrong, a number, a question. `{"from", "to", "skip"}`.
- **highlight**: the three to five phrases that carry the idea. A highlight is
  a whole phrase: a modifier always goes with the noun or verb it modifies. A
  number is highlighted with the word after it automatically. Never a word
  said ten times.
- **stickers**: a word and its icon. A Noto 3D emoji code point where one fits
  (`1f914` thinking, `1f916` robot, `1f9e0` brain, `1f4b8` money, `26a0`
  warning, `2705`/`274c` yes/no); `{"icon": "<what it is>"}` to generate one
  in the same 3D style; `{"logo": "<Simple Icons slug>"}` whenever a product
  or company is named. A product shown or described in use can have a
  screenshot of its site as a cutaway instead.

## 2. The grammar pass

Many speakers are not native English speakers. Run `text` and read every
sentence as a viewer reads captions at speed. Each one must be proper English
or read as if it were: fix it by deleting words with `skip` or by moving a
`keep` boundary (a doubled verb, a stray article, "of like", a filler, a false
start, a self-interruption, a side remark to someone in the room). Never add
or reorder words. A sentence that deletion cannot fix stays only if its gist
is instant; otherwise cut it. Then read the whole clip once more top to
bottom: if any stretch sags or needs a second read, cut it.

The render then corrects grammar and puts currency signs on money (ADR 0007),
storing each correction in `clips.json` under `grammar` (as said → as
written). A correction that changes meaning is wrong: edit the entry by hand.

## 3. Plan the imagery

Go beat by beat and ask, for each line, whether a picture makes it land
faster. Write the plan before rendering.

- **inserts**: two or three generated cutaways, 1.5 to 2 s each, at most 30 %
  of the clip, on a setup or an abstract line: `{"on": "<first words>",
  "for": 1.8, "image": "<a concrete scene>"}`. The script adds the house look
  (navy, electric blue, yellow, cinematic 3D); describe the scene only. Never
  on the hook or the payoff: the face carries those.
- **tones**: an old-film sepia wash on a line about the past.
- Images are cached by prompt in the clip's `gen/` folder, about $0.14 each.
  Look at every generated image; a wrong hand, unreadable text or off-brand
  colour means a new prompt.

## 4. Render

```sh
mise exec -- uv run scripts/talk_clip.py render <date> <talk> --id <id>
mise exec -- uv run scripts/talk_clip.py frames <date> <talk> --id <id>
mise exec -- uv run scripts/talk_clip.py remix  <date> <talk> --id <id>   # new music only
```

What the render does on its own, so it is not re-decided per clip:

- **Boundaries**: every cut (the hook's ends, the body's ends, every join)
  falls in the silence between two aligned words, past the last word's decay
  and before the next word's onset. A clip never opens or closes inside a word.
- **Captions**: one to three words, a highlighted phrase as one caption,
  centred in a symmetric box, with a short crisp entrance.
- **Sound**: effects only where the picture really changes (the drop,
  cutaways in and out, the room and wide shots, stickers, the first punch-ins
  on key phrases), one at a time, never a rattle. CC0 recordings in
  `scripts/sounds.json`. The music is the series' trap beat with deep bass
  (`MUSIC_DEFAULT`), clearly audible and ducked while someone speaks. A new
  track is never 8-bit, game-like or orchestral.
- **End card**: after the last word, on the brand's animated field (the talk
  videos' title card): a like button that gets pressed, "Like and follow for
  more", and the logo small at the bottom.
- **Subtitles**: the `.srt` holds the hook and every caption, as written.

## 5. Check before calling it done

On the output, never assumed:

- `text` reads as proper English sentences end to end (section 2), and the
  `grammar` entries in `clips.json` are corrections, not rewrites.
- The frame sheet: the hook builds and fits; the speaker's face is in every
  shot; captions are centred; cutaways and icons land on their words.
- The `.srt`: every caption is what was said, corrected as the `grammar`
  entries say. Fix a misheard word in `work/clips/<talk>.<id>.json`, a wrong
  correction in `grammar`, and render again. A 4-second chunk can drop
  words: re-transcribe a doubtful passage in one longer window and compare.
- The voice track (`<clip>/voice.wav`), re-transcribed: every kept word is
  there and nothing is clipped at either end.

Hand over the `.mp4`, the `.srt`, the YouTube title (the hook as a claim) and
the music credit if the track needs one.
