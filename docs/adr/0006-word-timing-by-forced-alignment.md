# 0006. Word timing by local forced alignment

- Status: Accepted
- Date: 2026-11-16

## Context
Clips show captions word by word and cut talks at the word. Both need each
word's time to within a few hundredths of a second. The transcript comes in
4-second chunks (ADR 0005), and spreading a chunk's words over its loud
moments put captions up to a second off; with speakers who are not native
English speakers it was visible in every clip. ADR 0005 keeps transcription
on OpenRouter and Whisper and local speech-to-text out; it says nothing about
timing a transcript that already exists. The user chose a local aligner over
a text-to-speech match or keeping the estimate (2026-11-16).

## Decision
Word times come from CTC forced alignment of the OpenRouter transcript
against the audio, run locally (`scripts/align.py`), with
facebook/wav2vec2-base-960h (Apache-2.0) as an ONNX export pinned by revision
and checksum. The aligner only places the words it is given; it never
produces text, and nothing it outputs is used as a transcript. Transcription
stays as ADR 0005 says. When alignment fails, the caller falls back to the
estimate and says so.

## Consequences
A 380 MB model is fetched once. Alignment is in English letters: digits are
spelled out for it, and a word with no letters is placed between its
neighbours. A word missing from the transcript makes its neighbours absorb its
time, so transcript errors are still fixed by hand before a clip is cut.
Cuts can now be made between any two words.
