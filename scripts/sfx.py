"""Sound design for talk clips: recorded effects and the final mix.

The effects are CC0 recordings from Freesound, listed with their pages and
checksums in `sounds.json` and fetched once into ~/.cache/agnteng/sounds. CC0
needs no credit and holds on YouTube, X and LinkedIn alike. A riser ends on the
drop, a sub drop and a bell ding land on it, whooshes peak on cuts, pops on emoji, a kick on
punch-ins, a shutter on flashes; no two within 250 ms (`space`).

The music enters on the drop, sits 12 dB under the speech in pauses and ducks
to 20 dB under while someone speaks, then the mix is normalised to -14 LUFS
with peaks at -1 dBTP.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import urllib.request

import numpy as np

SR = 48000
HERE = pathlib.Path(__file__).resolve().parent
CACHE = pathlib.Path.home() / ".cache" / "agnteng" / "sounds"
# dB against the speech level; set so effects peak 3 to 7 dB above the voice, as in the reference Shorts.
LEVELS = {"ding": -5, "riser": -10, "boom": 0, "whoosh_big": -2, "whoosh": -4, "pop": -3, "hit": -3, "shutter": -8}
# Glue the voice and effects, catch the transient peaks, then normalise: without the limiter the
# effects' peaks cap the gain and the clip lands near -18 LUFS.
MASTER = ("acompressor=threshold=0.1:ratio=3:attack=5:release=150:makeup=2.4,"
          "alimiter=limit=0.55:attack=2:release=60:level=false,loudnorm=I=-14:TP=-1.0:LRA=8")
PRIORITY = ["boom", "riser", "ding", "whoosh_big", "hit", "pop", "shutter", "whoosh"]


def write_wav(path: pathlib.Path, x: np.ndarray) -> None:
    x = np.asarray(x, np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", str(path)],
                   input=x.tobytes(), check=True)


def read_audio(path: pathlib.Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def sound(kind: str, k: int = 0) -> np.ndarray:
    """The k-th recording of a kind, round robin, leading silence trimmed."""
    items = json.loads((HERE / "sounds.json").read_text())[kind]
    s = items[k % len(items)]
    path = CACHE / f"{s['id']}.mp3"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        data = urllib.request.urlopen(urllib.request.Request(s["url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
        if hashlib.sha256(data).hexdigest() != s["sha256"]:
            raise SystemExit(f"{s['url']}: unexpected checksum; not using it")
        path.write_bytes(data)
    x = read_audio(path)
    loud = np.flatnonzero(np.abs(x).max(1) > np.abs(x).max() * 0.02)
    return x[loud[0]:] if len(loud) else x


def space(events: dict[str, list[float]], gap: float = 0.25) -> dict[str, list[float]]:
    """Drop the less important of any two effects closer than `gap`."""
    kept: list[tuple[float, str]] = []
    for kind in PRIORITY:
        for t in sorted(events.get(kind, [])):
            # The riser is a bed under the hook and the ding its peak, both on the boom: they never collide.
            if kind in ("riser", "ding") or all(abs(t - u) >= gap for u, k in kept if k not in ("riser", "ding")):
                kept.append((t, kind))
    out: dict[str, list[float]] = {}
    for t, kind in sorted(kept):
        out.setdefault(kind, []).append(t)
    return out


def _envelope(x: np.ndarray, win: float = 0.05) -> np.ndarray:
    """Speech presence per sample, fast attack and slow release, from 0 to 1."""
    mono = np.abs(x).mean(1)
    k = int(win * SR)
    rms = np.sqrt(np.convolve(mono ** 2, np.ones(k) / k, "same"))
    gate = (rms > np.percentile(rms, 35)).astype(np.float32)
    out = np.empty_like(gate)
    v, att, rel = 0.0, np.exp(-256 / (0.01 * SR)), np.exp(-256 / (0.35 * SR))
    for i0 in range(0, len(gate), 256):
        g = gate[i0:i0 + 256].max()
        c = att if g > v else rel
        v = c * v + (1 - c) * g
        out[i0:i0 + 256] = v
    return out


def _db(x: float) -> float:
    return 10 ** (x / 20)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)) + 1e-9)


def mix(visual: pathlib.Path, voice: np.ndarray, music_path: pathlib.Path, drop: float, duration: float,
        events: dict[str, list[float]], out: pathlib.Path, work: pathlib.Path) -> dict[str, list[float]]:
    n = int(duration * SR)
    v = np.zeros((n, 2), np.float32)
    v[:min(n, len(voice))] = voice[:n]
    env = _envelope(v)
    speech = _rms(v[env > 0.8]) if (env > 0.8).any() else _rms(v)
    bus = v.copy()

    # Music: from the drop, entered on its first loud second, ducked under the voice.
    m = read_audio(music_path)
    level = np.sqrt(np.convolve(np.abs(m).mean(1) ** 2, np.ones(SR // 2) / (SR // 2), "same"))
    entry = int(np.argmax(level > 0.7 * np.median(level[level > 0]))) if len(level) else 0
    d0 = int(drop * SR)
    seg = m[entry:entry + n - d0]
    if len(seg):
        seg = seg / _rms(seg) * speech * _db(-12)
        seg = seg * (1 - (1 - _db(-8)) * env[d0:d0 + len(seg)])[:, None]
        tail = min(len(seg), int(0.25 * SR))
        seg[-tail:] *= np.linspace(1, 0, tail)[:, None]
        bus[d0:d0 + len(seg)] += seg

    events = space(events)
    for kind, times in events.items():
        for k, t in enumerate(times):
            fx = sound(kind, k)
            # A riser grows: level it on its whole length, or its last second ends up far too loud.
            fx = fx / _rms(fx if kind == "riser" else fx[: int(0.5 * SR)]) * speech * _db(LEVELS[kind])
            if kind == "riser":            # ends on the drop, 12 dB further down while anyone speaks
                i = int(t * SR) - len(fx)
                duck = np.ones(len(fx), np.float32)
                a0 = max(0, i)
                duck[a0 - i:] = 1 - (1 - _db(-12)) * env[a0:i + len(fx)]
                fx = fx * duck[:, None]
            elif kind.startswith("whoosh"):  # peaks on the cut
                i = int(t * SR) - int(np.argmax(np.abs(fx).max(1)))
            else:
                i = int(t * SR)
            a, b = max(0, i), min(n, i + len(fx))
            if b > a:
                bus[a:b] += fx[a - i:b - i]

    bus /= max(1.0, np.abs(bus).max() / 0.98)
    write_wav(work / "mix.wav", bus)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(visual), "-i", str(work / "mix.wav"), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", MASTER, "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)
    return events
