#!/usr/bin/env python3
"""
Content Engine v0 — Beverly Crandon on Wine
RSS (Wix blog) -> OpenAI -> Google Sheet (optional)

Purpose: prove the AI drafts sound like Beverly. Start with --dry-run
(no Sheet needed), tune prompt.md, then wire up the Sheet.

Setup:
    pip install -r requirements.txt
    # put OPENAI_API_KEY=sk-... in a .env file (from platform.openai.com)

Run (voice-tuning loop, no Sheet required):
    python engine_v0.py --dry-run --limit 5

Run (append new posts to a Google Sheet):
    export SHEET_ID=...                # the id in the sheet URL
    export GOOGLE_CREDS=service_account.json
    python engine_v0.py
"""

import os
import re
import sys
import json
import argparse
import datetime as dt

import feedparser
import requests
from bs4 import BeautifulSoup

def _load_dotenv():
    """Load KEY=VALUE lines from a .env file next to this script, so you set the
    key once instead of exporting it every session. Shell exports still win."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

FEED_URL = "https://www.beverlycrandon.com/blog-feed.xml"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
PROMPT_PATH = os.environ.get("PROMPT_PATH", "prompt.md")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Sheet columns, in order. 'guid' is used for dedupe; 'status' is left blank for review.
COLUMNS = [
    "processed", "title", "url", "pillar", "newsletter_intro",
    "ig_carousel", "ig_reel_script", "tiktok_script", "linkedin_post",
    "quote_card", "guid", "status",
]


def load_prompt() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def fetch_body(url: str, excerpt: str) -> str:
    """Wix blogs are server-rendered for SEO, so the article text is usually in
    the static HTML. Pull the paragraphs; fall back to the RSS excerpt."""
    try:
        html = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            tag.decompose()
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        body = "\n".join(p for p in paras if len(p) > 40)
        return body[:8000] if len(body) > 200 else excerpt
    except Exception as e:  # noqa
        print(f"  ! body fetch failed ({e}); using excerpt", file=sys.stderr)
        return excerpt


def generate(system_prompt: str, entry: dict) -> dict:
    """Call the OpenAI Chat Completions API and return the parsed content pack."""
    user = (
        f"TITLE: {entry['title']}\n"
        f"CATEGORIES: {', '.join(entry['categories']) or 'n/a'}\n"
        f"URL: {entry['link']}\n"
        f"IS_VIDEO: {entry['is_video']}\n\n"
        f"POST BODY:\n{entry['body']}"
    )
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    r = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    text = r.json()["choices"][0]["message"]["content"].strip()
    # strip ``` fences and pull the JSON object out of any stray prose
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    s, e = text.find("{"), text.rfind("}")
    return json.loads(text[s:e + 1])


def flatten_for_sheet(entry: dict, pack: dict) -> list:
    def joins(x):
        return "\n".join(x) if isinstance(x, list) else str(x)
    carousel = pack.get("instagram_carousel", {})
    reel = pack.get("instagram_reel", {})
    tiktok = pack.get("tiktok", {})
    carousel_txt = joins(carousel.get("slides", [])) + \
        "\n\nCAPTION: " + str(carousel.get("caption", "")) + \
        "\n" + " ".join(carousel.get("hashtags", []))
    reel_txt = f"HOOK: {reel.get('hook','')}\n{reel.get('script','')}"
    tiktok_txt = f"HOOK: {tiktok.get('hook','')}\n{tiktok.get('script','')}"
    return [
        dt.date.today().isoformat(),
        pack.get("source_title") or entry["title"],
        entry["link"],
        pack.get("pillar", ""),
        pack.get("newsletter_intro", ""),
        carousel_txt,
        reel_txt,
        tiktok_txt,
        pack.get("linkedin", {}).get("post", ""),
        pack.get("quote_card", ""),
        entry["guid"],
        "",  # status — filled during review
    ]


def get_worksheet():
    import gspread
    gc = gspread.service_account(filename=os.environ["GOOGLE_CREDS"])
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    ws = sh.sheet1
    # ensure header row exists
    if ws.row_values(1) != COLUMNS:
        if not ws.get_all_values():
            ws.append_row(COLUMNS)
    return ws


def already_done(ws) -> set:
    try:
        idx = COLUMNS.index("guid") + 1
        return set(ws.col_values(idx)[1:])  # skip header
    except Exception:
        return set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print drafts, don't touch the Sheet")
    ap.add_argument("--limit", type=int, default=5, help="max posts to process")
    ap.add_argument("--json-out", default=None,
                    help="also save each pack as <guid>.json here (feeds visuals.py)")
    args = ap.parse_args()

    if "OPENAI_API_KEY" not in os.environ:
        sys.exit("Set OPENAI_API_KEY in your .env file (create a key at https://platform.openai.com/api-keys)")

    system_prompt = load_prompt()

    ws = None
    seen = set()
    if not args.dry_run:
        ws = get_worksheet()
        seen |= set(already_done(ws))
    # also skip posts we've already saved as packs (so scheduled runs only
    # process genuinely new posts)
    if args.json_out and os.path.isdir(args.json_out):
        seen |= {os.path.splitext(f)[0] for f in os.listdir(args.json_out) if f.endswith(".json")}

    feed = feedparser.parse(FEED_URL)
    processed = 0
    for e in feed.entries:
        if processed >= args.limit:
            break
        guid = e.get("id") or e.get("guid") or e.link
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", guid)
        if guid in seen or safe in seen:
            continue

        enclosures = e.get("enclosures", [])
        is_video = any("video" in (enc.get("type", "")) or "youtu" in (enc.get("href", ""))
                       for enc in enclosures)
        entry = {
            "title": e.title,
            "link": e.link,
            "guid": guid,
            "categories": [t.term for t in e.get("tags", [])],
            "is_video": is_video,
            "body": fetch_body(e.link, e.get("summary", "")),
        }

        print(f"→ {entry['title']}")
        try:
            pack = generate(system_prompt, entry)
        except Exception as ex:  # noqa
            print(f"  ! generation failed: {ex}", file=sys.stderr)
            continue

        if args.json_out:
            os.makedirs(args.json_out, exist_ok=True)
            with open(os.path.join(args.json_out, f"{safe}.json"), "w", encoding="utf-8") as jf:
                json.dump(pack, jf, indent=2, ensure_ascii=False)
            print(f"  ✓ saved {safe}.json")

        if args.dry_run:
            print(json.dumps(pack, indent=2, ensure_ascii=False))
            print("-" * 60)
        else:
            ws.append_row(flatten_for_sheet(entry, pack), value_input_option="RAW")
            print("  ✓ appended to sheet")
        processed += 1

    print(f"\nDone. Processed {processed} post(s).")


if __name__ == "__main__":
    main()
