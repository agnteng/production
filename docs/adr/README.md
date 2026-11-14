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
