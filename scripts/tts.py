# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.3.5"]
# ///
"""The voice of a news Short, from its script: record, check word for word, speed up.

    mise exec -- uv run scripts/tts.py <dir>             script.txt -> voice.mp3 + words.json
    mise exec -- uv run scripts/tts.py <dir> --speed 1.2

Reads `<dir>/script.txt`. ElevenLabs reads it with the channel's news voice (NEWS_VOICE_ID, ELEVENLABS_API_KEY in
the environment or .env). Each take is transcribed (OpenRouter) and compared with the script word for word; a take
that drops, adds or swaps a word is recorded again, up to four times (house rules: the voice says exactly the
script). The kept take is sped up (default 1.2, pitch kept). `words.json` holds the script's words with rough
times; news_short.py times them exactly by forced alignment of voice.mp3 (ADR 0006).
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

import common
import short_checks
from common import die

MODEL = "eleven_v3"
TAKES = 4


def record(text: str) -> bytes:
    voice = common.secret("NEWS_VOICE_ID")
    body = {"text": text, "model_id": MODEL, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode(),
                                 headers={"xi-api-key": common.secret("ELEVENLABS_API_KEY"), "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=300).read()
    except urllib.error.HTTPError as e:
        die(f"ElevenLabs HTTP {e.code}: {e.read()[:300]!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir", type=pathlib.Path)
    ap.add_argument("--speed", type=float, default=1.2)
    args = ap.parse_args()
    d = args.dir
    text = " ".join((d / "script.txt").read_text().split())
    raw = d / "voice-raw.mp3"
    for take in range(1, TAKES + 1):
        raw.write_bytes(record(text))
        diff = short_checks.voice(raw, text)
        if not diff:
            print(f"  take {take}: says the script word for word")
            break
        print(f"  take {take} differs from the script: {diff[:6]}" + ("; recording again" if take < TAKES else ""))
    else:
        die(f"no take matched the script in {TAKES} tries: listen to {raw} and fix the script's wording")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"atempo={args.speed}", "-b:a", "192k",
                    str(d / "voice.mp3")], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(d / "voice.mp3")],
                               capture_output=True, text=True).stdout)
    words = text.split()
    step = dur / max(1, len(words))
    (d / "words.json").write_text(json.dumps([{"w": w, "t": round(i * step, 3), "e": round((i + 1) * step, 3)} for i, w in enumerate(words)], indent=0))
    print(f"  {d / 'voice.mp3'}: {dur:.1f} s at {args.speed}x, {len(words)} words")


if __name__ == "__main__":
    sys.exit(main())
