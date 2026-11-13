# Agentic Engineering Lisbon #4, 23 September 2026

Lunar Strategy, Av. Duque de Loulé 24A. The deck is
[/slides/lisbon-2026-09-23](https://branding.agnteng.com/slides/lisbon-2026-09-23).

## What's here

| Path | What |
|---|---|
| `event.json` | City, venue, Luma ids and speakers; the deck reads it too. |
| `raw/C0083.MP4` | The camera file, 45.9 min, 1080p100. Not committed. |
| `NN-<speaker>/` | One folder per talk: the clip (not committed), `description.md` and `transcript.md`. |
| `article.md` | The Substack recap. |
| `youtube-metadata.json` | What was uploaded to YouTube, before the upload script wrote `youtube.json`. |
| `upload/` | The re-encoded files that went to YouTube. Not committed. |
| `work/` | Audio, chunk transcripts. Scratch, not committed. |

This event predates the current `meetup-video` layout and was moved into it on
2026-11-13. Its transcripts come from the 60s coarse pass, the only full-length
one made at the time. For 30s transcripts, re-run
`python3 scripts/meetup_video.py talk` per talk (Tim and Jeremy are single
spans; Doris's is spliced, below).

## The cut

| Talk | Span | Length | Opens / closes on |
|---|---|---|---|
| 01 Tim Haldorsson | 7:58–18:13 | 10.2 min | "All right. So today I'm going to dive into Grokbot" → "Thanks so much for listening. [applause]" |
| 02 Doris Hernandez Argueta | spliced, below | 10.9 min | "Hi guys, thank you so much for hosting this" → the demo, ending "thank you very much, guys. [applause]" |
| 03 Jeremy Healsmith | 31:18–41:21 | 10.1 min | "Hello, I'm Jeremy" → "thank you very much. [applause]" |

The clips are 100 fps, cut before the skill switched to 50.

**Doris's clip is spliced from four spans.** Her screen share died mid-talk and
she finished without the demo, then came back after Jeremy's talk to show it.
The clip removes both dead patches and appends the recovered demo:

| Span | What |
|---|---|
| 19:23–27:08 | the talk, up to the moment the demo fails |
| 28:10–29:48 | *(62s of the failed demo cut)* takeaways, close, applause |
| 43:07–43:19 | her bridge: "I just want to show you the output" |
| 43:54–45:15 | *(34s of a second fumble cut)* the demo, close, applause |

The demo is **appended rather than injected** into the gap where it failed.
Injecting it there would have her deliver the demo and then say "I can continue
without it" — the surrounding audio contradicts the splice. As a coda it plays
naturally, and her bridge line explains why it's there.

Rebuild it with:

```sh
python3 scripts/meetup_video.py splice content/2026-09-23 \
  --out '02-doris-hernandez-argueta' \
  --span '19:23-27:08' --span '28:10-29:48' \
  --span '43:07-43:19' --span '43:54-45:15'
```

**Q&A is excluded.** The host held questions to the end, so the Q&A at
41:20–43:00 covers all three talks at once and doesn't belong to any single
clip.

## Still missing

- **Video URLs** in each `description.md` (`VIDEO_URL`).
- **Social links** for all three speakers. The deck carried names and
  affiliations only, and nobody gave handles on stage.
- **Titles are proposed, not given.** None of the three announced one.
- **Jeremy's last two bullets** say "Capture fields, not narratives" twice.

## The event

- **Venue:** Lunar Strategy, Av. Duque de Loulé 24A, Lisboa
- **Luma:** [luma.com/kqlbak7w](https://luma.com/kqlbak7w); ids and speakers in `event.json`
- **Deck:** [/slides/lisbon-2026-09-23](https://branding.agnteng.com/slides/lisbon-2026-09-23)

### Speakers, in running order

1. **Tim Haldorsson** — CEO, Lunar Strategy
2. **Doris Hernandez Argueta** — Co-Founder, Altana Network
3. **Jeremy Healsmith** — Co-Founder, Pravi

### Numbers, pulled from Luma on 2026-10-08

- **160** registered
- **37** checked in

Treat the 37 with care. Check-in depends on people actually being scanned at the
door, and 23% of registrations is far below what the room looked like. It is
more likely a measure of how rigorously check-in was run than of attendance. For
the article, either count the room from the video or describe the turnout
without a hard number.

Of the 37 who were scanned in: 22 founders, 9 engineers, 2 PMs, and one each of
VC/investor, marketer, BD/sales and DevRel. Five flagged that they are raising in
the next six months, two looking for a co-founder, two looking for a new role,
one hiring.

### Supporters

lajarre · Misha Kolesnik · ARTEM TOMIUK · Igor · Ryan Dickinson

### Sponsor

HackMeridian — Stellar's hackathon, 25–26 October, Warehouse ONE16 Lisbon.
