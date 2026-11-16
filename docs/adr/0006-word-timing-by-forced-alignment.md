# 0006. Word timing by local forced alignment

- Status: Accepted
- Date: 2026-11-16
- Amends: 0005 (a local model may time a transcript, never write one; a clip's
  span gets its own short-chunk pass)

## Context
Clips show captions word by word and cut talks at the word. Both need each
word's time to within a few hundredths of a second. Spreading a chunk's words
over its loud moments put captions up to a second off; with speakers who are
not native English speakers it was visible in every clip. ADR 0005 keeps
transcription on OpenRouter and bars Whisper and local speech-to-text, so
that no local model writes what a speaker said. The user chose a local
aligner over a text-to-speech match or keeping the estimate (2026-11-16).

## Decision
A clip's span is transcribed again on OpenRouter with ADR 0005's model and
plain prompt, in 4-second chunks, so a cut can be placed near any word. Those
chunks get no second pass; their words are read against the talk's checked
`transcript.md` by hand before a clip is cut (`talk-clip` skill).

Word times come from CTC forced alignment of that transcript against the
audio, run locally (`scripts/align.py`), with facebook/wav2vec2-base-960h
(Apache-2.0) as an ONNX export pinned by revision and checksum. The aligner
only places the words it is given; it never produces text, and nothing it
outputs is used as a transcript, which is the line ADR 0005's ban now draws.
When alignment fails or places fewer than half the words, the caller falls
back to the estimate and says so. A model file that fails its checksum stops
the run.

## Consequences
A 380 MB model is fetched once. Alignment is in English letters: numbers,
amounts and percentages are spelled out as said, and a word with no letters
is placed between its neighbours. A word missing from the transcript makes
its neighbours absorb its time, so transcript errors are still fixed by hand
before a clip is cut. Cuts can now be made between any two words.
