# AGENTS.md

Read `README.md` first: it maps the repository. Read the ADRs in `docs/adr/`
that cover what you're changing. A change that contradicts an ADR needs a new
ADR that supersedes it, in the same pull request. Then these rules:

- **This repository is public.** Its files, commit messages, pull requests and
  issues name no internal infrastructure: no secret-store vaults or items,
  secret references, internal repositories or script paths, machine names,
  hostnames, IP addresses or service IDs. Private business material goes to
  the private workspace.
- **Media stays out of the repository.** Video, audio, frames and chunk
  transcripts live in `$AGNTENG_MEDIA/<date>/`. Never commit them, and never
  move them into `content/`.
- **Event data is the website's.** Read `../website/content/<date>/event.json`;
  never copy its values here. A wrong name or role is fixed there.
- **Luma slugs are `ae-<city>-<n>`** (`luma.com/ae-lisbon-6` is Lisbon #6).
  Every script takes a slug where it takes a date. When the website has no
  `event.json` for it yet, `python3 scripts/luma_event.py <slug> --write`
  creates one from the Luma page.
- **Tools and tasks come from `mise.toml`**; `mise tasks` lists them, and CI
  runs the same ones.
- **Fitness checks are the definition of done.** `mise run fitness` before
  every pull request. When something breaks that no check caught, add a check
  to `scripts/fitness.py` as part of the fix.
- **Transcription models change only through the benchmark**
  (`mise run bench -- --models <id>`).
- Recordings → published talks: the `meetup-video` skill. Talk descriptions:
  `agentic-engineering-description`.
