# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.3.5", "playwright==1.55.0"]
# ///
"""The house-rule checks every Short runs (short-critic/references/house-rules.md, "Checked on every build").

talk_clip.py and news_short.py call these after building the page (clipping, holds) and after rendering (legibility,
voice). Each returns a list of problems; empty means the check passed.

    uv run scripts/short_checks.py voice <voice.mp3|wav> <script.txt>    the voice says exactly the script
"""
from __future__ import annotations

import base64
import difflib
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import captions  # noqa: E402
import common  # noqa: E402


# ------------------------------------------------------------------ holds

def holds(events: list[float], start: float, end: float, limit: float = captions.MAX_HOLD) -> list[tuple[float, float]]:
    """Stretches longer than `limit` between `start` and `end` in which nothing new appears on screen."""
    ev = sorted({start, end, *(t for t in events if start <= t <= end)})
    return [(round(a, 2), round(b, 2)) for a, b in zip(ev, ev[1:]) if b - a > limit]


# --------------------------------------------------------------- clipping

CLIP_JS = """([times, sel, timeline]) => {
  const tl = window.__timelines[timeline], out = [];
  for (const t of times) {
    tl.seek(t, false);
    document.querySelectorAll(sel).forEach((e) => {
      for (let a = e; a && a !== document.body; a = a.parentElement) {
        const s = getComputedStyle(a); if (s.visibility === 'hidden' || s.opacity === '0') return; }
      let r = e.getBoundingClientRect(); if (!r.width) return;
      if (e.matches('.counter, .big') || (getComputedStyle(e).display === 'block' && r.width >= 1000)) { const g = document.createRange(); g.selectNodeContents(e); r = g.getBoundingClientRect(); }  // text, not its box
      const over = Math.max(-r.left, r.right - 1080, -r.top, r.bottom - 1920);
      if (over > 6) out.push(`${t}s ${e.className || e.tagName} "${(e.textContent || '').trim().slice(0, 30)}" off by ${Math.round(over)}px`);
    });
  }
  return [...new Set(out)];
}"""


def clipping(page: pathlib.Path, times: list[float], selectors: str, timeline: str) -> list[str]:
    """Every element matching `selectors` stays inside the 1080x1920 frame at each of `times` (the page's GSAP
    timeline is seeked there). Full-width blocks are measured by their text, not their box."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=common.chrome_binary(), headless=True)
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(page.resolve().as_uri(), wait_until="load")
        pg.wait_for_timeout(2500)
        found = pg.evaluate(CLIP_JS, [sorted(set(round(t, 2) for t in times)), selectors, timeline])
        b.close()
    return found


# ------------------------------------------------------------ legibility

def legibility(video: pathlib.Path, cues: list[dict], band: tuple[int, int], out: pathlib.Path) -> pathlib.Path:
    """One tile per caption cue (`start`, `end`, `last`: the time its last word appears), cropped to the caption band
    (top, height), on one sheet beside the video. Rebuilt from scratch on every render."""
    tiles = out.with_suffix("")
    tiles.mkdir(parents=True, exist_ok=True)
    for old in tiles.glob("c*.png"):
        old.unlink()
    top, height = band
    for i, c in enumerate(cues):
        t = max(c["start"] + 0.02, min(c["last"] + 0.15, c["end"] - 0.08))  # inside the cue, its last word up when there is time
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"crop=1080:{height}:0:{top},scale=540:-1", str(tiles / f"c{i:03d}.png")], check=True)
    cols = 4
    rows = -(-len(cues) // cols)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(tiles / "c%03d.png"),
                    "-vf", f"tile={cols}x{rows}:padding=4:color=magenta", "-frames:v", "1", str(out)], check=True)
    return out


# ----------------------------------------------------------------- voice

def words_said(text: str) -> list[str]:
    """Words as they are spoken, so "$1.4 billion", "1.4 billion dollars" and "one point four" compare equal."""
    import align
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\b(gon|wan)na\b", lambda m: {"gon": "going to", "wan": "want to"}[m.group(1).lower()], text, flags=re.I)
    text = re.sub(r"(\w)['’](s|re|ll|ve|d)\b", lambda m: m.group(1) + " " + {"s": "is", "re": "are", "ll": "will", "ve": "have", "d": "would"}[m.group(2).lower()], text)
    w = [x for x in align.spoken(text.replace("U.S.", "US")).split() if x != "and"]
    return ["one" if x == "a" and i + 1 < len(w) and w[i + 1] in ("hundred", "thousand", "million") else x for i, x in enumerate(w)]


REFUSAL = re.compile(r"content.?(polic|filter)|moderation|flagged|safety", re.I)  # how a content refusal reads


def transcribe(audio: pathlib.Path) -> str:
    """The audio's words. A content-filter refusal often isn't repeated, so it asks up to four times."""
    mp3 = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-ac", "1", "-b:a", "64k", "-f", "mp3", "-"],
                         capture_output=True, check=True).stdout
    body = {"model": "google/gemini-3.8-flash", "messages": [{"role": "user", "content": [
        {"type": "text", "text": "Transcribe this audio verbatim, every word exactly as spoken, nothing else."},
        {"type": "input_audio", "input_audio": {"data": base64.b64encode(mp3).decode(), "format": "mp3"}}]}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {common.openrouter_key()}", "Content-Type": "application/json"})
    why = ""
    for _ in range(4):
        try:
            choice = json.loads(urllib.request.urlopen(req, timeout=300).read())["choices"][0]
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if not (e.code == 403 and REFUSAL.search(msg)):  # a 403 for the key or its budget is a failure, not a refusal
                raise
            why = f"HTTP 403: {msg[:160]}"
            continue
        reason = str(choice.get("finish_reason") or "")
        if REFUSAL.search(reason):  # refused, even when some text came back: a cut transcript can't be compared
            why = f"finish_reason {reason}"
            continue
        if choice["message"].get("content"):
            return choice["message"]["content"]
        common.die(f"the transcriber returned no text (finish_reason {reason or 'none'}): a tool failure, not a refusal")
    common.die(f"the transcriber refused this audio 4 times ({why}), so its voice can't be checked: reword the lines "
               "it objects to, or drop the story")


def voice(audio: pathlib.Path, text: str) -> list[tuple[str, str, str]]:
    """The voice says exactly `text`: every word dropped, added or swapped, as (op, script, heard)."""
    a, h = words_said(text), words_said(transcribe(audio))
    return [(op, " ".join(a[i1:i2]), " ".join(h[j1:j2]))
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=h, autojunk=False).get_opcodes() if op != "equal"]


def report(name: str, problems: list) -> bool:
    print(f"  {name}: " + ("ok" if not problems else f"{len(problems)} problem(s): " + "; ".join(map(str, problems[:8]))))
    return not problems


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "voice":
        sys.exit(0 if report("voice", voice(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]).read_text())) else 1)
    common.die(__doc__.split("\n\n")[-1].strip())
