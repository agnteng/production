# Agentic Engineering Lisbon #5, 11 November 2026

Lisbon #5: the previous event, 23 Sep, was #4, and the Luma slug is `lisbon-5`.

The Nest by NEAR, during Web Summit week ("Wet Summit": it stormed).
Luma: [luma.com/lisbon-5](https://luma.com/lisbon-5); ids and speakers in `event.json`.
The deck is [/slides/lisbon-2026-11-11](https://branding.agnteng.com/slides/lisbon-2026-11-11).

## What's here

| Path | What |
|---|---|
| `raw/C0084.MP4`, `raw/C0085.MP4` | Camera files, untouched. One recording that the camera split in two: C0085 starts exactly where C0084 ends. Not committed. |
| `NN-<speaker>/` | One folder per talk: the clip, `transcript.md`, `description.md` (Substack) and `youtube.md`. |
| `04-qa/` | The Q&A, for the newsletter only (not YouTube): `04-qa.mp4`, the full `transcript.md`, and `questions.md`, every question with who answered and what they said. |
| `event.json` | City, venue, Luma ids and speakers; the deck reads it too. |
| `work/` | Audio, chunk transcripts, frames and QR scans. Scratch, not committed. |

Built with the `meetup-video` skill (`.claude/skills/meetup-video/`).

## The cut

Timecodes are on the joined C0084+C0085 timeline (78:35 total).

| Talk | Span | Length | Opens / closes on |
|---|---|---|---|
| 01 Andy Nikulin | 8:36–21:28 | 12:52 | "And we are live. Hey everybody" → "Thank you very much. Good luck." |
| 02 David Mihal | 21:42–32:10 | 10:28 | "Hey, everybody. My name is David Mihal" → "Thank you guys very much. [applause]" |
| 03 Sacha Dumay | 32:41–42:10 | 9:29 | "Hello everyone. My name is Sacha" → "If you have any questions, let me know. [applause]" |

- **The Q&A is its own clip**, `04-qa/04-qa.mp4`, 42:10–1:06:14 (24:04). It
  ran as one session for all three speakers and is in none of the talk
  clips. It runs from the host's "I guess we'll open it up now for Q&A"
  to the closing applause.
- **Andy runs long**, almost 13 minutes, past the 10-minute alarm. Nothing was
  cut from the middle.
- Clips are 50 fps, half the camera's 100.
- **QuickTime "slowing down" the raw files.** The camera shoots 1080p100, and
  QuickTime treats high-frame-rate footage as slow-motion: it plays part of
  the file slowed (the tick strip with two handles) and shows a longer
  duration than the real one. ffmpeg reads the true timing, so the clips play
  at normal speed. At 50 fps, QuickTime doesn't apply slow-motion to them.

Rebuild:

```sh
python3 scripts/meetup_video.py cut content/2026-11-11 \
  --talk 'Andy Nikulin@8:36-21:28' --talk 'David Mihal@21:42-32:10' \
  --talk 'Sacha Dumay@32:41-42:10'
python3 scripts/meetup_video.py cut content/2026-11-11 --first 4 --talk 'QA@42:10-66:14'
```

## Titles

All three are from the speakers' title slides, not proposed:

1. **Cheap ~~Thrills~~ Tokens: A field guide to discounted inference**, Andy Nikulin
2. **Does your agent know "why"?** (kicker: "ADRs in the age of agents"), David Mihal
3. **Your SaaS is becoming an agent** ("What we learned building an AI bookkeeper,
   and why we moved it to Vercel's eve"), Sacha Dumay

## QR codes on screen

Decoded from the frames by `zbarimg`:

| Time | Talk | Target |
|---|---|---|
| 13:04 | Andy | https://newsletter.semianalysis.com/p/anthropic-subscriptions-offer-5x |
| 16:04 | Andy | https://platform.cheaperinference.com/dashboard/models?providers=anthropic&sort=discount |
| 16:04 | Andy | https://xaction.ai/pricing |
| 18:36 | Andy | https://www.getcheapai.com/gemini-4-carbon |
| 19:24 | Andy | https://providerbench.ai/models/deepseek/deepseek-v4-flash-0731/ |
| 19:44 | Andy | https://www.linkedin.com/in/nikouline/ (his closing slide) |
| 41:48 | Sacha | https://sachadumay.substack.com |

Every QR code visible on the contact sheets decoded. None needed a manual retry.

## Speakers and links

| Speaker | Role | Verified links | Not found |
|---|---|---|---|
| Andy Nikulin | Founder & AI product builder, Chatronix | [LinkedIn](https://www.linkedin.com/in/nikouline/) (QR on his slide) | personal X, GitHub |
| David Mihal | Co-founder, Meridian ([trademeridian.co](https://trademeridian.co)) | [X](https://x.com/dmihal) (bio: "Co-founder @Try_Meridian"), [GitHub](https://github.com/dmihal), [davidmihal.com](https://davidmihal.com) | LinkedIn |
| Sacha Dumay | Co-founder & CTO, Cashflowy | [X](https://x.com/dumay_sacha) (bio names Cashflowy and ChatNode), [GitHub](https://github.com/racinger), [Substack](https://sachadumay.substack.com) (QR on his slide) | LinkedIn |

Each link was accepted only through a chain back to the person: a QR code on
their own slide, or an X/GitHub bio that names their company. Not used:
`x.com/AndyNikulin` (a different person), and the many other Meridians
(`trymeridian.com` is an unrelated AI-search company).

The deck (`event.json`) has "Andy Nik". His
slides say Andy Nikulin, so the folder and every write-up use that.
Meridian's site lists David as Head of Product, while his own X bio and the
deck say co-founder. The write-ups use co-founder.

## Still missing

- **Publishing.** The videos and the "Lisbon Meetup #5" playlist are private
  until reviewed in YouTube Studio.
- **Andy's title.** The slide reads "Cheap ~~Thrills~~ Tokens". The
  strikethrough doesn't survive YouTube or a link title, so the write-ups say
  "Cheap Tokens: A Field Guide to Discounted Inference".
