---
name: web-photos
description: Put photos on agnteng.com - an event's gallery, a speaker's headshot, or any other photo the site shows. Use when the user shares meetup photos, asks to add, replace or optimize a photo on the website, or a speaker has no photo.
---

# Photos on the website

Every photo the site shows is a web copy made by `scripts/photos.py` (org ADR
0009). Run every command from this repository's root.

## Originals

Originals stay in the night's media folder,
`$(python3 scripts/meetup_video.py media <date>)/photos/`, in any format,
subfolders included. They never enter a repository: phone photos carry GPS
and faces. Photos the user pastes into the chat go there too.

## An event's gallery

The gallery shows every photo the user provides for the night, once each, in
the order they were taken.

1. **Find the night's photos.** Folders the user drops can overlap (a later
   night's folder repeating earlier ones), so match each photo by what it
   shows (the venue, the speaker, the slide) and keep one copy of each, the
   largest. Done when every photo belongs to exactly one night.
2. **Look at every photo and write its alt text** from what it shows. Name a
   speaker only when the photo proves it (their talk title on screen, or a
   face matching their headshot); otherwise "a speaker". Done when every
   photo has its alt text.
3. **List them** in `content/<date>/gallery.tsv`, one `FILE<TAB>alt` per line,
   FILE relative to the night's media folder, `<TAB>plain` after a slide or
   screen that should skip the enhancement.
4. **Publish**: `uv run scripts/event_photos.py <date> --list content/<date>/gallery.tsv`.
   It orders the photos by capture time. Done when it prints one line per photo.
5. **Ship**: in the website, `mise run fitness` shows `ok photos`; commit
   `content/<date>/photos/` and `photos.json` there, and `gallery.tsv` here.
   Done when it is deployed and `mise run fitness:live` passes.

## Speaker headshots

`uv run scripts/photos.py web --no-enhance --max-edge 800 SRC ../website/apps/branding/public/assets/speakers/<first>-<last>.jpg`,
then set `"photo": "/assets/speakers/<first>-<last>.jpg"` on the speaker in
the website's `content/<date>/event.json`. Done when the website's
`mise run fitness` shows `ok photos` and `ok events`.

## Any other photo

New: `uv run scripts/photos.py web SRC ../website/apps/branding/public/assets/photos/<name>.jpg`.
Already on the site but too large or carrying metadata:
`uv run scripts/photos.py optimize FILE …`, once per photo, with
`--no-enhance --max-edge 800` for headshots.

## The enhancement

`uv run scripts/photos.py preview SRC OUT.jpg` writes before and after side
by side. For the first photos from a new venue or odd light, show the user
the preview and continue on their yes; a photo the enhancement hurts goes in
with `--plain`.
