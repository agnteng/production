# News Short components

A scene in `spec.py` is a dict; `cut[k]`..`cut[k+1]` bounds it. Times are seconds, usually `T("<words>")`, the
moment those words are said. Every component sits on the scene's `bg` (`"blue"`, `"navy"` or `"yellow"`, each
with the brand dither). Colours: `Y` yellow, `BL` blue, `NV` navy, `WH` white, `CO` coral.

| Key | What it shows | Notes |
|---|---|---|
| `person` | `person(name, x, y, w, push=, punch=[t], sil=True, silAt=t)`: a duotone cut-out | Bottom-anchored; it drops below the caption band when its face would cross it. `sil` flickers to a silhouette at `silAt` (someone gone). |
| `photo` | `{"src": copy("x.jpg")}` full-bleed, slow push | Add `"scrim": True` so captions sit on a dark band. |
| `receipt` | `receipt(name, top, rot, mark, zoom, maxh=, w=)` | `mark`: when the highlight sweeps. `zoom`: `[{"at": t, "s": 1.3, "mid": 520}]`, a punch-in that keeps the whole highlight in frame. Pair it with a `person` or `photo` below. |
| `chart` | `{"closes": [[label, value], …], "at", "dur", "ticker", "labelStart", "labelEnd", "color"}` | A line drawn point by point from real data. `ticker` is the label centred under its counter. |
| `counters` | `[{"to", "at", "dur", "top", "size", "color", "prefix", "suffix", "dec"/"comma", "col"}]` | Lands on its value at `at + dur`. `"series": [values]` steps through real points; `"steps": [{"text", "at"}]` replaces one value by the next; `"count": True` counts up (running tallies only). `"col": "left"/"right"` puts it under its logo. |
| `words` | `[{"text", "color", "top", "size", "at"}]` | A big word or sign that slams in, such as a `"<"` between two counters. |
| `stamps` | `[{"text", "x", "y", "rot", "at", "kind": "label"/"label alt"}]` | A rubber stamp or a label. Only for what the caption doesn't say. |
| `imgs` | `[{"src", "x", "y", "w", "at", "bg": "#fff", "pad", "dim": t}]` | A logo tile (only the actor's), `dim` greys it out. |
| `typed` | `[{"text", "at", "top", "size", "cps"}]` | Text typed key by key in Kode Mono (a command, a tool's name). |
| `flow` | `{"top", "steps": [{"text", "at", "hot"}]}` | Steps with arrows, in the order they are said; each adds what the caption can't. |
| `dots` | `{"n", "k", "at", "hit", "top"}` | A ratio as icons: `k` of `n` filled ("1 in 4"). |
| `shake` | `[t]` | A short camera shake on a hit. |

`TITLE` (optional) is a hook headline above the first scene, centred in its own band, and must say something the
first caption doesn't. `EVENTS(cut)` places sounds: `hit`, `whoosh`, `pop`, `ding`, `boom`; the end card's are
added for you.
