# 0003. Thumbnails are rendered, and AI may restore the speaker

- Status: Accepted
- Date: 2026-11-14

## Context
Thumbnails were hand-cropped photos, different every time and unreadable at
feed size. The photos we get of speakers are often phone shots from the back
of the room, where the head is 40 to 100 pixels tall, so a crop tight enough
to work as a thumbnail is soft. An image model can restore such a face
convincingly, which is the risk: the detail it adds is invented.

## Decision
`scripts/thumbnail.py` renders every thumbnail from one design
(`scripts/thumbnail.html`) and from three inputs kept in the talk's
`talk.json`: the photo, where the face is, and a hook of five words or fewer.
The speaker photo is copied to `<media>/<date>/thumbnails/`, outside git like
all media.

`--enhance` may restore the speaker with an image model, under these rules:

- Only a crop of the speaker is sent, through OpenRouter, with no name, talk
  or event attached.
- The result replaces the speaker only. The room comes from the photo, and
  nothing else on the thumbnail is generated.
- An enhanced thumbnail goes on a video only after someone who knows the
  speaker has compared it with the photo and accepted the likeness.
- The model is the one that stayed closest to the source in a side-by-side on
  our own photos (`google/gemini-3.1-flash-image`, against
  `google/gemini-3-pro-image`, which sharpened more and changed expressions
  more). Change it the same way: side by side, on real speaker photos.

## Consequences
Rendering needs Chrome or Chromium and the network. A full-resolution
original is still better than an enhanced copy, and a photo where the speaker
is turned away or hidden is replaced, not enhanced. The `thumbnail-critic`
skill reviews the result before it is uploaded.
