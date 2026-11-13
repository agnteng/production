#!/usr/bin/env python3
"""An event's facts from its Luma page, and the website's event.json from them.

Luma slugs are ae-<city>-<n>: luma.com/ae-lisbon-6 is Lisbon meetup #6, so
the city and the number come from the slug and the rest from the page.

    python3 scripts/luma_event.py ae-lisbon-6            print what Luma says
    python3 scripts/luma_event.py ae-lisbon-6 --write    fill ../website/content/<date>/event.json

--write adds only what event.json lacks. Where the two disagree it prints both
and keeps event.json, since a person may have corrected it. If Luma's date no
longer matches the event's folder (a rescheduled event), it stops instead of
creating a second folder. The public page hides the venue until you register;
with LUMA_API_KEY (environment or .env) the venue comes from the Luma API.

Speakers are read from the "Speakers" section of the event description, one
per line as `Name - Title` (or `Name, Title`). Photos are never filled in.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from common import LUMA_SLUG, WEBSITE_CONTENT, date_for_slug, die, secret, slug_of

PAGE = "https://luma.com/{slug}"
API = "https://api.lu.ma/public/v1/event/get?api_id={api_id}"
UA = "Mozilla/5.0 (compatible; agnteng-production)"


def fetch(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def page_data(slug: str) -> dict:
    try:
        html = fetch(PAGE.format(slug=slug)).decode()
    except urllib.error.HTTPError as e:
        die(f"luma.com/{slug}: HTTP {e.code}")
    except urllib.error.URLError as e:
        die(f"luma.com/{slug}: {e.reason}")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        die(f"luma.com/{slug}: no event data in the page")
    return json.loads(m.group(1))["props"]["pageProps"]["initialData"]["data"]


def blocks(node: dict) -> list[tuple[str, bool]]:
    """(text, is_heading) for each paragraph or heading of a Luma description.

    A heading node, or a paragraph that is bold throughout, counts as a
    heading. Hard breaks become newlines.
    """
    out = []
    for n in node.get("content", []):
        kind = n.get("type")
        if kind in ("paragraph", "heading"):
            parts = n.get("content", [])
            text = "".join("\n" if p.get("type") == "hard_break" else p.get("text", "")
                           for p in parts).strip()
            bold = all(any(m.get("type") == "bold" for m in p.get("marks", []))
                       for p in parts if p.get("text", "").strip())
            if text:
                out.append((text, kind == "heading" or bold))
        else:
            out.extend(blocks(n))
    return out


def speakers(description: dict | None) -> list[dict]:
    found, inside = [], False
    for text, heading in blocks(description or {}):
        if heading:
            inside = text.rstrip(":").strip().lower() == "speakers"
            continue
        if inside:
            for line in text.splitlines():
                name, title = (re.split(r"\s+[-–—]\s+|,\s+", line.strip(), maxsplit=1) + [""])[:2]
                if name:
                    found.append({"name": name.strip(), "title": title.strip()})
    return found


def venue_from_api(api_id: str) -> str | None:
    key = secret("LUMA_API_KEY", required=False)
    if not key:
        return None
    try:
        ev = json.loads(fetch(API.format(api_id=api_id), {"x-luma-api-key": key})).get("event", {})
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"note: Luma API failed ({getattr(e, 'code', e)}); no venue", file=sys.stderr)
        return None
    geo = ev.get("geo_address_json") or {}
    return geo.get("address") or geo.get("description") or None


def facts(slug: str) -> dict:
    data = page_data(slug)
    ev = data["event"]
    start = dt.datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00"))
    local = start.astimezone(ZoneInfo(ev.get("timezone") or "UTC"))
    m = LUMA_SLUG.fullmatch(slug)
    if m:
        city, number = m.group(1).replace("-", " ").title(), int(m.group(2))
    else:
        print(f"note: {slug} is not ae-<city>-<n>; city from the page, no number",
              file=sys.stderr)
        city, number = (ev.get("geo_address_info") or {}).get("city"), None
    geo = ev.get("geo_address_json") or {}
    venue = geo.get("address") or venue_from_api(ev["api_id"])
    f = {
        "date": local.date().isoformat(),
        "city": city,
        "number": number,
        "venue": venue,
        "tonight": f"{local:%a} {local.day} {local:%B %Y} · {venue}" if venue else None,
        "luma": {"apiId": ev["api_id"], "url": PAGE.format(slug=slug),
                 "startAt": ev["start_at"]},
        "speakers": speakers(data.get("description_mirror")),
    }
    return {k: v for k, v in f.items() if v not in (None, [])}


def write(slug: str, f: dict) -> None:
    if not WEBSITE_CONTENT.is_dir():
        die(f"no website checkout at {WEBSITE_CONTENT.parent}")
    known = date_for_slug(slug)
    if known and known != f["date"]:
        die(f"Luma now says {f['date']}, but content/{known}/ has this event: "
            f"move the folder in the website (and here), then re-run")
    path = WEBSITE_CONTENT / f["date"] / "event.json"
    have = json.loads(path.read_text()) if path.exists() else {}
    merged = json.loads(json.dumps(have))
    for k, v in f.items():
        if k not in have:
            merged[k] = v
            print(f"  + {k}")
        elif isinstance(v, dict) and isinstance(have[k], dict):
            for lk, lv in v.items():
                if lk not in have[k]:
                    merged[k][lk] = lv
                    print(f"  + {k}.{lk}")
                elif have[k][lk] != lv:
                    print(f"  ≠ {k}.{lk}: event.json {have[k][lk]!r}, Luma {lv!r} (kept event.json)")
        elif have[k] != v:
            print(f"  ≠ {k}: event.json {have[k]!r}, Luma {v!r} (kept event.json)")
    for k in ("venue", "tonight"):
        if k not in merged:
            print(f"  ! {k}: unknown (Luma hides the venue without LUMA_API_KEY); add it by hand")
    if merged == have:
        print(f"{path}: up to date")
        return
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    print(f"{path}: {'updated' if have else 'created'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", help="ae-<city>-<n>, or a luma.com URL")
    ap.add_argument("--write", action="store_true", help="fill the website's event.json")
    args = ap.parse_args()
    slug = slug_of(args.slug)
    f = facts(slug)
    if args.write:
        write(slug, f)
    else:
        print(json.dumps(f, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
