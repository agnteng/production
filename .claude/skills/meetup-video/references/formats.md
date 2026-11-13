# Output formats: questions.md, youtube.md, the upload

`description.md` belongs to the `agentic-engineering-description` skill, which
owns that format. This file covers what is specific to the video pipeline.

## questions.md (the Q&A, for the newsletter)

It goes straight into the newsletter, so it reads on its own; the transcript
is the source, not the output.

- One entry per question, **in the order asked**.
- Heading: `#### <the question, summarised in a line>`, carrying enough of the
  asker's framing that the answer reads without it. The heading is the
  question; the answer goes straight under it.
- No timestamps anywhere in the file.
- Under it, `**<Full Name>:**` and the answer in two to four sentences,
  keeping the speaker's sharpest lines in quotes.
- A question put to the panel gets one `**Name:**` paragraph per answer, in the
  order they answered. A follow-up gets its own `####` straight after.
- Name whoever answered from what the answer says. Audience members stay
  anonymous unless they gave a name.
- Leave out host housekeeping ("who wants to give a talk next time?").
- Fix obvious mishearings of names and products. Mark an inaudible audience
  question `[inaudible]`.

## talk.json → youtube.md

`youtube.md` is generated: `python3 scripts/youtube_md.py content/<date>`
renders it from `description.md` plus `talk.json`, and the upload script does
the same before every upload. Edit `description.md`, never `youtube.md`.

```json
{"speaker": "David Mihal", "tags": ["agentic engineering", "ai agents", "lisbon", "meetup", "…"]}
```

- `speaker` is the full name as on their slides; the title becomes
  `Talk Title - Speaker`.
- Tags: about ten, lowercase; the talk's subject, named tools, and always
  `agentic engineering`, `lisbon` (the city), `meetup`.

What the generator produces, matching the channel (checked 2026-11-12 with
`videos.list`): `Title:` line, the summary, `Main Takeaways` with `- ` bullets
ending in a full stop, the speaker's name and one `Label: url` per social, then
`Mentioned in the talk` and one `Label: url` per link, then `Tags:`. No footer.

The upload script refuses, before uploading: "Agentic Engineering" in the title
(the playlist carries the event), a title over 100 characters, a description
over 5000 bytes, and `<` or `>` anywhere in the description.

## Uploading

```sh
python3 scripts/youtube_upload.py content/<date> --playlist "Lisbon Meetup #N" --dry-run
python3 scripts/youtube_upload.py content/<date> --playlist "Lisbon Meetup #N"
```

- Uploads are **private**: the Data API has no draft state, and an unverified
  API project is locked to private. The user publishes in YouTube Studio.
- Playlist `<City> Meetup #N`, as the channel's existing ones (Lisbon Meetup
  #1–#5, Berlin Meetup #2). The number is the Luma slug (`luma.com/lisbon-5` →
  #5). Reused when it exists, created private otherwise; videos are prepended,
  since the channel lists the last talk first. Category 22 (People & Blogs).
- Writes back: `(VIDEO_URL)` in `description.md` becomes the watch URL, the h1
  of `transcript.md` becomes `# [Title](url)`, and each talk gets a
  `youtube.json`. A talk with a `youtube.json` is never uploaded again, so
  re-running only fills in what's missing.
- Thumbnails: the user supplies a photo of each speaker, usually in front of
  their title slide. Crop to 16:9 with the face and the slide title both in
  frame, scale to 1280×720, save as `NN-*/thumbnail.jpg` (under 2 MB), and look
  at each crop before setting it:
  `ffmpeg -i photo.jpg -vf "crop=W:H:X:Y,scale=1280:720:flags=lanczos" -q:v 2 thumbnail.jpg`.
  The script sets any `thumbnail.jpg` it finds, including on a re-run. Custom
  thumbnails need a phone-verified channel (403 otherwise).
- Auth: `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` in `.env`; the refresh
  token in `~/.config/agnteng/youtube-token.json`, scope `youtube`. When it's
  missing or lacks that scope, the user runs
  `python3 scripts/youtube_upload.py --login` in their own browser.
- Quota: an upload costs 1,600 of 10,000 units a day, so six videos a day.
