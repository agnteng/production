# 0007. Text written from audio is grammatical

- Status: Accepted
- Date: 2026-11-16
- Amends: 0004 (transcripts are no longer only tidied: after tidying, a model
  corrects their grammar)

## Context
Many speakers are not native English speakers, and every speaker slips:
"we have 47 tool", "everyone talk about it", a price said without its
currency. Read on screen or on the website, a slip makes the reader stop. The
user asked (2026-11-16) for every piece of text written from audio, in
transcripts, subtitles and captions, to use correct grammar, and for money to
carry a dollar sign whenever the context is money. ADR 0004 tidies
transcripts with fixed rules and rules out rewriting them, which cannot fix
agreement, plurals or articles.

## Decision
After tidying (ADR 0004), text written from audio is corrected by
`scripts/grammar.py`. A model gets the lines with fixed rules: fix agreement,
singular and plural, articles, verb forms, and a word misheard as one that
sounds alike when the sentence shows which was said; never word choice,
order, tense, meaning, names or numbers. Money is written with its sign; an
amount the context makes money but the speaker gave no currency for is
written in dollars, as the user asked. A guard keeps the original of any line
where the answer is a rewrite: more than a quarter of the words changed (two
in a short line), the length moved by more than three words, a number
changed other than into an amount, or a changed word is neither a form of the
one it replaces nor a function word.

It applies to every `transcript.md`, whose provenance note then says
"grammar-corrected"; the `grammar` fitness check fails a transcript without
it, so a new or re-rendered transcript can't skip it. It applies to clip
captions and subtitles too, whose corrections are stored in the clip's
`clips.json` under `grammar`. The audio is never changed; a clip's captions
show the corrected words at the times the spoken ones were said.

## Consequences
Transcripts and captions are no longer what was said word for word; the raw
chunks in the media folder are. Corrections come from a model, so a new
transcript's are read once before publishing, like its names. Fixing a
correction means editing the transcript, or the clip's `grammar` entry, by
hand. An amount in another currency that the speaker never named is written
in dollars; the reader of that transcript fixes it.
