---
name: speaker-cards
description: Make an event's speaker announcement - a JPG, a GIF and an MP4 of its speakers on the brand's animated background, or one card per speaker. Use when the user asks for speaker cards, a speaker announcement, or an image or video announcing who is speaking at a meetup.
---

# Speaker cards

`scripts/speaker_cards.py` reads the event's speakers from the website's
`event.json` and writes the announcement. Run it from this repository's root.

1. **Check the speakers are in `event.json`**
   (`../website/content/<date>/event.json`): each needs `name`, `title` and
   `photo`. A missing speaker or a wrong role is fixed there, not here; a
   missing photo goes in with the `web-photos` skill. Done when the script no
   longer stops on one.
2. **Render**: `python3 scripts/speaker_cards.py <date-or-luma-slug>` makes one
   picture of all the speakers; add `--each` for a portrait card per speaker,
   `--line "…"` to replace the city and date beside the logo. It prints the
   files it wrote, under `<media>/<date>/speakers/`.
3. **Look at the JPG** before handing the set over: a face cropped by its
   square, a role too long for its column. A bad crop is fixed by a better
   headshot (`web-photos`). Done when the JPG reads well and the GIF and MP4
   are beside it.

For a layout this does not make, the website's `brand-image` skill renders any
of the builder's presets.
