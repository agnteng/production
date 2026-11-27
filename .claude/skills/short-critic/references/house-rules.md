# House rules for every Short

The rules every Short on the channel follows. **Every Short** applies to all of them; **Talk Shorts** and
**News Shorts** add to it for their format. The maker applies them while building; the builders check what can be
checked by machine; `short-critic` reads the result and lists every breach as a defect. When a rule here and an
older note anywhere else disagree, this file wins.

## Every Short

### Checked on every build

The builders run these and stop on a failure; the critic reads their output first:

- **Sync.** Caption times come from forced alignment of the voice track (ADR 0006), never from a voice service's
  own timestamps, which drift.
- **The voice says exactly the script** (a TTS voice). It is transcribed and compared word for word with the
  script; a dropped, added or swapped word means a new take.
- **Anchors.** Everything timed to a word is timed to that word's one occurrence: a phrase said twice is named
  with the words around it, and scenes only move forward in time.
- **Fit.** Every caption, label, stamp, counter, logo, typed line and big word stays inside the frame in every
  scene.
- **Holds.** A new picture every one to two seconds, never a hold past 2 s: a cut, punch-in, counter step,
  highlight or new element lands at least that often, and it must visibly change the frame (a slow push is not
  a change).
- **Legibility.** One tile per caption, cropped to the caption band, on one sheet beside the render, rebuilt on
  every render. Every tile is read.

### Legibility

Every word on screen reads against whatever is behind it at that frame: a dark jacket, a yellow field, a photo, a
screenshot. A colour that works on the background can vanish over the person in front of it, so legibility is
judged per frame, never per scene. Captions never cross a face.

### Captions

- A caption stays up at least 0.3 s; a shorter cue joins its neighbour.
- A key phrase is highlighted whole, on one line; a number stays in one caption with its unit.
- Captions carry no commas or full stops; question and exclamation marks, percent signs, apostrophes and the
  separator inside a number stay. The `.srt` keeps normal punctuation.

### Every word and picture informs

Every sentence, caption, label, title and picture tells the viewer something they need to understand what
happened. What doesn't is cut: filler, a line that restates, scene-setting, a hedge that carries nothing, an
adjective the fact doesn't need. What these rules ask for on purpose stays: a talk Short's hook said again in its
place, a news Short's closing question.

### The screen adds, never repeats

What is on screen shows what the voice can't: a face, a photo, a number in motion. It shows the fact
being said at that moment, never the one before or after. Each fact is carried in one place at a time: when a
counter, a receipt highlight or a picture already shows it, the caption doesn't highlight it too, and no label
restates the caption. A label is the exception, for a number nothing else explains. A logo appears only when it
says who is acting.

### Numbers move

A number is shown by an animation of what it means, built from real data recorded with the Short's sources: a
count, a line drawn to its value, one number replaced by the next, a "<" between two. It agrees with the voice at
every moment: it lands on or before the spoken figure, and in between it shows only true values (a series steps
through its real points; a single figure lands in one slam; only a running tally counts up). A chart moves the
way the voice does and starts where the voice's "since" starts; its label sits centred under its number, its
dates at the ends of the axis. Two compared numbers each sit under the face or logo they belong to. The code font
is for chart axes only.

- A hedge in the voice ("up to", "about", "could") is carried by the number on screen.

### Every picture reads on its own

A stranger seeing one frame, with no caption and no context, can say what it shows. A crop that hides the
subject, a blur, a duotone that erases a logo, or a screenshot too small to read fails; the fix is a better crop
or a better picture, never a label. Generated pictures look like a news agency photograph of a real, ordinary
place or object: realistic light and texture, no fantasy, robots, glow or sci-fi, no people, and no tag or label
saying they were generated.

### Time

A relative time word ("tonight", "this week") is used only when it stays true for the Short's first 48 hours on
the feed; otherwise the date or the day. A claim that a known event will settle (a listing, a vote, a ruling)
names its date on screen, and the Short is posted before that date.

### The end

Every Short ends on the channel's end card (the brand field, a like button that gets pressed, "Like and follow
for more"), within a second of the last word.

## Talk Shorts

Cut from a meetup talk (`talk-clip` skill):

- Only the speaker's words, in their order; corrections are grammar only (ADR 0007).
- The hook is the strongest line of the body, said first and again in its place.
- The body ends on the speaker's payoff, a claim or a number in their words.
- The series lettering (Montserrat italic, the key phrase large and yellow) is the talk Shorts' signature.
- The speaker's face carries the frame; cutaways sit on setups and abstract lines, never on the hook or the
  payoff.

## News Shorts

Built from the week's AI news (`news-short` skill, story in `shorts-writer`):

### The story

- Lead with the most dramatic thing the sources support, said plainly. Sensational, never false.
- The words that carry the hook are spoken within 2 seconds and not restated later.
- Each beat answers the question the one before it raised; every fact says why it matters. A list of facts is
  not a middle. A story that can't be hooked and threaded is dropped.
- The viewer is American: no "America's" or "US" in front of a US agency, place or person ("the FCC").
- Every sentence has a subject and a verb, the way a person says it out loud (not "Each one a data center." or
  "One working satellite by 2033.").
- Plain words a stranger gets with no context.
- Every company, agency, product and public figure is named, and introduced with what it is or who they are, as it
  bears on the story, in a clause after the name when it first comes up (after the hook, if the hook names it):
  "Brendan Carr, who chairs the FCC"; "Nvidia, which makes AI chips". Never a description in place of the name ("the
  regulator", "Claude's maker"), and no empty label ("rival Amazon"). The same name every time, in the voice, on
  screen and in the title. `tts.py` refuses the stand-ins and labels it knows.
- One claim per sentence; no pronoun that could point at two things.
- A number is the headline figure the sources lead with, in the unit the source counts it in; a ratio is shown as
  it is spoken.
- A cut quote keeps the clause that makes it matter.
- A security story says what a flaw lets an attacker do and who is exposed, never how to trigger it: no payloads,
  inputs or steps.
- One closing question, answerable in a word, over its own picture.

### The sources

- Every claim is in the sources the description lists, and the strongest version they state is the one used.
- What is reported or alleged is said as reported or alleged, and named by who actually said or did it, never by
  the outlet that reported it ("Reuters reports"), in the voice or on screen. `tts.py` refuses the credits it knows.
- Most Shorts show no receipt, and none shows more than one (`news_short.py` refuses a second). A receipt is for the
  one claim a viewer would doubt without seeing it in print: the outlet's headline and the very sentence
  highlighted, both as written, at a size a phone can read, never a whole page, never alone on a colour field (the
  person or place it is about sits below it); a punch-in on it keeps the whole highlighted sentence in frame.
- Private people the story is about stay unnamed and unpictured. Everyone pictured near an allegation is named
  by the voice or the screen. Bystanders in a public photo are fine.

### The pictures

- A mix in every Short: the public figure (brand duotone cut-out), a diagram (a chart that moves, a flow of steps,
  a ratio as icons) and real-world photos.
- Besides the caption, a frame shows figures in two places at most (a counter, a label, a step or a receipt's
  highlighted sentence), and each figure in only one of them. `news_short.py` checks it before rendering.
- The opening frame is the strongest picture with the first caption on it. A hook headline may sit above it in its
  own band when it says something the caption doesn't.

### The voice

The channel's news voice, about 20% above its natural speed, saying the script word for word.
