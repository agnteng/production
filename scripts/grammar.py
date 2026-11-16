"""Correct the grammar of text written from audio, never its wording (ADR 0007).

Speakers slip, often in a second language: "we have 47 tool", "everyone talk
about it", "it cost 100" for a price. What a viewer or reader sees is written
correctly: captions, subtitles and transcripts. The audio is untouched.

A model (OpenRouter) gets the lines with fixed rules and returns them
corrected. A guard then compares each line word by word and keeps the original
(and reports it) when the answer is a rewrite, not a correction: more than a
quarter of the words changed (two in a short line), the length moved by more
than three words, or a changed word is neither a form of the one it replaces
(tool/tools, arise/arose), a function word (a, the, is, are, this, these…), nor
money written with its sign. Lines go in batches; each answer must have the
same number of lines.

    python3 scripts/grammar.py FILE …      correct transcript.md files in place, printing every change

A corrected transcript says so in its provenance note ("grammar-corrected"),
which the `grammar` fitness check looks for.
"""
from __future__ import annotations

import difflib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

import common

MODEL = "google/gemini-3.8-flash"
API = "https://openrouter.ai/api/v1/chat/completions"
RULES = """You correct the grammar of lines transcribed from talks at a meetup about building with AI agents.
Many speakers are not native English speakers. Return the same lines, corrected, so a reader reads correct English.

Fix only:
- subject-verb agreement ("everyone talk" -> "everyone talks")
- singular and plural ("47 tool" -> "47 tools", "10 workflow" -> "10 workflows")
- missing or wrong articles and determiners ("it's 15% discount" -> "it's a 15% discount")
- wrong verb forms ("what can be go wrong" -> "what can go wrong", "it will consider" -> "it will be considered")
- a word the transcript misheard as one that sounds alike, when the sentence shows which was said
  ("try throw-in requests" -> "try throwing requests")
- money: write amounts with their currency sign whenever the context is money, even if the speaker did not say
  the currency: "100 dollars" -> "$100", "1 dollar per conversation" -> "$1 per conversation", "it cost 100" (money)
  -> "it cost $100", euros with "€". Cents may stay as "15 cents".

Never:
- correct what is already acceptable English. Leave a line unchanged when in doubt.
- change tense: telling past events in the present is fine ("so we make the decision" stays). Fix a verb only
  when its form is wrong for its subject or auxiliary.
- pluralise a noun used for a concept or a field ("workflow is outdated", "AI is everywhere" stay)
- change word choice, word order, tone or meaning, or make a sentence more formal
- remove or add content words, examples or asides
- touch names of people, companies, products, models or code, or numbers other than currency signs
- merge or split lines

Return only JSON: {"lines": [...]} with exactly as many strings as you were given, in the same order."""


def _ask(lines: list[str]) -> list[str]:
    body = json.dumps({"model": MODEL, "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": RULES},
                                    {"role": "user", "content": json.dumps({"lines": lines}, ensure_ascii=False)}]}).encode()
    for _ in range(3):
        req = urllib.request.Request(API, data=body, headers={"Authorization": f"Bearer {common.openrouter_key()}",
                                                              "Content-Type": "application/json"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=180).read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 402):
                common.die(f"OpenRouter HTTP {e.code}: the key needs replacing; stop here")
            continue
        text = r["choices"][0]["message"]["content"] or ""
        m = re.search(r"\{.*\}", text, re.S)
        try:
            out = json.loads(m.group(0))["lines"] if m else None
        except (json.JSONDecodeError, KeyError):
            out = None
        if isinstance(out, list) and len(out) == len(lines) and all(isinstance(x, str) for x in out):
            return out
    common.die(f"{MODEL}: no usable correction after 3 tries")


FUNCTION = set("""a an the this that these those there here it its it's them they they're their he he's she she's
him his her we us our you your i i'm me my is are am was were be been being has have had having do does did done
doesn't don't didn't isn't aren't wasn't weren't won't can't that's what's here's we're you're i've we've they've
will would can could should shall may might must to of in on at for
with by from as about into than and or but so not no much many few fewer less little more most another other some any
each every all one""".split())
NUMBER_WORDS = set("""zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen
sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million
billion grand k""".split())
CURRENCY = {"dollar", "dollars", "buck", "bucks", "usd", "euro", "euros", "eur", "pound", "pounds", "cent", "cents"}
MONEY = re.compile(r"[$€£]")


def _norm(w: str) -> str:
    return re.sub(r"[^\w$€£']", "", w.lower().replace("’", "'"))


def _form(was: str, now: str) -> bool:
    """`now` is a form of `was` (tool/tools, going/goes, arise/arose), not another word."""
    k = len(os.path.commonprefix([was, now]))
    return difflib.SequenceMatcher(None, was, now).ratio() >= 0.6 or k >= max(2, min(len(was), len(now)) / 2)


def guard(old: str, new: str) -> bool:
    """True when `new` is a correction of `old`, not a rewrite (see the module docstring)."""
    a, b = old.split(), new.split()
    if abs(len(a) - len(b)) > 3:
        return False
    money = len(MONEY.findall(new)) > len(MONEY.findall(old))
    changed = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        said, written = "".join(map(_norm, a[i1:i2])), "".join(map(_norm, b[j1:j2]))
        is_money = money and bool(MONEY.search(written))
        if not is_money and re.sub(r"\D", "", said) != re.sub(r"\D", "", written):
            return False  # numbers never change, except into an amount
        if said and written and _form(said, written):
            changed += max(i2 - i1, j2 - j1)
            continue
        was = [w for w in map(_norm, a[i1:i2]) if w and w not in FUNCTION
               and not (money and (w in CURRENCY or w in NUMBER_WORDS or re.fullmatch(r"[\d.,]+", w)))]
        now = [w for w in map(_norm, b[j1:j2]) if w and w not in FUNCTION and not MONEY.match(w)]
        if (was or now) and not (was and now and _form("".join(was), "".join(now))):
            return False
        # An amount written with its sign is one change, however many words it was said in.
        changed += 1 if is_money else max(i2 - i1, j2 - j1)
    return changed <= max(2, len(a) // 4)


def correct(lines: list[str], batch: int = 40) -> tuple[list[str], list[tuple[str, str]]]:
    """The lines corrected, and the (old, new) pairs the guard refused."""
    out, refused = [], []
    for k in range(0, len(lines), batch):
        part = lines[k:k + batch]
        for old, new in zip(part, _ask(part)):
            new = " ".join(new.split())
            if new == old or guard(old, new):
                out.append(new)
            else:
                out.append(old)
                refused.append((old, new))
    return out, refused


def correct_file(path: pathlib.Path) -> int:
    """Correct a transcript.md in place: the text of each **[m:ss]** paragraph, nothing else. Returns lines changed."""
    lines = path.read_text().split("\n")
    idx = [n for n, line in enumerate(lines) if re.match(r"^\*\*\[[\d:]+\]\*\* ", line)]
    heads = [re.match(r"^(\*\*\[[\d:]+\]\*\* )(.*)$", lines[n]).groups() for n in idx]
    new, refused = correct([text for _, text in heads])
    changed = 0
    for n, (head, old), text in zip(idx, heads, new):
        if text != old:
            changed += 1
            lines[n] = head + text
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old.split(), text.split(), autojunk=False).get_opcodes():
                if op != "equal":
                    print(f"  {head.strip()} {' '.join(old.split()[i1:i2]) or '∅'} → {' '.join(text.split()[j1:j2]) or '∅'}")
    for old, new_ in refused:
        print(f"  REFUSED (a rewrite, kept as said): {old[:80]}… → {new_[:80]}…", file=sys.stderr)
    path.write_text(stamp("\n".join(lines)))
    return changed


def stamp(text: str) -> str:
    """The provenance note (the paragraph before the first timestamp) says the transcript is grammar-corrected."""
    if "grammar-corrected" in text.lower():
        return text
    if "lightly cleaned;" in text:
        return text.replace("lightly cleaned;", "lightly cleaned and grammar-corrected;", 1)
    head, sep, body = text.partition("\n\n**[")
    return head.rstrip() + " Grammar-corrected." + sep + body


def main() -> None:
    for name in sys.argv[1:]:
        path = pathlib.Path(name)
        print(f"{path}: ", flush=True)
        print(f"  {correct_file(path)} paragraphs corrected")


if __name__ == "__main__":
    main()
