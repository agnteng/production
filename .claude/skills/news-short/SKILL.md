---
name: news-short
description: Build a news Short - a 30 to 40 s vertical explainer on the week's AI news - from a written script, in the brand's look - receipts, people in duotone, real photos, numbers that move, a verified voice, captions and the end card - gated by automatic checks and short-critic (in the unattended news run, org ADR 0023). Use when a news Short's script is ready to produce, or to rebuild or fix one.
---

# News Short

The story comes first and lives in the content repo: `shorts-writer`'s news branch picks the story, researches it,
writes `script.txt` and `sources.md`, and has post-critic read the script before anything is made. This skill
starts from that folder (`$AGNTENG_MEDIA/<date>/news-<slug>/`) and ends on a render that short-critic has passed,
or in the unattended news run on its best version (org ADR 0023). Every Short follows the house rules
(`../short-critic/references/house-rules.md`: **Every Short** and **News Shorts**); read them before building, and
the components in `references/components.md`. Run every script as `mise exec -- uv run scripts/<name>.py …` from
the repo root; each takes `--help`.

## 1. Receipts

For every claim in the script, the sentence it rests on, from the page in `sources.md`:
`receipt.py <dir> <name> <url> "<the exact sentence or phrase>"` (`--head "<headline start>"` when the page's
`<h1>` isn't the headline). Look at each `<name>-head.png` and `<name>-para.png`: the headline is the outlet's,
the phrase is boxed (the script reports how many lines), and nothing covers it. A page that won't give its
sentence (paywall, PDF) gets a different source, or the line is cut from the script.

Done when every claim has a receipt you have looked at.

## 2. People and pictures

- The public figures the story names: `news_assets.py person <dir> <name> <photo>` from a freely licensed photo
  (Wikimedia Commons), its author and licence noted in `sources.md` for the description's credits.
- Places and objects: a real photo (`raw` or `photo` with a crop that keeps the subject), or
  `news_assets.py generate` for a realistic news photo, then `raw` to crop it.

Look at every picture at phone size: it reads on its own, with no person the story doesn't name.

## 3. Voice

`tts.py <dir>`: the channel's news voice reads `script.txt`; every take is compared word for word with the
script and recorded again until it matches; the kept take is sped up 20%. Done when it reports a take that says
the script word for word. A script that no take can say cleanly gets reworded in the content repo.

## 4. Spec and build

Write `<dir>/spec.py` (format in `scripts/news_short.py --help`, components in `references/components.md`):
one scene per beat of the script, each showing the fact being said, the picture types mixed. Then:

1. `news_short.py <dir> --no-render`: aligns the words to the voice, lays out the captions and runs the
   **pre-render checks** (fit, holds, the screen repeating the captions, receipts alone, two receipts in a row,
   the picture mix). Fix the spec until they pass; `--force` is for a failure you have decided to keep, said
   to the owner.
2. Look at one frame per scene (`npx hyperframes snapshot <dir>/build --at …`) before rendering.
3. `news_short.py <dir>`: renders, mixes and writes `<NAME>.mp4`, its `.srt` and `legibility.png`, and copies them
   with the spec and script to `<dir>/versions/v<n>/`. Read every tile of the legibility sheet.

## 5. short-critic

Run `short-critic` on the render with its folder and save its report as that render's
`<dir>/versions/v<n>/critic.md`. Fix what it finds, as general rules first: a defect no house rule covers is added
to the house rules, worded for every Short, not just this one (in the unattended news run, proposed in the run's
report instead). Repeat until it says `post` or only judgement calls are left. The unattended news run follows org
ADR 0023 instead: two rounds at most, fewer when one stops improving the Short; a claim a critic questions is fixed
and re-rendered without another round; a `redo` drops the story. If an earlier version was better, it is rendered
again from its kept spec and script, so the latest render is the one scheduled. Only then does the owner see it.

## 6. Publish

Only once the render is passed: by the owner, or, in the unattended news run, as its best version with every claim
a critic questioned fixed to its sources (org ADR 0023). The title and description are in the folder's
`youtube.json` (written by `shorts-writer` through `title-critic`). Pull `content`, then add the schedule entry
(`content/shorts.json`): `video` (its path under `$AGNTENG_MEDIA`, `<date>/news-<slug>/<NAME>.mp4`), `title`,
`description` (with sources and photo credits), `hashtags`, `category: "25"` and `publish_at` (a time, or `"now"`).
Log its story in the same commit (the content repository's news log, `shorts-writer` step 11), push, and copy the
render to where the upload runs if it was built elsewhere (the workspace's `shorts:push`). Only the scheduled
upload job writes `video_id`: it uploads the entry and records its id.

## Open items

- Looping the last frame into the first works against the end card today; a way to loop news Shorts is a later
  change, not a rule yet.
