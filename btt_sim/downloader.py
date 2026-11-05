from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from rich.console import Console

from .config import Settings, SourceConfig

console = Console()

KEY_PORTFOLIO_SLUGS = [
    "svif-usa-portfolio",
    "stock-picks-performance-paid",
    "watchlist",
    "stock-watchlist-risk-reward-2025",
    "weekly-stock-performance-tracker",
    "global-portfolio-free",
    "start-here-beating-the-tide-essential",
    "start-here-stock-investing-newsletter",
    "frequently-asked-questions-faqs",
    # Cluseau key portfolio reviews
    "september-2026-portfolio-review",
    "june-2026-portfolio-review",
    "april-2026-portfolio-review",
    # TJStocks key tracker pages
    "stocktok-etf-20",
    "timothys-stocktok-tracker",
    "stocktok-etf-doubles-the-s-and-p",
    "buying-4-stocks-major-update-to-portfolio",
    "important-portfolio-update",
]

DATAWRAPPER_URL_RE = re.compile(
    r"https?://(?:datawrapper\.dwcdn\.net|www\.datawrapper\.de/_)/([A-Za-z0-9]+)(?:/(\d+))?/?",
    re.IGNORECASE,
)


def _base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _make_session(cookie_name: str | None = None, cookie_val: str | None = None, host: str | None = None) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        }
    )
    if cookie_name and cookie_val:
        s.cookies.set(cookie_name, cookie_val)
        if host:
            clean_host = host.split("//")[-1].split("/")[0]
            s.cookies.set(cookie_name, cookie_val, domain=clean_host)
            if "substack.com" in clean_host:
                s.cookies.set(cookie_name, cookie_val, domain=".substack.com")
    return s


def resolve_cookie_name(source: SourceConfig) -> tuple[str | None, bool]:
    """Return (resolved_cookie_name, is_paid_authenticated)."""
    if not source.cookie_val:
        return None, False

    base = _base_url(source.url)
    # Pick suitable paid test slug per source
    test_slug = "svif-usa-portfolio"
    if source.key == "cluseau":
        test_slug = "september-2026-portfolio-review"
    elif source.key == "tjstocks":
        test_slug = "stocktok-etf-20"

    test_url = f"{base}/api/v1/posts/{test_slug}"

    unauth_resp = _make_session().get(test_url, timeout=20)
    unauth_len = len(unauth_resp.json().get("body_html") or "") if unauth_resp.ok else 0

    candidates = (
        ["connect.sid", "substack.sid"]
        if source.cookie_name in ("", "auto")
        else [source.cookie_name]
    )

    for cname in candidates:
        sess = _make_session(cname, source.cookie_val, host=base)
        try:
            resp = sess.get(test_url, timeout=20)
            if resp.ok:
                data = resp.json()
                body = data.get("body_html") or ""
                if len(body) > unauth_len or "datawrapper" in body.lower():
                    return cname, True
        except Exception:
            pass

    fallback = source.cookie_name if source.cookie_name not in ("", "auto") else "substack.sid"
    return fallback, False


def run_sbstck_dl(
    source: SourceConfig,
    sbstck_bin: Path,
    cookie_name: str | None,
    after: str | None = None,
    before: str | None = None,
    download_images: bool = True,
) -> int:
    """Invoke sbstck-dl.exe to mirror HTML + images locally for this source."""
    if not sbstck_bin.exists():
        console.print(f"[yellow]Warning: {sbstck_bin} not found, skipping sbstck-dl HTML mirror.[/yellow]")
        return 1

    source.archive_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(sbstck_bin),
        "download",
        "--url",
        source.url,
        "--output",
        str(source.archive_dir),
        "--add-source-url",
        "--download-files",
    ]
    if download_images:
        cmd.append("--download-images")
    if after:
        cmd.extend(["--after", after])
    if before:
        cmd.extend(["--before", before])
    if cookie_name and source.cookie_val:
        cmd.extend(["--cookie_name", cookie_name, "--cookie_val", source.cookie_val])

    console.print(f"[cyan]Running sbstck-dl for {source.display_name} into {source.archive_dir}...[/cyan]")
    proc = subprocess.run(cmd, cwd=str(source.base_dir))
    return proc.returncode


def fetch_all_api_posts(
    source: SourceConfig,
    cookie_name: str | None,
    after: str | None = None,
    before: str | None = None,
    force: bool = False,
) -> list[Path]:
    """Fetch full post JSONs into source.api_posts_dir."""
    base = _base_url(source.url)
    sess = _make_session(cookie_name, source.cookie_val, host=base)
    source.api_posts_dir.mkdir(parents=True, exist_ok=True)

    slugs_meta: dict[str, dict] = {}
    offset = 0
    while True:
        resp = sess.get(
            f"{base}/api/v1/archive",
            params={"sort": "new", "offset": offset, "limit": 50},
            timeout=25,
        )
        if not resp.ok:
            break
        batch = resp.json()
        if not batch:
            break
        for item in batch:
            slug = item.get("slug")
            if not slug:
                continue
            pdate = (item.get("post_date") or "")[:10]
            if after and pdate and pdate < after:
                continue
            if before and pdate and pdate > before:
                continue
            slugs_meta[slug] = item
        offset += len(batch)
        if len(batch) < 50:
            break
        time.sleep(0.25)

    # Always check key portfolio/tracker pages for this source
    for kslug in KEY_PORTFOLIO_SLUGS:
        slugs_meta.setdefault(kslug, {"slug": kslug})

    try:
        sm = sess.get(f"{base}/sitemap.xml", timeout=20)
        if sm.ok:
            for loc in re.findall(r"<loc>(.*?)</loc>", sm.text):
                if "/p/" in loc:
                    s = loc.split("/p/", 1)[1].strip("/").split("?")[0]
                    if s and not after and not before:
                        slugs_meta.setdefault(s, {"slug": s})
    except Exception:
        pass

    saved_paths: list[Path] = []
    total = len(slugs_meta)
    console.print(f"[cyan]Fetching {total} post JSON records for {source.display_name}...[/cyan]")

    for idx, (slug, meta) in enumerate(slugs_meta.items(), 1):
        existing = list(source.api_posts_dir.glob(f"*__{slug}.json"))
        if existing and not force and slug not in KEY_PORTFOLIO_SLUGS:
            try:
                content = json.loads(existing[0].read_text(encoding="utf-8"))
                body = content.get("body_html") or ""
                # If body is substantial and not a paywall stub, reuse existing
                if len(body) > 3000 and "paywall" not in body[-2000:].lower():
                    saved_paths.append(existing[0])
                    continue
            except Exception:
                pass

        url = f"{base}/api/v1/posts/{slug}"
        try:
            r = sess.get(url, timeout=25)
            if not r.ok:
                continue
            data = r.json()
            pdate = (data.get("post_date") or "0000-00-00")[:10]
            out_path = source.api_posts_dir / f"{pdate}__{slug}.json"
            out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            saved_paths.append(out_path)
            if idx % 20 == 0 or slug in KEY_PORTFOLIO_SLUGS:
                body_len = len(data.get("body_html") or "")
                console.print(f"  [{idx}/{total}] Saved {out_path.name} (len={body_len})")
            time.sleep(0.25)
        except Exception as exc:
            console.print(f"  [red][{idx}/{total}] Error fetching {slug}: {exc}[/red]")

    return saved_paths


def extract_datawrapper_datasets(source: SourceConfig) -> list[dict]:
    """Scan all saved posts for Datawrapper embeds and download CSVs for this source."""
    source.datawrapper_dir.mkdir(parents=True, exist_ok=True)
    sess = _make_session()
    discovered: dict[tuple[str, str], dict] = {}

    for jpath in sorted(source.api_posts_dir.glob("*.json")):
        data = json.loads(jpath.read_text(encoding="utf-8"))
        slug = data.get("slug") or jpath.stem
        pdate = (data.get("post_date") or "")[:10]
        body = data.get("body_html") or ""
        for m in DATAWRAPPER_URL_RE.finditer(body):
            chart_id = m.group(1)
            ver = m.group(2) or ""
            discovered[(slug, chart_id)] = {
                "slug": slug,
                "post_date": pdate,
                "title": data.get("title") or "",
                "chart_id": chart_id,
                "version": ver,
                "raw_url": m.group(0),
            }

    if not discovered:
        console.print(f"[dim]No Datawrapper embeds found for {source.display_name}.[/dim]")
        return []

    manifest: list[dict] = []
    console.print(f"[cyan]Found {len(discovered)} Datawrapper embeds in {source.display_name}. Downloading CSVs...[/cyan]")

    for (slug, chart_id), info in discovered.items():
        base_chart_url = f"https://datawrapper.dwcdn.net/{chart_id}/"
        resolved_base = None
        try:
            head_resp = sess.get(base_chart_url, timeout=20)
            m_redir = re.search(r'url=(https://datawrapper\.dwcdn\.net/[^/]+/\d+/)', head_resp.text, re.I)
            if m_redir:
                resolved_base = m_redir.group(1)
            elif head_resp.url and head_resp.url != base_chart_url:
                resolved_base = head_resp.url if head_resp.url.endswith("/") else head_resp.url + "/"
        except Exception:
            pass

        if not resolved_base:
            ver_part = f"{info['version']}/" if info["version"] else "1/"
            resolved_base = f"https://datawrapper.dwcdn.net/{chart_id}/{ver_part}"

        csv_text = None
        used_csv_url = None
        for candidate_name in ("dataset.csv", "data.csv"):
            candidate_url = resolved_base + candidate_name
            try:
                r = sess.get(candidate_url, timeout=20)
                if r.ok and r.text.strip() and not r.text.lstrip().startswith("<!DOCTYPE"):
                    csv_text = r.text
                    used_csv_url = candidate_url
                    break
            except Exception:
                continue

        if not csv_text and not resolved_base.endswith("/1/"):
            fallback_base = f"https://datawrapper.dwcdn.net/{chart_id}/1/"
            for candidate_name in ("dataset.csv", "data.csv"):
                try:
                    r = sess.get(fallback_base + candidate_name, timeout=20)
                    if r.ok and r.text.strip() and not r.text.lstrip().startswith("<!DOCTYPE"):
                        csv_text = r.text
                        used_csv_url = fallback_base + candidate_name
                        break
                except Exception:
                    continue

        if csv_text:
            csv_file = source.datawrapper_dir / f"{info['post_date'] or '0000-00-00'}__{slug}__{chart_id}.csv"
            csv_file.write_text(csv_text, encoding="utf-8")
            first_line = csv_text.splitlines()[0] if csv_text.splitlines() else ""
            row_count = max(0, len(csv_text.splitlines()) - 1)
            entry = {
                **info,
                "resolved_url": used_csv_url,
                "csv_path": str(csv_file.relative_to(source.base_dir)),
                "columns": [c.strip() for c in first_line.split(",")],
                "rows": row_count,
            }
            manifest.append(entry)
            console.print(f"  [green]Saved {csv_file.name}[/green] ({row_count} rows)")

    manifest_path = source.datawrapper_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
