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

1. **Look at every original** before choosing. Done when you can say what
   each one shows.
2. **Pick five or six**, the full room first (it leads the gallery), then
   each speaker on stage, people talking, a question from the floor. Sharp,
   well lit, no near-duplicates. Done when you have an ordered list.
3. **Write the alt text** from what the photo shows. Name a speaker only when
   the photo proves it (their name or talk title on screen); otherwise "a
   speaker". Done when every pick has its alt text.
4. **Publish**: `uv run scripts/event_photos.py <date> --photo FILE "alt" …`
   in display order, with `--plain FILE "alt"` in place of `--photo` for a
   slide or screen. Done when it prints one line per photo.
5. **Ship**: in the website, `mise run fitness` shows `ok photos`; commit
   `content/<date>/photos/` and `photos.json` there. Done when it is deployed
   and `mise run fitness:live` passes.

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
