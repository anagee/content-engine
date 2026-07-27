#!/usr/bin/env python3
"""
Content Engine v1 — Visual builder  (Beverly Crandon brand system)
Turns a content pack (the JSON the engine produces) into branded, ready-to-post
PNGs: Instagram carousel slides (1080x1350) + a quote card (1080x1080).

Brand system (from CrandonDesign):
  - Light grounds (White / Sand). No dark hero, no burgundy.
  - Line Black for type and rules only.
  - Signal Red used sparingly — the dash, the number tick, the CTA field.
  - One typeface: Familjen Grotesk. Roman = the publication; ITALIC is reserved
    for Beverly's first-person voice and the "wine with me" tagline.

Setup (one time, on your Mac):
    pip install playwright
    playwright install chromium

Use:
    python visuals.py pack.json --out assets --handle @beverlycrandon
"""

import os
import re
import json
import argparse

# ---- Brand tokens ----------------------------------------------------------
BRAND = {
    "signal_red": "#D6261B",   # accent only: dash, link, button, one word
    "black": "#000000",        # type & rules
    "deep_teal": "#134D4F",    # secondary voice (education, data)
    "amber": "#E0A32E",        # graphic only, never text on white
    "aubergine": "#4A2545",    # the one permitted dark surface (events)
    "sand": "#EFE9DE",         # warm ground
    "white": "#FFFFFF",        # default ground
    "off_white": "#F7F6F4",
    "rule": "#E2DFDA",         # hairlines, dividers
    "muted": "#6F6A63",        # captions, metadata
    "font": "'Familjen Grotesk', -apple-system, Helvetica, sans-serif",
}

FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Familjen+Grotesk:ital,wght@0,400;0,500;0,700;1,400;1,500&display=swap" '
    'rel="stylesheet">'
)

CAROUSEL_W, CAROUSEL_H = 1080, 1350
CARD_W, CARD_H = 1080, 1080


def _clean(text: str) -> str:
    """Strip a leading 'slide 3:' style prefix the model sometimes adds."""
    return re.sub(r"^\s*slide\s*\d+\s*:\s*", "", text, flags=re.I).strip()


def _wrapper(inner: str, w: int, h: int) -> str:
    b = BRAND
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{FONT_LINK}
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:{w}px;height:{h}px;overflow:hidden;}}
.stage{{width:{w}px;height:{h}px;position:relative;font-family:{b['font']};
  -webkit-font-smoothing:antialiased;}}
.dash{{display:inline-block;height:3px;background:{b['signal_red']};
  vertical-align:middle;}}
.mark{{font-weight:700;letter-spacing:.14em;}}
.tag{{font-style:italic;font-weight:400;letter-spacing:0;}}
</style></head><body>{inner}</body></html>"""


def carousel_slide(text, index, total, kind, handle, label=""):
    b = BRAND
    text = _clean(text)
    if kind == "cover":
        label = (label or "Beverly Crandon on Wine").upper()
        inner = f"""<div class="stage" style="background:{b['sand']};padding:96px 90px;
          display:flex;flex-direction:column;">
          <div class="mark" style="color:{b['signal_red']};font-size:22px;">
            <span class="dash" style="width:44px;margin-right:16px;"></span>{label}</div>
          <div style="flex:1;display:flex;align-items:center;">
            <div style="font-weight:500;color:{b['black']};font-size:88px;line-height:1.02;
              letter-spacing:-.02em;">{text}</div>
          </div>
          <div>
            <div class="mark" style="color:{b['black']};font-size:30px;">BEVERLY CRANDON</div>
            <div style="color:{b['black']};font-size:30px;margin-top:8px;">
              <span class="dash" style="width:30px;height:2px;margin-right:12px;"></span>
              <span class="tag">wine with me</span></div>
          </div>
        </div>"""
    elif kind == "cta":
        inner = f"""<div class="stage" style="background:{b['signal_red']};padding:110px 90px;
          display:flex;flex-direction:column;justify-content:center;">
          <div style="font-weight:500;color:{b['white']};font-size:66px;line-height:1.12;
            letter-spacing:-.015em;">{text}</div>
          <div style="width:80px;height:3px;background:{b['white']};margin:46px 0;"></div>
          <div style="font-weight:500;color:{b['white']};font-size:34px;">Read the full post &rarr; link in bio</div>
          <div class="mark" style="color:{b['white']};font-size:20px;position:absolute;
            bottom:70px;left:90px;">BEVERLY CRANDON</div>
        </div>"""
    else:  # body
        num = f"{index+1:02d} / {total:02d}"
        inner = f"""<div class="stage" style="background:{b['white']};padding:110px 90px 90px;
          display:flex;flex-direction:column;">
          <div class="mark" style="color:{b['black']};font-size:24px;">
            <span class="dash" style="width:36px;margin-right:14px;"></span>{num}</div>
          <div style="flex:1;display:flex;align-items:center;">
            <div style="font-weight:500;color:{b['black']};font-size:56px;line-height:1.24;
              letter-spacing:-.015em;">{text}</div>
          </div>
          <div style="border-top:1px solid {b['rule']};padding-top:26px;">
            <span class="mark" style="color:{b['black']};font-size:20px;">BEVERLY CRANDON</span>
          </div>
        </div>"""
    return _wrapper(inner, CAROUSEL_W, CAROUSEL_H)


def quote_card(quote, handle):
    b = BRAND
    quote = quote.strip().strip('"').strip("“”")
    # Beverly's first-person voice -> italic, per the type rule.
    inner = f"""<div class="stage" style="background:{b['sand']};padding:100px;
      display:flex;flex-direction:column;justify-content:center;">
      <div class="dash" style="width:66px;height:5px;margin-bottom:46px;"></div>
      <div style="font-style:italic;font-weight:400;color:{b['black']};font-size:66px;
        line-height:1.26;letter-spacing:-.01em;">{quote}</div>
      <div class="mark" style="color:{b['black']};font-size:24px;margin-top:56px;">BEVERLY CRANDON<span class="tag" style="font-size:24px;"> &mdash; wine with me</span></div>
    </div>"""
    return _wrapper(inner, CARD_W, CARD_H)


def build_pages(pack, handle):
    """Return a list of (filename, html, width, height)."""
    pages = []
    slides = (pack.get("instagram_carousel") or {}).get("slides", []) or []
    label = pack.get("pillar") or "Beverly Crandon on Wine"
    total = len(slides)
    for i, s in enumerate(slides):
        kind = "cover" if i == 0 else ("cta" if i == total - 1 else "body")
        pages.append((f"slide_{i+1:02d}.png",
                      carousel_slide(s, i, total, kind, handle, label=label),
                      CAROUSEL_W, CAROUSEL_H))
    q = pack.get("quote_card")
    if q:
        pages.append(("quote_card.png", quote_card(q, handle), CARD_W, CARD_H))
    return pages


def render(pages, out_dir, scale=2):
    """Render each page to PNG with Playwright (imported lazily)."""
    from playwright.sync_api import sync_playwright
    os.makedirs(out_dir, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, html, w, h in pages:
            page = browser.new_page(viewport={"width": w, "height": h},
                                    device_scale_factor=scale)
            page.set_content(html, wait_until="networkidle")
            page.screenshot(path=os.path.join(out_dir, name))
            page.close()
            print(f"  ✓ {name}")
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack", help="path to a content-pack JSON file")
    ap.add_argument("--out", default="assets", help="output folder")
    ap.add_argument("--handle", default="@beverlycrandon")
    ap.add_argument("--scale", type=int, default=2, help="pixel density (2 = retina-crisp)")
    args = ap.parse_args()

    with open(args.pack, encoding="utf-8") as f:
        pack = json.load(f)

    pages = build_pages(pack, args.handle)
    if not pages:
        raise SystemExit("No carousel slides or quote_card found in that pack.")
    print(f"Rendering {len(pages)} image(s) -> {args.out}/")
    render(pages, args.out, scale=args.scale)
    print("Done.")


if __name__ == "__main__":
    main()
