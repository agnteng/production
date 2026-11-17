"""Word timings by CTC forced alignment (ADR 0006).

The words come from the OpenRouter transcript; this only finds when each is
said. A wav2vec2 model (facebook/wav2vec2-base-960h, Apache-2.0, as an ONNX
export pinned by revision and checksum) gives the probability of each letter
every 20 ms, and a Viterbi pass finds the most likely path through the known
letters. Nothing here transcribes: a word the model would hear differently is
still placed where the letters fit best.

Accurate to a few frames on clear speech. English letters only: digits are
spelled out for the alignment and the word keeps its written form.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import urllib.request

import numpy as np

REVISION = "a19f851b3d42865797e410752b4c570c871e4825"  # Xenova/wav2vec2-base-960h
FILES = {"model.onnx": "e46614273f03ff4b87923a965e417fa72004825522cb007c9c25633b8475490d",
         "vocab.json": "4178db26b3c7570f6a47f14ac6a1c7b32950b8c2800fb097287e53776934f1c5"}
CACHE = pathlib.Path.home() / ".cache" / "agnteng" / "align"
FRAME = 320 / 16000  # seconds per output frame
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _file(name: str) -> pathlib.Path:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".part")
        urllib.request.urlretrieve(f"https://huggingface.co/Xenova/wav2vec2-base-960h/resolve/{REVISION}/"
                                   f"{'onnx/' if name.endswith('.onnx') else ''}{name}", part)
        if hashlib.sha256(part.read_bytes()).hexdigest() != FILES[name]:
            part.unlink()
            raise SystemExit(f"{name}: unexpected checksum; not using it")
        part.rename(path)
    return path


def _spell(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + _spell(n % 100))
    for size, name in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= size and n // size < 1000:
            return _spell(n // size) + " " + name + ("" if n % size == 0 else " " + _spell(n % size))
    return " ".join(ONES[int(d)] for d in str(n))


def _letters(word: str) -> str:
    """What is said for a written word: "$11,000" is "eleven thousand dollars", "55%" "fifty five percent"."""
    w = re.sub(r"(?<=\d),(?=\d{3})", "", word)
    w = re.sub(r"(?<=\d)\.(?=\d)", " point ", w)
    w = re.sub(r"\d+", lambda m: " " + _spell(int(m.group())) + " ", w)
    w += {"$": " dollars", "€": " euros", "£": " pounds"}.get(word.lstrip("\"'(")[:1], "")
    w = w.replace("%", " percent")
    return re.sub(r"[^A-Z']", "", w.upper().replace("-", "").replace(" ", ""))


def align(audio: np.ndarray, words: list[str]) -> list[tuple[float, float] | None]:
    """(start, end) in seconds from the start of `audio` (16 kHz mono float) for each word, or None
    for a word with no letters to align (a dash, an ellipsis)."""
    import onnxruntime as ort
    vocab = json.loads(_file("vocab.json").read_text())
    session = ort.InferenceSession(str(_file("model.onnx")), providers=["CPUExecutionProvider"])
    x = (audio - audio.mean()) / np.sqrt(audio.var() + 1e-7)
    logits = session.run(None, {session.get_inputs()[0].name: x[None, :].astype(np.float32)})[0][0]
    logp = logits - logits.max(1, keepdims=True)
    logp = logp - np.log(np.exp(logp).sum(1, keepdims=True))

    # Targets: each word's letters, words separated by "|"; remember which word each letter belongs to.
    tokens, owner = [], []
    for k, w in enumerate(words):
        letters = _letters(w)
        if not letters:
            continue
        if tokens:
            tokens.append(vocab["|"])
            owner.append(-1)
        for ch in letters:
            tokens.append(vocab[ch])
            owner.append(k)
    blank = vocab["<pad>"]
    T, L = len(logp), len(tokens)
    if L == 0 or T < L:
        return [None] * len(words)
    S = 2 * L + 1
    ext = np.full(S, blank)
    ext[1::2] = tokens
    skip = np.zeros(S, bool)  # a letter may follow the letter two back when they differ (no blank needed)
    skip[3::2] = ext[3::2] != ext[1:-2:2]
    NEG = -1e30
    dp = np.full(S, NEG)
    dp[0], dp[1] = logp[0, blank], logp[0, ext[1]]
    back = np.zeros((T, S), np.int8)
    for t in range(1, T):
        stay = dp
        step = np.concatenate([[NEG], dp[:-1]])
        jump = np.where(skip, np.concatenate([[NEG, NEG], dp[:-2]]), NEG)
        choice = np.stack([stay, step, jump])
        back[t] = choice.argmax(0)
        dp = choice.max(0) + logp[t, ext]
    s = S - 1 if dp[S - 1] >= dp[S - 2] else S - 2
    path = np.empty(T, np.int64)
    for t in range(T - 1, -1, -1):
        path[t] = s
        s = int(s) - int(back[t, s])

    spans: dict[int, list[int]] = {}
    for t, s in enumerate(path):
        if s % 2 == 1 and owner[s // 2] >= 0:
            spans.setdefault(owner[s // 2], []).append(t)
    return [(spans[k][0] * FRAME, (spans[k][-1] + 1) * FRAME) if k in spans else None for k in range(len(words))]


def spoken(text: str) -> str:
    """A written line as it is said, in lower-case words: "$1.4 billion" is "one point four billion dollars"."""
    t = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    t = re.sub(r"\$(\d+(?:\.\d+)?)\s*(trillion|billion|million|thousand)?", lambda m: f"{m.group(1)} {m.group(2) or ''} dollars", t)
    t = re.sub(r"(\d+)\.(\d+)", lambda m: f"{m.group(1)} point {' '.join(m.group(2))}", t)
    t = re.sub(r"(\d+)%", r"\1 percent", t)
    t = re.sub(r"\d+", lambda m: " " + _spell(int(m.group())) + " ", t)
    return " ".join(re.sub(r"[^a-z' ]", " ", t.lower().replace("-", " ")).split())


def time_words(audio: np.ndarray, words: list[dict], label: str = "voice") -> int:
    """Set each word's `t`/`e` (seconds from the start of `audio`, 16 kHz mono float) by forced alignment, in
    place. Used for voices whose text is known exactly (a TTS read): the service's own timestamps drift, so they
    are only the fallback. When fewer than half the words are placed, the words keep their times and this says so.
    Returns how many words moved by more than 0.12 s."""
    import sys
    spans = align(audio, [w["w"] for w in words])
    placed = sum(sp is not None for sp in spans)
    if placed < len(words) / 2:
        print(f"  {label}: forced alignment placed {placed} of {len(words)} words; keeping the given times", file=sys.stderr)
        return 0
    moved = 0
    for w, sp in zip(words, spans):
        if sp:
            moved += abs(sp[0] - w["t"]) > 0.12
            w["t"], w["e"] = round(sp[0], 3), round(sp[1], 3)
    return moved
