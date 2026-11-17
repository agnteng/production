"""Caption and picture rules every Short shares (house rules, Every Short): talk_clip.py and news_short.py both use
these, each with its own lettering and layout."""
from __future__ import annotations

import re

# A word that belongs with the number before it: "$278 billion" is one caption, never "$278 | billion".
UNITS = {"billion", "trillion", "million", "thousand", "percent", "dollars", "years", "days", "months", "hours", "minutes"}
MIN_CUE = 0.3   # a caption stays up at least this long; a shorter cue merges into the one before it
MAX_HOLD = 2.0  # no picture holds longer than this without a cut, punch-in or new element

# Generated pictures look like a news agency photograph of a real, ordinary place or object.
PHOTO_STYLE = ("Hyperrealistic photojournalism, as a news agency would publish it: a real, ordinary place or object, "
               "shot on a full-frame camera with natural or available light, true colours, realistic textures, slight "
               "grain, candid composition. No text, no logos, no robots, no holograms, no glowing lights, no sci-fi, "
               "no fantasy, no people, no watermark, no photo credit, no agency name.")


# What a picture prompt may not ask for: the photo style can't override a prompt that names it.
NOT_IN_PICTURES = re.compile(r"\b(robots?|androids?|humanoids?|cyborgs?|holograms?|holographic|glowing|futuristic|"
                             r"sci-?fi|fantasy|people|persons?|crowds?|woman|women|men)\b", re.I)


def picture_prompt(prompt: str) -> str:
    """A generated picture's scene, checked against the photo style: a real, ordinary place or object, no people."""
    bad = sorted({m.group(0).lower() for m in NOT_IN_PICTURES.finditer(prompt)})
    if bad:
        import common
        common.die(f"picture prompt asks for {', '.join(bad)} (house rules: a realistic news photo of a real, "
                         f"ordinary place or object, no people): rewrite {prompt!r}")
    return prompt


def bare(w: str) -> str:
    return re.sub(r"[^\w%'$]", "", w).lower()


def is_number(w: str) -> bool:
    return bool(re.match(r"^[$−-]?\d", w))


def show(w: str) -> str:
    """A word as a caption shows it: no commas or full stops (a separator inside a number stays); ?, !, %, ' stay."""
    return re.sub(r"(?<!\d)[,.;:]|[,.;:](?!\d)", "", w)


def merge_short(caps: list[dict]) -> list[dict]:
    """Captions with `start`/`end`/`words`: a cue shorter than MIN_CUE joins the one before it."""
    out: list[dict] = []
    for c in caps:
        if out and c["end"] - c["start"] < MIN_CUE:
            out[-1]["words"] += c["words"]
            out[-1]["end"] = c["end"]
            if "said" in out[-1] and "said" in c:
                out[-1]["said"] += " " + c["said"]
        else:
            out.append(c)
    return out


def srt(cues: list[tuple[float, float, str]]) -> str:
    """Subtitles keep normal punctuation; only the on-screen captions drop it."""
    ts = lambda s: f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:06.3f}".replace(".", ",")
    return "".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(cues, 1))
