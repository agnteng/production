# 0007. Text written from audio is grammatical

- Status: Accepted
- Date: 2026-11-16
- Amends: 0004 (its rule that tidying never adds words)

## Context
Many speakers are not native English speakers, and every speaker slips:
"we have 47 tool", "everyone talk about it", a price said without its
currency. Read on screen or on the website, a slip makes the reader stop. The
user asked (2026-11-16) for every piece of text written from audio, in
transcripts, subtitles and captions, to use correct grammar, and for money to
carry its currency sign whenever the context is money. ADR 0004 tidies
transcripts with fixed rules that never add or reorder words, which cannot
fix agreement, plurals or articles.

## Decision
After tidying (ADR 0004), text written from audio is corrected by
`scripts/grammar.py`: a model gets the lines with fixed rules (agreement,
singular and plural, articles, verb forms, currency signs; never word choice,
order, tense, meaning, names or numbers) and a guard keeps the original of any
line where more than a quarter of the words changed or the length moved by
more than three words. It applies to every `transcript.md` and to clip
captions, whose corrections are stored in the clip's `clips.json` under
`grammar`. The audio is never changed; a clip's captions show the corrected
words at the times the spoken ones were said.

## Consequences
Transcripts and captions are no longer what was said word for word; the raw
chunks in the media folder are. Corrections come from a model, so a new
transcript's are read once before publishing, like its names. Fixing a
correction means editing the transcript, or the clip's `grammar` entry, by
hand.
