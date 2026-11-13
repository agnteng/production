# Traps, with the evidence

Each rule in `../SKILL.md` came from one of these. Read the matching entry when
a rule seems not to apply, or before changing a script that enforces one.

## Timing comes from the chunk grid

A model asked to timestamp 46 minutes of audio drifts, and the drift is
invisible: the text reads fine while the numbers wander. Chunk `i` starts at
`start + i * seconds` because that is where ffmpeg cut it, so timing is exact
by construction and the model is only asked *what* was said.

## Silence detection fails in a live room

`silencedetect` at -30dB found one gap in 46 minutes on 2026-09-23. Forty
people in a room never get that quiet. The transcript is the signal.

## A window past the end of the file gets filled with fiction

ffmpeg produces empty chunks and the model invents speech for them: confident
applause and dialogue for audio that does not exist. `transcribe_chunks.py`
clamps to the real duration.

## A vocabulary prompt produces whole invented passages

On 2026-11-11, 30s chunks sent with a prompt listing speaker names and product
terms came back as 1,000+ words of fluent, on-topic fiction, including a
complete fake panel discussion with all three speakers. The same audio with the
plain default prompt was accurate. Names get fixed afterwards, from the slides.
The old xAI `keyterm` path was removed for the same reason.

## Hallucinations cluster in the Q&A

Quiet audience questions and mic handovers give the model room to fill. On
2026-11-11 the 30s Q&A chunk at 45:10 came back as a plausible answer about
React and MVPs where the speaker was talking about ADR context cost; the coarse
60s pass had it right. Only 36% of that chunk's words appeared in the coarse
pass, against 84% or more for 95% of real chunks, which is where the 0.6
threshold in `transcribe_chunks.suspects` comes from. Another talk's audio
replayed into the Q&A scores 0.45 at most.

## A coarse chunk can be wrong where a fine one is right

The 30:00 coarse chunk on 2026-09-23 reported a Q&A exchange that the 5s pass
showed to be 90 seconds of silence. Shorter windows give the model less room to
drift, so in a boundary dispute the fine pass wins. In a content dispute
(SUSPECT against coarse), re-run at 10s and read all three.

## A talk far off ten minutes is a wrong boundary

On 2026-09-23 the third speaker appeared to run to 45:15, a 14-minute talk. It
was Jeremy's talk ending at 41:10, then the *second* speaker returning at 43:00
to demo what a screen-share failure had stopped her showing live.

## Append late material; read the audio around a splice

On 2026-09-23 the obvious move was to drop the recovered demo into the gap
where it failed, but she says "I can continue without it" moments after where
the demo would sit. Appended after her closing applause it plays as a coda, and
her own bridge line ("I just want to show you the output") explains it.

## Speaker labels from the model are unreliable

It put the host's name on David's answers and Andy's on Sacha's (2026-11-11).

## The deck's name can be a short form

content.ts had "Andy Nik"; his own title and closing slides said "Andy
Nikulin".

## The model returns its own segment markers

`[ 0m5s46ms - 0m9s936ms ]`, relative to the chunk and meaningless in a clip.
`talk_transcript.py` strips them.

## QuickTime "slows down part of the file"

The camera shoots 1080p100. QuickTime treats high-frame-rate footage like
iPhone slow-motion: it draws a slow-mo range and plays the middle slowed, so it
shows 1:32:41 for a 48:41 file. Video and audio durations match; the frame rate
is constant; ffmpeg is unaffected. Clips are cut at 50 fps, a clean halving
that plays at normal speed in QuickTime and on YouTube.

## Several camera files are one timeline

Sony cameras split a long recording into consecutive files with no gap:
C0085's `creation_time` is exactly C0084's start plus its duration. A real gap
would shift every timecode after it, so check the creation times.

## Tooling

- Installing zbar upgraded `x265` and left ffmpeg linked to a missing dylib
  (`Library not loaded: libx265.216.dylib`, exit 134). `brew upgrade ffmpeg`
  fixes it.
- Homebrew's ffmpeg has no `drawtext` filter, which is why contact-sheet times
  live in `sheet-NN.txt`.
- The Sony files carry a timed-metadata track (`rtmd`) mp4 can't hold, so cuts
  map `0:v:0` and `0:a:0` only.
- zsh does not word-split unquoted variables: `for w in "a b c"; do set -- $w`
  passes empty arguments. Write invocations out.
