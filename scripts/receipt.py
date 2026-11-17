# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.55.0"]
# ///
"""A receipt for a news Short: an article's headline and the sentence a line of the script rests on, as screenshots.

    mise exec -- uv run scripts/receipt.py <dir> <name> <url> "<exact sentence or phrase>" [--head "<headline start>"]
                                                                                       [--full-head] [--width 400]

Writes `<dir>/<name>-head.png` (the headline: masthead to headline with --full-head), `<name>-para.png` (the block
that holds the phrase) and `<name>.json` (sizes and the phrase's line boxes, which news_short.py highlights). The
page is read at phone width; a consent wall is answered ("Reject all"), and fixed bars and overlays are removed.
The phrase must appear on the page word for word: a receipt shows the sentence the voice is saying. --head finds a
headline by its first words when the page's <h1> is something else.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import common
from common import die

PREPARE = """([phrase, head]) => {
  document.querySelectorAll('body *').forEach((e) => { const p = getComputedStyle(e).position;
    if (p === 'fixed' || p === 'sticky') { if (e.getBoundingClientRect().top > 300) e.remove(); else e.style.position = 'static'; } });
  for (const sel of ['#onetrust-consent-sdk', '.onetrust-pc-dark-filter', '[class*="paywall"]', 'iframe', '[role="dialog"]', '[aria-modal="true"]'])
    document.querySelectorAll(sel).forEach((e) => { if (!e.contains(document.querySelector('h1'))) e.remove(); });
  const norm = (s) => s.replace(/\\s+/g, ' ');
  const para = [...document.querySelectorAll('p, li, blockquote, div')].filter((x) => norm(x.textContent).includes(phrase))
    .sort((a, c) => a.textContent.length - c.textContent.length)[0];
  if (!para) return { error: 'the phrase is not on the page' };
  const box = (e) => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y + scrollY, w: r.width, h: r.height }; };
  const nodes = []; const walk = document.createTreeWalker(para, NodeFilter.SHOW_TEXT); let n; while ((n = walk.nextNode())) nodes.push(n);
  let text = '', map = []; nodes.forEach((node) => { for (let i = 0; i < node.textContent.length; i++) map.push([node, i]); text += node.textContent; });
  const m = new RegExp(phrase.split(' ').map((w) => w.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')).join('\\\\s+')).exec(text);
  const rects = [];
  if (m) { const r = document.createRange(); const [sn, si] = map[m.index]; const [en, ei] = map[m.index + m[0].length - 1];
    r.setStart(sn, si); r.setEnd(en, ei + 1); for (const q of r.getClientRects()) rects.push({ x: q.x, y: q.y + scrollY, w: q.width, h: q.height }); }
  const h1 = head ? [...document.querySelectorAll('h1, h2, div, span, p')].filter((x) => x.textContent.trim().startsWith(head) && x.getBoundingClientRect().height > 10)
    .sort((a, c) => a.textContent.length - c.textContent.length)[0] : document.querySelector('h1');
  return { h1: h1 ? box(h1) : null, para: box(para), rects, title: document.title };
}"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir", type=pathlib.Path)
    ap.add_argument("name")
    ap.add_argument("url")
    ap.add_argument("phrase")
    ap.add_argument("--head", default="")
    ap.add_argument("--full-head", action="store_true", help="masthead to headline instead of the headline alone")
    ap.add_argument("--width", type=int, default=400)
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright
    scale, vw = 3, args.width
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=common.chrome_binary(), headless=True)
        pg = b.new_page(viewport={"width": vw, "height": 900}, device_scale_factor=scale, is_mobile=vw < 500,
                        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
        try:
            pg.goto(args.url, wait_until="networkidle", timeout=90000)
        except Exception:  # noqa: BLE001 - a page that never settles is still read
            pass
        pg.wait_for_timeout(2500)
        for _ in range(2):  # a consent wall: answer it in whichever frame holds it
            clicked = False
            for f in pg.frames:
                try:
                    btn = f.get_by_role("button", name=re.compile(r"^(reject all|accept all|i accept|agree)$", re.I))
                    if btn.count():
                        btn.first.click(timeout=3000)
                        clicked = True
                except Exception:  # noqa: BLE001
                    continue
            if not clicked:
                break
            pg.wait_for_timeout(2500)
        info = pg.evaluate(PREPARE, [args.phrase, args.head])
        if info.get("error"):
            b.close()
            die(f"{args.url}: {info['error']}: {args.phrase!r}")
        if not info["rects"]:
            print("  warning: the phrase was found but could not be boxed; the receipt will have no highlight", file=sys.stderr)
        h1 = info["h1"]
        head = ({"x": 0, "y": info["para"]["y"] - 14, "width": vw, "height": 1} if not h1 else
                {"x": 0, "y": 0, "width": vw, "height": h1["y"] + h1["h"] + 46} if args.full_head else
                {"x": 0, "y": h1["y"] - 24, "width": vw, "height": h1["h"] + 48})
        para = {"x": 0, "y": info["para"]["y"] - 14, "width": vw, "height": info["para"]["h"] + 28}
        pg.screenshot(path=str(args.dir / f"{args.name}-head.png"), clip=head, full_page=True)
        pg.screenshot(path=str(args.dir / f"{args.name}-para.png"), clip=para, full_page=True)
        b.close()
    rects = [{"x": r["x"] * scale, "y": (r["y"] - para["y"]) * scale, "w": r["w"] * scale, "h": r["h"] * scale} for r in info["rects"]]
    (args.dir / f"{args.name}.json").write_text(json.dumps({"width": vw * scale, "head": head["height"] * scale,
                                                            "para": para["height"] * scale, "rects": rects, "title": info["title"],
                                                            "url": args.url}))
    print(f"  {args.name}: {info['title']} ({len(rects)} highlighted line(s))")


if __name__ == "__main__":
    main()
