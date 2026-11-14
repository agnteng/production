# 0004. Transcripts are tidied, not rewritten

- Status: Accepted
- Date: 2026-11-14

## Context
Transcripts carried every "um" and "uh" (about 1,500 in 40,000 words),
sound annotations the model adds ("[laughter]", "[applause]") and stutters
("the the"). They read badly on the website. Org ADR 0004 keeps the
transcription prompt plain, because asking the model for more made it invent
passages, so the cleanup can't happen in transcription.

## Decision
`talk_transcript.tidy()` cleans each paragraph after transcription with fixed
rules: it drops fillers (um, uh, hmm; "ah" stays), sound annotations and
stutters (doubles people say on purpose, like "that that" or "very very",
stay), and fixes the punctuation and capital letter left behind. It never
adds or reorders words. `render()` applies it to every new transcript;
`talk_transcript.py --tidy FILE …` applies it to ones already written.

## Consequences
Transcripts are no longer verbatim; the raw chunks in the media folder are.
The `transcripts` fitness check fails any paragraph that tidy() would still
change, so a transcript written another way can't skip it.
