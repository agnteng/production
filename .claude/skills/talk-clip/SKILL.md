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
  that stands alone and ends on its payoff, ideally a number or a claim, never
  a trailing "so yeah". Nothing points at the slides.
- **keep**: edit the talk at the word. List the phrases to keep, in order,
  each `[first words, last words]` as `words` prints them; the joins fall on
  the quietest instant between words. Add `"same sentence"` to an entry that
  continues the sentence before it, so its caption runs on. Many speakers are
  not native English speakers (user, 2026-11-16): cut false starts, fillers,
  repeated words, self-interruptions and side remarks ("yes, Baptiste") until
  every sentence reads cleanly at speed. Imperfect grammar is fine if the gist
  is instant. Only the speaker's own words, in their own order.
- **Engagement**: read the kept captions top to bottom as a viewer would. If
  the middle sags (setup that goes nowhere, a detour, a sentence that needs a
  second read), cut it. The clip from Sacha Dumay (Lisbon #5) went from 39 s
  to 25 s this way and ends on "Now we have 47 tool".
- **Hook**: the strongest line inside the body, 2 to 4 seconds: a claim that
  sounds wrong, a number, a question. It plays first, then the drop. Name its
  first and last words in `hook` exactly as `words` prints them.
- **highlight**: three to five words that carry the idea; they turn yellow
  and punch the camera in. Never a word said ten times.
- **stickers**: three to five words with an icon each: a Noto 3D emoji code
  point where one fits (`1f914` thinking, `1f916` robot, `1f9e0` brain, `1f4b8`
  money, `1f525` fire, `1f4a5` boom, `26a0` warning, `2705`/`274c` yes/no), or
  `{"icon": "<what it is>"}` to generate one in the same 3D-emoji style, cut out
  of its background.
- **Products and companies**: when the speaker names one, its logo pops in:
  `{"logo": "<Simple Icons slug>"}`, a CC0 mark on a white card. When they
  show or describe a product in use, a screenshot of its site can be a
  cutaway instead; a logo is enough for a passing mention.

## 2. Plan the imagery for the whole clip

Read the body beat by beat and ask, for each line, whether a picture makes it
land faster. Write the plan down before rendering (user, 2026-11-16: "what
imagery would you add, and where").

- **inserts** (cutaways): two or three, 1.5 to 2 s each, at most 30 % of the
  clip, on a setup or an abstract line ("imagine…", "you look at some code"):
  `{"on": "<first words>", "for": 1.8, "image": "<a concrete scene>"}`. The
  image model draws it 9:16 in the house look (navy, electric blue, yellow,
  cinematic 3D), which the script adds; describe the scene, not the style.
  Never on the hook or on the payoff word: the face carries those.
- **tones**: an old-film sepia wash on a line about the past ("back in the
  day"): `{"on": "back in the day", "for": 1.5}`.
- Images are cached by prompt in the clip's `gen/` folder; each new one costs
  about $0.14 (OpenRouter). Look at each generated image before the render is
  done: a wrong hand, unreadable text or an off-brand colour means a new
  prompt.

The lettering is Montserrat Black Italic (OFL) to match the reference Shorts;
the sound is the riser under the hook, a bell ding and sub drop on the drop,
whooshes on cuts and cutaways, pops on stickers, a kick on punch-ins, all CC0
(`scripts/sounds.json`).

## 3. Render

```sh
mise exec -- uv run scripts/talk_clip.py render <date> <talk> --id <id>
mise exec -- uv run scripts/talk_clip.py frames <date> <talk> --id <id>
```

## 4. Check before calling it done

On the output, never assumed:

- The frame sheet: the hook builds line by line and fits the frame; the
  speaker's face is in every frame; no shot is so wide the speaker is small.
- The `.srt` next to the clip: every caption is what was said. Fix misheard
  words in `work/clips/<talk>.<id>.json` (kept while the cut stays) and render
  again. A 4-second chunk can drop words outright: re-transcribe a doubtful
  passage in one longer window and compare. Word times come from forced
  alignment (ADR 0006), so a caption lands within a few hundredths of a second
  of its word once the words are right.
- The sound: the hook ends on its last word, not the next one; the effects
  are audible. You cannot listen, so put the clip through an audio model
  (OpenRouter, `input_audio`) and ask for every sound effect with its time;
  compare with the events the render placed.

Hand over the `.mp4`, the `.srt`, the YouTube title (the hook as a claim) and
the music credit the render prints, which goes in every post's description.
