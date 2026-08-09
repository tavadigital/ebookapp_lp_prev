#!/usr/bin/env python3
"""
Scan repo untuk semua file HTML sales page (nama file mengandung "-lp"),
ambil tanggal commit terakhir tiap file dari git, lalu tulis ke data.json.

Dijalankan otomatis oleh GitHub Actions setiap kali ada push.
Bisa juga dijalankan manual:  python scripts/build_index.py
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------- konfigurasi

KEYWORD = "-lp"                      # penanda file sales page
EXCLUDE_DIRS = {".git", ".github", "node_modules", "scripts", "vendor"}
EXCLUDE_FILES = {"index.html", "404.html"}
OUTPUT = "data.json"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- util

def run_git(args):
    try:
        out = subprocess.run(
            ["git"] + args, cwd=ROOT, text=True,
            capture_output=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def git_dates(relpath):
    """(tanggal commit pertama, tanggal commit terakhir) dalam ISO-8601."""
    log = run_git(["log", "--follow", "--format=%cI", "--", relpath])
    if not log:
        return None, None
    lines = [l for l in log.splitlines() if l.strip()]
    if not lines:
        return None, None
    return lines[-1], lines[0]          # pertama, terakhir


def read_head(path, n=40000):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(n)
    except OSError:
        return ""


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;?", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_title(head):
    m = re.search(r"<title[^>]*>(.*?)</title>", head, re.I | re.S)
    if m:
        t = strip_tags(m.group(1))
        if t and t.lower() not in ("document", "untitled"):
            return t[:140]
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                  head, re.I)
    if m:
        t = strip_tags(m.group(1))
        if t:
            return t[:140]
    m = re.search(r"<h1[^>]*>(.*?)</h1>", head, re.I | re.S)
    if m:
        t = strip_tags(m.group(1))
        if t:
            return t[:140]
    return None


def extract_desc(head):
    for pat in (r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)'):
        m = re.search(pat, head, re.I)
        if m:
            d = strip_tags(m.group(1))
            if d:
                return d[:200]
    return None


def pretty_slug(filename):
    """mcs-lp.html.html -> Mcs / hr-lp.html -> Hr"""
    name = filename
    while True:
        base, ext = os.path.splitext(name)
        if ext.lower() in (".html", ".htm"):
            name = base
        else:
            break
    name = re.sub(r"[-_]?lp$", "", name, flags=re.I)
    name = re.sub(r"^lp[-_]?", "", name, flags=re.I)
    name = re.sub(r"[-_]+", " ", name).strip()
    return name.upper() if len(name) <= 5 else name.title()


# ---------------------------------------------------------------- scan

def collect():
    items = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fn in filenames:
            low = fn.lower()
            if not (low.endswith(".html") or low.endswith(".htm")):
                continue
            if low in EXCLUDE_FILES:
                continue
            if KEYWORD not in low:
                continue

            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            head = read_head(full)
            created, updated = git_dates(rel)

            items.append({
                "path": rel,
                "file": fn,
                "folder": os.path.dirname(rel) or ".",
                "slug": pretty_slug(fn),
                "title": extract_title(head) or pretty_slug(fn),
                "description": extract_desc(head),
                "size": os.path.getsize(full),
                "created": created,
                "updated": updated or created,
            })

    # terbaru di atas; yang tanpa data git ditaruh paling bawah
    items.sort(key=lambda x: x["updated"] or "", reverse=True)
    return items


def main():
    items = collect()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "keyword": KEYWORD,
        "count": len(items),
        "items": items,
    }
    out_path = os.path.join(ROOT, OUTPUT)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{len(items)} sales page ditulis ke {OUTPUT}")
    for it in items:
        print(f"  - {it['path']}  ({it['updated']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
