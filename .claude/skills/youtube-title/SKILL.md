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

3. **Draft hooks for each title** by the hook rules and "How to find one"
   below. Start from the thesis you wrote in step 1, not from the title.

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

The hook is the largest thing on the thumbnail and is read in a glance, before
the title. Its job is to open a question the talk answers, in words nobody
has to decode. The title then says exactly what the video is.

- **Opens a loop.** After reading it a stranger wants to know something: how,
  why, what happened, is that true. A hook that only names the topic
  ("Agents Need Decision Records") closes the loop and gives no reason to
  click. Ask: what question does this leave in someone's head?
- **About the talk's main thing.** The question it opens is one the talk
  spends its time answering. A loop on a passing detail ("It Caught the Wrong
  Day", "It Comes at 9 p.m.") is a trick, and the viewer feels it.
- **Plain and concrete.** Things you can picture and verbs that do something:
  "It Ships. It Flirts.", "Lose Crypto", "Phone Calls". No jargon, no
  acronyms, no abstract advice ("Focus, Not Context"), nothing preachy.
- **Two to four words**, five at most, on one to three lines. Short lines are
  set larger: aim for ten characters a line.
- **Line breaks.** Each line is a phrase, and the lines are of similar
  length. One short word alone on a line beside a long line ("Run", "My") is
  a fault, and so is a break inside a phrase ("My Phone / Calls"). Two
  balanced lines beat three ragged ones.
- **The highlight.** The yellow block sits on the words that carry the point,
  as a whole phrase: "Phone Calls", "Lose Crypto", "Marketing". It never
  sits on a connective or half a phrase ("Focus, Not", "Per", "Calls").
- **Not the title again.** The two may share a word. Together they should say
  more than either alone, and they need not match.
- **True.** The talk must confirm the click. Sharpening a true framing is
  fair ("I Survived" for "I Spent"); promising what the talk does not deliver
  is not.

### How to find one

1. Write the most exaggerated version of what the talk shows, then pull it
   back until every word is true.
2. Draft ten that are properly different, not rewordings. Try these shapes:
   a two-beat contrast ("It Ships. It Flirts."), a contradiction of what
   people assume, a confession or failure, a stake or loss, a number that is
   the talk's main result, a superlative or "myth", X versus Y, a warning.
3. Read each in one second, as if scrolling. Drop any you had to read twice.
4. Before the critic sees them, write down which you expect to win. Compare
   afterwards; the misses teach you the taste.

### What the channel's owner has kept and thrown out

Kept: "It Ships. It Flirts.", "Grey Market AI Tokens", "SaaS Is Becoming an
Agent", "AI Bots Do My Marketing", "Stop Agent Slop", "Give Your Agent Eyes",
"How Agents Lose Crypto".

Thrown out: "It Caught the Wrong Day" and "It Comes at 9 p.m." (a detail, not
the talk), "Real Agents Run Without You" (too many words), "No Names, Still
Identified" (clumsy), "Agents Need Focus, Not Context" (abstract advice),
"A Bot Per Marketing Job" (stiff; they wrote "AI Bots Do My Marketing").

Sources and strength of evidence: `../title-critic/references/best-practices.md`.
