---
name: youtube-title
description: Write a meetup talk's YouTube title and its thumbnail hook as a pair, from what the speaker actually said. Use when the user asks to write, rewrite, improve or update a video title or a thumbnail hook, or when a talk is written up and has no title yet.
---

# YouTube title

A talk's title and its thumbnail hook are shown side by side in every feed and
are written together. The hook is seen first, large, on the thumbnail: it says
what the talk is about in a few words. The title is read second and says it
exactly, in words people search for. Both must be true to the talk, because
YouTube ranks on watch time and a viewer who was promised something else
leaves.

## Where they live

- The title is the heading of `content/<date>/NN-speaker/description.md`
  (`### [Title](url)`). `youtube.md` and the website take it from there; the
  speaker's name is added after it (`Title - Speaker`), so leave the name out.
- The hook is `thumbnail.hook` in the folder's `talk.json`, set with
  `python3 scripts/thumbnail.py <event> <talk> --hook "Line one|Line two"`.

## Steps

1. **Read the talk**: `transcript.md` in full, then `description.md`. Note the
   thesis in one sentence, the three most specific things said (numbers,
   named tools, a result, a failure, a contradiction) with their timestamps,
   and the words a viewer would type to find this talk. Done when each of
   those is written down with a timestamp.

2. **Draft five titles of different kinds**: one searchable (names the topic
   and the tool in plain words), one claim, one built on a number, one
   question, one "how" or "why". For each, quote the transcript line that
   backs it. A title with no line behind it is dropped.

3. **Draft a hook for each title** by the hook rules below. Start from the
   thesis you wrote in step 1, not from the title: cover the title and ask
   whether the hook alone says what the talk is about.

4. **Check each pair** against the rules below and keep the best three.

5. **Have them critiqued**: run the `title-critic` skill on the three pairs,
   giving it the talk folder. Revise and re-run until one pair gets `ship`,
   or report the best pair with what still holds it back. Never score your
   own titles: the critic's value is that it has not read your reasoning.

6. **Write the winner**: edit the heading of `description.md`, set the hook
   with `thumbnail.py`, then `python3 scripts/youtube_md.py content/<date>`.
   The video itself changes only when the user asks for it:
   `python3 scripts/youtube_upload.py content/<date> --update`.

## Rules for a title

- **True.** Every claim, number and name is in the transcript. Round nothing
  up. If the speaker hedged, the title does not state it flat.
- **The first 40 characters carry it.** Feeds cut titles off, and the
  speaker's name follows, so the topic and the pull both come early.
- **55 characters or fewer** before the speaker's name. YouTube refuses more
  than 100 in total, and the characters `<` and `>`.
- **A stranger understands it.** Name the thing in words people search for.
  Spell out or replace jargon the speaker coined; a product name alone is not
  a title.
- **A reason to click.** A claim, a number, a tension or a question beats a
  label. "Nobody Reviews 4,093 PRs a Month" over "Code Review with Agents".
- **Not clickbait.** No "you won't believe", no ALL CAPS, no emoji, no
  cliffhanger the talk does not resolve.
- **Title Case**, as the channel's other titles. No trailing full stop.
- **Unlike its neighbours.** Read the event's other titles: three talks that
  all start "How I..." hide each other.

## Rules for a hook

The hook is the largest thing on the thumbnail and is read before the title,
often with the title cut off or not read at all.

- **Stands alone.** Someone who sees only the photo and the hook can say what
  the talk is about. Test it by covering the title.
- **The main point, not a moment.** It carries the talk's thesis, result or
  stake. A detail from an anecdote ("It Caught the Wrong Day") or the time
  something happened ("It Comes at 9 p.m.") is not the talk.
- **Names its subject.** No "It", "They" or "This" whose meaning lives in the
  title. Use the noun.
- **A number only with its unit and only if it is the talk's central
  result.** "81% Written by Agents", not "212 Times".
- **Five words or fewer, on one to three lines.** Four is better. Short lines
  are set larger: aim for ten characters a line.
- **Line breaks.** Each line is a phrase, and the lines are of similar
  length. One short word alone on a line beside a long line ("Run", "My") is
  a fault, and so is a break inside a phrase ("My Phone / Calls"). Two
  balanced lines beat three ragged ones.
- **The highlight.** The yellow block sits on the words that carry the point,
  as a whole phrase: "Phone Calls", "Lose Crypto", "Marketing". It never
  sits on a connective or half a phrase ("Focus, Not", "Per", "Calls").
- **Works with the title, without copying it.** It may share the topic word.
  It must not be the title again, and the two together should say more than
  either alone.
- **True**, by the same standard as the title.

Sources and strength of evidence: `../title-critic/references/best-practices.md`.
