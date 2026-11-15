---
name: recap-cover
description: Make the cover image for an event's Substack recap - a meetup photo in the brand's blue with the event's name and date, 1920x1080. Use when the user asks for a Substack cover, a recap cover or a post image for a meetup, and after publishing a new event's gallery.
---

# Recap cover

`scripts/recap_cover.py` writes the picture a recap post shows on Substack and
in a shared link. Every event gets one, in one fixed style. Run it from this
repository's root.

1. **Check the event has a gallery with a cover**: one photo flagged `cover`
   in `content/<date>/gallery.tsv` and published (the `web-photos` skill). The
   script stops and says so when there is none.
2. **Render**: `python3 scripts/recap_cover.py <date-or-luma-slug>`. It prints
   the file it wrote, `<media>/<date>/cover/recap.jpg`.
3. **Look at it**: people should be easy to see, and the name and date should
   not sit across a face. If they do, or the photo is a weak one, pick another
   from the gallery with `--photo <number>` (its number on the website). Done
   when the picture reads well at the size of a link preview.

The style is fixed: change it in the script for every event, not for one. For
any other branded picture, the website's `brand-image` skill.
