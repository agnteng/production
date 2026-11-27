# /// script
# requires-python = ">=3.12"
# dependencies = ["opencv-python-headless==4.11.0.86", "pillow==12.3.0", "numpy==2.3.5", "rembg==2.0.86",
#                 "onnxruntime==1.31.1", "playwright==1.55.0"]
# ///
"""Build a news Short from its folder: a spec, a verified voice and its assets. The skill is news-short.

    mise exec -- uv run scripts/news_short.py <dir>              build, check, render, mix, check again
    mise exec -- uv run scripts/news_short.py <dir> --no-render  build and run the pre-render checks only
    mise exec -- uv run scripts/news_short.py <dir> --force      render even when a pre-render check fails

Every render is also kept, with the spec and script that made it, in `<dir>/versions/v<n>/` (ADR 0009).

<dir> (`$AGNTENG_MEDIA/<date>/news-<slug>/`) holds `script.txt`, `voice.mp3` + `words.json` (from `tts.py`),
the assets (receipts from `receipt.py`, people and photos from `news_assets.py`) and `spec.py`, which defines:

    NAME     the output's basename
    DISPLAY  [(said, shown)]: spoken words as the caption shows them ("seventy" -> "70")
    HOT      [(phrase, after_phrase or None)]: key phrases, one solid block each
    STARTS   [phrase, ...]: the first words of scenes 2..n (scene 1 starts at 0)
    TITLE    optional {"lines": [{"text", "hot"}], "end": phrase}: a hook headline that is not the caption
    SCENES(cut) -> [scene, ...]  (cut[k]..cut[k+1] bounds scene k)
    EVENTS(cut) -> {"hit"|"whoosh"|"pop"|"ding"|"boom": [t, ...]}

with these helpers already in scope: T(phrase, after=None) the time a phrase is said, at(), copy(), person(),
receipt(), the brand colours Y BL NV WH CO, and json. Scene components: references/components.md in the skill.
Word times come from forced alignment of the voice (ADR 0006), never the TTS service's timestamps.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess

import numpy as np
from PIL import Image

import align
import captions
import common
import endcard
import sfx
import short_checks
import talk_clip as tc
from common import die

HERE = pathlib.Path(__file__).resolve().parent
FONTS = {  # the brand's type (packages/brand): Manrope for words, Kode Mono for chart axes. OFL.
    "Manrope.ttf": ("https://github.com/google/fonts/raw/7af0d90b4d532ffa4b041937b560c6df4e7b1e95/ofl/manrope/Manrope%5Bwght%5D.ttf",
                    "3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6", "Manrope-wght.ttf"),
    "KodeMono.ttf": ("https://github.com/google/fonts/raw/7af0d90b4d532ffa4b041937b560c6df4e7b1e95/ofl/kodemono/KodeMono%5BROND%2Cwdth%2Cwght%5D.ttf",
                     "bd7b11b37524e03e270c7a1726f08cc52cb17e8ebc3f664f9d323dfd9277b311", "KodeMono-ROND-wdth-wght.ttf"),
}
COLOURS = {"Y": "#f9c835", "BL": "#1e2be6", "NV": "#05071e", "WH": "#f4f5ff", "CO": "#ff6e4d"}
CAPTION_BAND = (1230, 330)  # where news captions sit (news_short.html .cap), for the legibility sheet
STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "it", "is", "its", "for", "by", "at", "than"}


class Short:
    def __init__(self, d: pathlib.Path):
        d = d.resolve()
        self.d, self.out = d, d / "build"
        self.out.mkdir(exist_ok=True)
        self.words = json.loads((d / "words.json").read_text())
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(d / "voice.mp3"), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        moved = align.time_words(np.frombuffer(pcm, np.float32), self.words)
        print(f"  aligned {len(self.words)} words to the voice; {moved} moved by more than 0.12 s from the TTS times")

    # --- helpers the spec uses
    def at(self, phrase: str, after: str | None = None) -> int:
        """Where a phrase is said: the first time after `after`, or the only time. A phrase said twice with no
        `after` stops the build, since a timing anchor on the wrong occurrence lands a picture seconds early."""
        start = self.at(after) if after else 0
        for said, shown in getattr(self, "display", []):  # a phrase may be written as said or as shown
            phrase = re.sub(re.escape(said.rstrip(".,?!")), shown.rstrip(".,?!"), phrase, flags=re.I)
        toks = [captions.bare(t) for t in phrase.split()]
        hits = [k for k in range(start, len(self.words)) if [captions.bare(x["w"]) for x in self.words[k:k + len(toks)]] == toks]
        if not hits:
            die(f"not in the voice: {phrase!r}")
        if len(hits) > 1 and not after:
            die(f"{phrase!r} is said {len(hits)} times: add words or after= so the anchor is the one meant")
        return hits[0]

    def T(self, phrase: str, after: str | None = None) -> float:
        return round(self.words[self.at(phrase, after)]["t"], 3)

    def copy(self, src: str | pathlib.Path, name: str | None = None) -> str:
        src = pathlib.Path(src) if pathlib.Path(src).is_absolute() else self.d / src
        name = name or src.name
        shutil.copy(src, self.out / name)
        return name

    def person(self, name: str, x: int, y: int, w: int, **kw) -> dict:
        src = self.d / "people" / f"{name}.png"
        p = {"src": self.copy(src), "x": x, "y": y, "w": w, "ratio": Image.open(src).height / Image.open(src).width}
        if kw.pop("sil", False):
            p["sil"] = self.copy(self.d / "people" / f"{name}-sil.png")
        return {**p, **kw}

    def receipt(self, name: str, top: int, rot: float, mark: float, zoom: list, maxh: int = 1000, w: int = 960) -> dict:
        """A receipt is its headline plus the highlighted sentence at readable size: the paragraph is cropped to the
        highlighted lines with one line either side (without highlights, to its first lines), a tall head to its
        headline."""
        m = json.loads((self.d / f"{name}.json").read_text())
        para = Image.open(self.d / f"{name}-para.png")
        k = para.size[0] / m["width"]
        if m["rects"]:
            pad = 1.2 * m["rects"][0]["h"]
            y0 = max(0, min(r["y"] for r in m["rects"]) - pad)
            y1 = min(m["para"], max(r["y"] + r["h"] for r in m["rects"]) + pad)
        else:
            y0, y1 = 0, min(m["para"], m["width"] * 0.45)
        para.crop((0, int(y0 * k), para.size[0], int(y1 * k))).save(self.out / f"{name}-para.png")
        m = {**m, "para": y1 - y0, "rects": [{**r, "y": r["y"] - y0} for r in m["rects"]]}
        head = Image.open(self.d / f"{name}-head.png")
        if head.size[1] / k > m["width"] * 0.6:
            m["head"] = m["width"] * 0.6
            head = head.crop((0, int(head.size[1] - m["head"] * k), head.size[0], head.size[1]))
        head.save(self.out / f"{name}-head.png")
        total = (m["head"] + m["para"]) * w / m["width"] + 26
        if total > maxh:
            w = int(w * (maxh - 26) / (total - 26))
        return {"head": f"{name}-head.png", "para": f"{name}-para.png", "width": m["width"], "headH": m["head"],
                "paraH": m["para"], "rects": m["rects"], "top": top, "rot": rot, "markAt": mark, "zoom": zoom, "w": w,
                "phrase": m.get("phrase", "")}

    def load_spec(self):
        loader = importlib.util.spec_from_file_location("short_spec", self.d / "spec.py")
        mod = importlib.util.module_from_spec(loader)
        mod.__dict__.update({"T": self.T, "at": self.at, "copy": self.copy, "person": self.person,
                             "receipt": self.receipt, "W": self.words, "D": self.d, "json": json, **COLOURS})
        loader.loader.exec_module(mod)
        return mod

    # --- captions
    def captions(self, spec) -> list[dict]:
        W = self.words
        self.display = getattr(spec, "DISPLAY", [])
        for said, shown in self.display:  # spoken words as the caption shows them
            n, k = len(said.split()), 0
            while k < len(W) - n + 1:
                if [captions.bare(x["w"]) for x in W[k:k + n]] == [captions.bare(t) for t in said.split()]:
                    last = W[k + n - 1]["w"]
                    tail = re.sub(r"[\w'%$]", "", last[len(captions.bare(said.split()[-1])):]) if last.lower().startswith(captions.bare(said.split()[-1])) else ""
                    toks = shown.split()
                    toks[-1] = toks[-1].rstrip(".,?!;:") + tail  # the voice's punctuation, once
                    t0, t1 = W[k]["t"], W[k + n - 1]["e"]
                    W[k:k + n] = [{"w": tk, "t": round(t0 + i * (t1 - t0) / len(toks), 3), "e": round(t0 + (i + 1) * (t1 - t0) / len(toks), 3)} for i, tk in enumerate(toks)]
                k += 1
        for ph, after in spec.HOT:
            k = self.at(ph, after)
            for x in W[k:k + len(ph.split())]:
                x["hot"] = ph
        units, k = [], 0
        while k < len(W):  # a key phrase is one unit; so is a number with its unit word
            h, n = W[k].get("hot"), 1
            while h and k + n < len(W) and W[k + n].get("hot") == h:
                n += 1
            while not h and captions.is_number(W[k + n - 1]["w"]) and k + n < len(W) and captions.bare(W[k + n]["w"]) in captions.UNITS:
                n += 1
            units.append(W[k:k + n])
            k += n
        groups, cur = [], []
        for u in units:  # up to three words a caption, four when a key phrase completes it; a break after punctuation
            if cur and len(cur) + len(u) > (4 if u[0].get("hot") else 3):
                groups.append(cur)
                cur = []
            cur += u
            if u[-1]["w"][-1] in ".,?!":
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        self.voice_end = round(W[-1]["e"] + 0.45, 3)
        caps = []
        for gi, g in enumerate(groups):
            last = gi + 1 == len(groups)
            nxt = self.voice_end if last else groups[gi + 1][0]["t"]
            words = []
            for x in g:  # a key phrase shows as one block, timed on its first word
                if words and x.get("hot") and words[-1]["hot"] == x.get("hot"):
                    words[-1]["w"] += " " + captions.show(x["w"])
                else:
                    words.append({"w": captions.show(x["w"]), "t": round(x["t"], 3), "hot": x.get("hot") or False})
            caps.append({"start": g[0]["t"], "end": nxt if last else min(nxt, g[-1]["e"] + 0.5),
                         "said": " ".join(x["w"] for x in g), "words": [{**w, "hot": bool(w["hot"])} for w in words]})
        return captions.merge_short(caps)

    # --- scenes
    @staticmethod
    def fmt(N: dict, v: float) -> str:
        body = f"{v:,.0f}" if N.get("comma") else (f"{v:.{N['dec']}f}" if N.get("dec") else f"{round(v)}")
        return N.get("prefix", "") + body + N.get("suffix", "")

    def numbers(self, scenes: list[dict]) -> None:
        """A counter shows only true values: a "series" steps through its real points, a running tally ("count")
        may count up, anything else lands in one slam on time. Each is sized to its widest value."""
        for S in scenes:
            for N in S.get("counters", []):
                if "steps" not in N and not N.get("count"):
                    t0, dur = N["at"], N.get("dur", 0)
                    if "series" in N:
                        vals = N.pop("series")
                        N["steps"] = [{"text": self.fmt(N, v), "at": round(t0 + dur * i / max(1, len(vals) - 1), 3)} for i, v in enumerate(vals)]
                        N.setdefault("show", t0)
                    else:
                        N["steps"] = [{"text": self.fmt(N, N["to"]), "at": round(t0 + dur, 3)}]
                        N["show"] = round(t0 + dur, 3)
                texts = [st["text"] for st in N.get("steps", [])] or [self.fmt(N, N["to"]), self.fmt(N, N.get("from", 0))]
                N["size"] = int(min(N.get("size", 250), (400 if N.get("col") else 860) / (0.66 * max(map(len, texts)))))

    @staticmethod
    def events(S: dict) -> list[float]:
        ev = []
        for c in S.get("counters", []):
            ev += [c["at"], c["at"] + c.get("dur", 0)] + [st["at"] for st in c.get("steps", [])]
        for k in ("stamps", "imgs", "words", "typed"):
            ev += [x["at"] for x in S.get(k, [])]
        if S.get("receipt"):
            ev += [S["receipt"]["markAt"]] + [z["at"] for z in S["receipt"].get("zoom", [])]
        if S.get("person"):
            ev += S["person"].get("punch", []) + ([S["person"]["silAt"]] if S["person"].get("silAt") else [])
        if S.get("chart"):
            ev += [S["chart"]["at"] + S["chart"]["dur"] * i / 4 for i in range(5)]
        if S.get("flow"):
            ev += [st["at"] for st in S["flow"]["steps"]]
        if S.get("dots"):
            ev += [S["dots"]["at"]] + ([S["dots"]["hit"]] if S["dots"].get("hit") else [])
        return ev + S.get("shake", []) + S.get("beats", [])

    def fill_holds(self, scenes: list[dict]) -> None:
        """No picture holds over MAX_HOLD: a long gap gets stepped punch-ins of the whole scene."""
        for S in scenes:
            for a, b in short_checks.holds(self.events(S), S["t"], S["end"]):
                n = int((b - a) // (captions.MAX_HOLD * 0.8))
                S.setdefault("beats", []).extend(round(a + (b - a) * (i + 1) / (n + 1), 3) for i in range(n))

    # --- checks before rendering
    def gates(self, scenes: list[dict], caps: list[dict]) -> list[str]:
        problems = []
        times = [S["t"] + (S["end"] - S["t"]) * f for S in scenes for f in (0.35, 0.7, 0.98)]
        clipped = short_checks.clipping(self.out / "index.html", times,
                                        ".stamp, .label, .counter, .img, .typed, .big, .cap .w, #title .ln span, .tick", "news")
        problems += [f"clipped: {c}" for c in clipped]
        problems += [f"hold over {captions.MAX_HOLD} s in scene {i}: {g}" for i, S in enumerate(scenes)
                     for g in short_checks.holds(self.events(S), S["t"], S["end"])]
        words = lambda txt: {w for w in re.sub(r"[^a-z0-9$%. ]", " ", txt.lower()).split() if w not in STOP}
        for i, S in enumerate(scenes):  # the screen adds, never repeats
            said = set().union(set(), *[words(c["said"]) for c in caps if c["start"] < S["end"] and c["end"] > S["t"]])
            shown = [x.get("text", "") for k in ("stamps", "words") for x in S.get(k, [])] + [N.get("label", "") for N in S.get("counters", [])] \
                + [st["text"] for st in S.get("flow", {}).get("steps", [])] + ([S["chart"].get("ticker", "")] if S.get("chart") else [])
            problems += [f"scene {i} repeats the caption: {t!r}" for t in shown if words(t) and len(words(t) & said) / len(words(t)) >= 0.5]
            if S.get("receipt") and not (S.get("person") or S.get("photo") or S.get("counters") or S.get("chart")):
                problems.append(f"scene {i}: a receipt alone on a colour field")
        for i, S in enumerate(scenes):  # figures: in two places at most besides the caption, each in one
            fig = short_checks.figures
            shown = [("counter", fig(" ".join(st["text"] for st in N.get("steps", [])) or self.fmt(N, N["to"])))
                     for N in S.get("counters", [])]  # as shown: numbers() has made each counter's steps
            shown += [("label", fig(x.get("text", ""))) for k in ("stamps", "words") for x in S.get(k, [])]
            shown += [("step", fig(st["text"])) for st in S.get("flow", {}).get("steps", [])]
            if S.get("receipt"):
                shown.append(("receipt", fig(S["receipt"]["phrase"])))
            problems += [f"scene {i} shows {p}" for p in short_checks.crowded(shown)]
        kinds = [("person" if S.get("person") else "photo" if S.get("photo") else "diagram" if S.get("chart") or S.get("flow") or S.get("dots")
                  else "receipt" if S.get("receipt") else "number" if S.get("counters") else "text") for S in scenes]
        if len(receipts := {S["receipt"]["head"] for S in scenes if S.get("receipt")}) > 1:
            problems.append(f"{len(receipts)} receipts ({', '.join(sorted(r.removesuffix('-head.png') for r in receipts))}): one at most")
        missing = [k for k in ("person", "diagram", "photo") if not any(
            S.get(k) or (k == "diagram" and (S.get("chart") or S.get("flow") or S.get("dots"))) for S in scenes)]
        print(f"  picture mix: {' > '.join(kinds)}" + (f" (no {', '.join(missing)})" if missing else ""))
        return problems

    def build(self, render: bool, force: bool) -> None:
        spec = self.load_spec()
        caps = self.captions(spec)
        cut = [0.0] + [round(self.T(p) - 0.06, 3) for p in spec.STARTS] + [self.voice_end]
        if any(b <= a for a, b in zip(cut, cut[1:])):
            die(f"scene starts go back in time: {cut}; make each STARTS phrase unique to its scene")
        scenes = spec.SCENES(cut)
        if len(scenes) != len(cut) - 1:
            die(f"{len(scenes)} scenes for {len(cut) - 1} spans (STARTS has {len(spec.STARTS)} entries)")
        for k, S in enumerate(scenes):
            S["t"], S["end"] = cut[k], cut[k + 1]
        self.numbers(scenes)
        self.fill_holds(scenes)
        duration = round(self.voice_end + tc.END, 3)
        plan = {"duration": duration, "scenes": scenes, "groups": caps, "end": {"t": self.voice_end, "dur": tc.END, "press": tc.PRESS}}
        if getattr(spec, "TITLE", None):
            plan["title"] = {"lines": spec.TITLE["lines"], "end": round(self.T(spec.TITLE["end"]) - 0.06, 3)}
        for name, src in FONTS.items():
            shutil.copy(tc.asset(src), self.out / name)
        shutil.copy(tc.asset(tc.MONTSERRAT), self.out / "Montserrat-Italic.ttf")
        shutil.copy(tc.LOGOS / "ae-mark-white.svg", self.out / "mark.svg")
        shutil.copy(tc.LOGOS / "ae-wordmark-line-white.svg", self.out / "wordline.svg")
        (self.out / "plan.json").write_text(json.dumps(plan, indent=1))
        page = endcard.splice((HERE / "news_short.html").read_text()).replace("__DUR__", f"{duration:.3f}")
        (self.out / "index.html").write_text(page.replace("/*PLAN*/null", json.dumps(plan).replace("</", "<\\/")))
        print(f"{spec.NAME}: {duration} s, {len(caps)} captions, {len(scenes)} scenes")
        print("  " + " | ".join(" ".join(x["w"] for x in c["words"]) for c in caps))
        problems = self.gates(scenes, caps)
        if not short_checks.report("pre-render checks", problems) and not force:
            die("fix the spec, or pass --force to render anyway")
        if not render:
            return
        r = subprocess.run(["npx", "-y", "hyperframes", "render", str(self.out), "--output", str(self.out / "visual.mp4"),
                            "--quality", "high", "--fps", "30"], capture_output=True, text=True)
        if r.returncode or not (self.out / "visual.mp4").is_file():
            die(f"hyperframes render failed:\n{(r.stdout + r.stderr)[-1500:]}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(self.d / "voice.mp3"), "-ar", "48000", "-ac", "2",
                        str(self.out / "voice.wav")], check=True)
        track, _ = tc.music_track(tc.MUSIC_DEFAULT)
        events = {k: list(v) for k, v in spec.EVENTS(cut).items()}
        for k, v in endcard.sounds(self.voice_end, tc.PRESS).items():
            events.setdefault(k, []).extend(v)
        final, sheet = self.d / f"{spec.NAME}.mp4", self.d / "legibility.png"
        sheet.unlink(missing_ok=True)  # never kept beside a render it doesn't belong to
        sfx.mix(self.out / "visual.mp4", sfx.read_audio(self.out / "voice.wav"), track, 0.0, duration, events, final, self.out)
        try:
            # Subtitles keep the voice's own punctuation: the said words, not the caption's.
            final.with_suffix(".srt").write_text(captions.srt([(c["start"], c["end"], c["said"]) for c in caps]))
            short_checks.legibility(final, [{"start": c["start"], "end": c["end"], "last": c["words"][-1]["t"]} for c in caps],
                                    CAPTION_BAND, sheet)
            print(f"  {final}\n  legibility sheet (read every tile): {sheet}")
        finally:
            kept = common.keep_version(self.d / "versions", [final, final.with_suffix(".srt"), sheet,
                                                             self.d / "spec.py", self.d / "script.txt"])
            print(f"  kept as {kept}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir", type=pathlib.Path)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--force", action="store_true", help="render even when a pre-render check fails")
    args = ap.parse_args()
    if not (args.dir / "spec.py").is_file() or not (args.dir / "voice.mp3").is_file():
        die(f"{args.dir} needs spec.py and voice.mp3 (from tts.py)")
    Short(args.dir).build(not args.no_render, args.force)


if __name__ == "__main__":
    main()
