#!/usr/bin/env python3
"""
Content Engine — batch review page.

Reads a folder of content packs (the JSON from `engine_v0.py --json-out`),
renders the branded images for each pack, and builds ONE review.html you open
in a browser to review every post's full kit — images, captions, scripts — in
one place, and tick what's approved.

Usage:
    python build_review.py packs --out review --handle @beverlycrandon
    open review/index.html          # macOS

Needs Playwright (same as visuals.py):  pip install playwright && playwright install chromium
"""

import os
import glob
import json
import html
import argparse

import visuals

CSS = """
*{box-sizing:border-box}
body{font-family:'Familjen Grotesk',-apple-system,Helvetica,sans-serif;color:#000;
  background:#F7F6F4;margin:0;padding:40px;line-height:1.4;}
h1{font-weight:500;font-size:34px;letter-spacing:-.02em;margin:0 0 6px}
.sub{color:#6F6A63;margin-bottom:34px}
section{background:#fff;border:1px solid #E2DFDA;border-radius:8px;padding:28px 30px;
  margin-bottom:26px;max-width:1100px}
.pill{display:inline-block;background:#EFE9DE;color:#000;font-weight:700;font-size:11px;
  letter-spacing:.12em;text-transform:uppercase;padding:5px 10px;border-radius:3px}
.dash{display:inline-block;width:30px;height:3px;background:#D6261B;vertical-align:middle;margin-right:10px}
h2{font-weight:500;font-size:23px;letter-spacing:-.01em;margin:12px 0 4px}
.src{color:#6F6A63;font-size:13px;text-decoration:none}
.imgs{display:flex;gap:10px;overflow-x:auto;padding:18px 0;margin:8px 0 6px;border-bottom:1px solid #E2DFDA}
.imgs img{height:300px;border:1px solid #E2DFDA;border-radius:4px;flex:0 0 auto}
.block{margin:16px 0}
h4{font-weight:700;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#D6261B;margin:0 0 6px}
.body{white-space:pre-wrap;font-size:15px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.approve{display:inline-flex;align-items:center;gap:10px;margin-top:20px;padding:10px 16px;
  background:#EFE9DE;border-radius:4px;font-weight:700;cursor:pointer}
.approve input{width:18px;height:18px}
@media print{.approve{display:none}}
"""


def esc(s):
    return html.escape(s or "")


def _block(title, body):
    return f'<div class="block"><h4>{esc(title)}</h4><div class="body">{esc(body)}</div></div>'


def section_html(pack, img_rel, images):
    car = pack.get("instagram_carousel") or {}
    reel = pack.get("instagram_reel") or {}
    tt = pack.get("tiktok") or {}
    li = pack.get("linkedin") or {}
    imgs = "".join(f'<img src="{img_rel}/{i}" alt="{i}">' for i in images)
    hashtags = " ".join(car.get("hashtags", []) or [])
    reel_txt = (reel.get("hook", "") + "\n\n" + reel.get("script", "")).strip()
    tt_txt = (tt.get("hook", "") + "\n\n" + tt.get("script", "")).strip()
    return f"""<section>
  <div><span class="pill">{esc(pack.get('pillar',''))}</span></div>
  <h2><span class="dash"></span>{esc(pack.get('source_title',''))}</h2>
  <a class="src" href="{esc(pack.get('source_url',''))}">{esc(pack.get('source_url',''))}</a>
  <div class="imgs">{imgs}</div>
  {_block('Newsletter intro — paste above the Substack cross-post', pack.get('newsletter_intro',''))}
  {_block('Instagram carousel caption', car.get('caption',''))}
  {_block('Hashtags', hashtags)}
  <div class="two">
    {_block('Instagram reel — hook + script (record to camera)', reel_txt)}
    {_block('TikTok — hook + script (record to camera)', tt_txt)}
  </div>
  {_block('LinkedIn', li.get('post',''))}
  {_block('Quote card text', pack.get('quote_card',''))}
  <label class="approve"><input type="checkbox"> Approved &mdash; ready to schedule</label>
</section>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("packs", help="folder of pack JSON files")
    ap.add_argument("--out", default="review", help="output folder for the review site")
    ap.add_argument("--handle", default="@beverlycrandon")
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(args.packs, "*.json")))
    if not files:
        # nothing drafted yet — write a friendly placeholder so the hosted page
        # still exists (and the workflow succeeds) instead of erroring out
        with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as fh:
            fh.write("<!DOCTYPE html><meta charset='utf-8'>"
                     "<body style='font-family:sans-serif;padding:48px;color:#000'>"
                     "<h1 style='font-weight:500'>No drafts yet</h1>"
                     "<p style='color:#6F6A63'>New blog posts will appear here automatically.</p>"
                     "</body>")
        open(os.path.join(args.out, ".nojekyll"), "w").close()
        print("No packs yet — wrote placeholder page.")
        return

    sections = []
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        with open(f, encoding="utf-8") as fh:
            pack = json.load(fh)
        pages = visuals.build_pages(pack, args.handle)
        img_dir = os.path.join(args.out, "assets", stem)
        images = [name for name, *_ in pages]
        print(f"→ {pack.get('source_title', stem)}")
        if all(os.path.exists(os.path.join(img_dir, n)) for n in images):
            print("  (images already rendered, skipping)")
        else:
            visuals.render(pages, img_dir, scale=args.scale)
        sections.append(section_html(pack, f"assets/{stem}", images))

    page = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:ital,wght@0,400;0,500;0,700;1,400&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<h1>Content review</h1>
<div class="sub">{len(files)} post(s) · tick what's approved, then schedule the approved ones · print to share with Bev</div>
{''.join(sections)}
</body></html>"""

    out_html = os.path.join(args.out, "index.html")
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(page)
    open(os.path.join(args.out, ".nojekyll"), "w").close()  # let GitHub Pages serve as-is
    print(f"\nDone. Open {out_html}")


if __name__ == "__main__":
    main()
