# Architecture decision records

Decisions that affect only this repository. Decisions that bind more than one
repository live in the workspace's `adr/`.

- One decision per file, `NNNN-short-title.md`, numbered in order.
- **An accepted ADR is never edited.** A new ADR supersedes it; only the old
  one's status line changes.
- Read the ADRs that cover a change before making it. A change that
  contradicts one needs a new ADR in the same pull request.
- This repository is public: an ADR names no internal infrastructure.

Template: `# NNNN. Title`, then `Status`, `Date`, and the sections Context,
Decision, Consequences.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-youtube-text-generated.md) | `youtube.md` is generated from `description.md` | Accepted |
| [0002](0002-fitness-checks.md) | Every past failure becomes a fitness check | Accepted |
| [0003](0003-thumbnails-rendered-speaker-may-be-enhanced.md) | Thumbnails are rendered from `talk.json`; AI may restore the speaker, with a likeness check | Accepted |
| [0004](0004-transcripts-are-tidied.md) | Transcripts are tidied with fixed rules, not rewritten | Accepted; amended by 0007 |
| [0005](0005-transcription-openrouter-default-prompt.md) | Transcription through OpenRouter, default prompt only | Accepted |
| [0006](0006-word-timing-by-forced-alignment.md) | Word timing by local forced alignment; transcription stays OpenRouter-only | Accepted |
| [0007](0007-written-text-is-grammatical.md) | Text written from audio is grammatical: transcripts, subtitles, captions; money carries its currency sign | Accepted |
