---
name: agentic-engineering-description
description: Talk descriptions in the Agentic Engineering house format — linked title, one-line summary, Main Takeaways, speaker links. Use when turning a talk transcript into a description, a meetup recap, a YouTube description, or the Substack write-up.
---

# Talk description

The output sits in a list beside every previous talk on
[agnteng.substack.com](https://agnteng.substack.com/). Looking like it belongs
matters more than being good in isolation, and a reader scans one in about
twenty seconds.

**Read `references/examples.md` before writing.** Real descriptions from
past events. The voice is not reconstructable from the
template alone — the examples are what make a draft land.

## Template

This skill owns the format. Write it as markdown, the way Substack takes it
when pasted (and as `description.md` in a talk folder, which
`scripts/youtube_md.py` turns into the YouTube description):

```
### [Talk Title](video-url)

One sentence: Speaker Full Name + active verb + what the talk covers and how.

**Main Takeaways**

*   Bullet 1
*   Bullet 2
*   Bullet 3
*   Bullet 4

Speaker's [X](url), [GitHub](url), [LinkedIn](url)

Mentioned: [Product](https://…), [repo](https://github.com/…), [QR: page](https://…)
```

- "Main Takeaways" is the only heading inside the description. No prose
  around it.
- The socials line starts with the speaker's first name and `'s`; that is
  how `youtube_md.py` finds it. Any link a speaker wants on YouTube (their
  company, say) goes here, not only in the YouTube text.
- `Mentioned:` lists the products, repos and QR targets the talk names or shows,
  in the order they come up. Omit the line when there are none.
- The examples in `references/examples.md` were copied from the rendered
  Substack page, so they show bare lines; the structure is the same.

## What separates a real one from a generated one

This is the whole job, and the first draft usually fails it.

**Bullets carry specifics, not definitions.** The real ones read like someone's
notes: *"Over 15 million payments totaling $1M processed monthly"*, *"A Figma
plugin reduced screen context from 17,000 to 1,400 tokens"*, *"AI burnout never
hits while you type. It hits at 9pm, Sunday evening."* A draft that opens a
bullet with "An agent is a model plus a harness" has reached for the textbook
instead of the talk.

**Go back to the transcript for the detail.** The concrete number, the named
tool, the thing that broke, the speaker's own phrasing. A bullet that could have
been written without watching the talk is the failure mode.

**Let them vary.** Four bullets of identical length and shape reads as
generated. Some are one clause, some two sentences.

**Keep the speaker's edge.** Opinionated claims survive intact. Smoothing
*"They're out to get you"* into neutral summary-speak loses the point.

## Rules

- **Four bullets.** Five only when a fifth idea genuinely stands alone.
- **15 words maximum per bullet.** Count them. Over, cut qualifiers.
- **90–130 words total.** If long, cut bullets before the summary sentence.
- Order: thesis, then mechanism, then the war story or number, then the
  prescription.
- The summary sentence opens with the speaker's full name and an active
  present-tense verb — *shows, breaks down, walks through, demos, argues* — and
  names both the subject and the method.

## Titles

Short and punchy, often a pun, a question, or a flat claim: *Faster Isn't Free*,
*Nobody Reviews 4,093 PRs a Month*, *Mind as Model*. Speakers rarely announce
one, so propose it in that voice and flag it as proposed.

## Missing metadata

Write the description anyway. Use placeholders for video URLs and social links,
and list what is missing at the end. A platform a speaker does not have is
omitted from the line entirely rather than left as a dead link. Never guess a
handle.
