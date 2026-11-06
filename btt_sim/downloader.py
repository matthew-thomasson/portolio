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

DATAWRAPPER_URL_RE = re.compile(
    r"https?://(?:datawrapper\.dwcdn\.net|www\.datawrapper\.de/_)/([A-Za-z0-9]+)(?:/(\d+))?/?",
    re.IGNORECASE,
)


def _base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _make_session(
    cookie_name: str | None = None,
    cookie_val: str | None = None,
    host: str | None = None,
) -> requests.Session:
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


def is_post_truncated_or_invalid(data: dict, has_auth_cookie: bool = False) -> tuple[bool, str]:
    """Check whether a saved Substack post JSON is empty, malformed, or paywall-truncated."""
    if not isinstance(data, dict) or not data.get("slug"):
        return True, "missing_slug_or_invalid_object"

    post_type = str(data.get("type") or "newsletter").lower()
    audience = str(data.get("audience") or "everyone").lower()
    body = data.get("body_html") or ""

    # Newsletter text posts should never have completely empty body_html unless paywalled without auth
    if post_type == "newsletter" and not body.strip():
        if audience == "only_paid" and not has_auth_cookie:
            return True, "unauthenticated_paid_empty_body"
        return True, "empty_newsletter_body_html"

    # Detect Substack paywall truncation markers:
    # Note: Unlocked paid posts retain <div class="paywall-jump" data-component-name="PaywallToDOM"></div>
    # at the jump point, followed by the full paid HTML! Truncated posts have NO content after PaywallToDOM
    # or carry non-null paywallInfo.
    if audience == "only_paid":
        if data.get("paywallInfo") or "paywall-preview" in body.lower():
            return True, "paywall_preview_stub"
        m_jump = re.search(r'<div[^>]*data-component-name="PaywallToDOM"[^>]*></div>', body, re.IGNORECASE)
        if m_jump:
            after_jump = body[m_jump.end():].strip()
            if not after_jump:
                # Some authors place an empty PaywallToDOM widget at the very end of a full paid post
                # ("there is nothing below the paywall"). Check wordcount vs body text words.
                plain_words = len(re.sub(r"<[^>]+>", " ", body).split())
                expected_words = int(data.get("wordcount") or 0)
                if expected_words > 0 and plain_words < expected_words * 0.75:
                    return True, "paywall_truncated_at_jump"
                if expected_words == 0 and len(body) < 5000:
                    return True, "paywall_truncated_at_jump"

    return False, "ok"


def resolve_cookie_name(source: SourceConfig) -> tuple[str | None, bool]:
    """Return (resolved_cookie_name, is_paid_authenticated) dynamically for any Substack publication."""
    if not source.cookie_val:
        return None, False

    base = _base_url(source.url)
    unauth_sess = _make_session()

    # Dynamically discover up to 3 paid posts from the publication archive
    # (some authors put an empty paywall at the bottom of a free-to-read post, so test up to 3 paid slugs)
    test_slugs: list[str] = []
    try:
        arch = unauth_sess.get(f"{base}/api/v1/archive", params={"sort": "new", "limit": 50}, timeout=20)
        if arch.ok:
            for item in arch.json():
                if item.get("audience") == "only_paid" and item.get("slug"):
                    test_slugs.append(str(item["slug"]))
                    if len(test_slugs) >= 3:
                        break
            if not test_slugs and arch.json():
                s0 = str(arch.json()[0].get("slug") or "")
                if s0:
                    test_slugs.append(s0)
    except Exception:
        test_slugs = []

    if not test_slugs:
        fallback = source.cookie_name if source.cookie_name not in ("", "auto") else "substack.sid"
        return fallback, False

    candidates = (
        ["connect.sid", "substack.sid"]
        if source.cookie_name in ("", "auto")
        else [source.cookie_name, "substack.sid", "connect.sid"]
    )
    seen_cands: list[str] = []
    for c in candidates:
        if c and c not in seen_cands:
            seen_cands.append(c)

    for test_slug in test_slugs:
        test_url = f"{base}/api/v1/posts/{test_slug}"
        unauth_len = 0
        try:
            unauth_resp = unauth_sess.get(test_url, timeout=20)
            if unauth_resp.ok:
                unauth_len = len(unauth_resp.json().get("body_html") or "")
        except Exception:
            unauth_len = 0

        for cname in seen_cands:
            sess = _make_session(cname, source.cookie_val, host=base)
            try:
                resp = sess.get(test_url, timeout=20)
                if resp.ok:
                    data = resp.json()
                    body = data.get("body_html") or ""
                    if len(body) > unauth_len:
                        return cname, True
            except Exception:
                continue

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
    """Fetch full post JSONs into source.api_posts_dir, automatically repairing 0-byte or truncated files."""
    base = _base_url(source.url)
    sess = _make_session(cookie_name, source.cookie_val, host=base)
    source.api_posts_dir.mkdir(parents=True, exist_ok=True)
    has_auth = bool(cookie_name and source.cookie_val)

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

    # Also discover standalone pages from sitemap.xml (e.g. portfolio hubs/trackers not in chronological archive)
    try:
        sm = sess.get(f"{base}/sitemap.xml", timeout=20)
        if sm.ok:
            for loc in re.findall(r"<loc>(.*?)</loc>", sm.text):
                if "/p/" in loc:
                    s = loc.split("/p/", 1)[1].strip("/").split("?")[0]
                    if s and not after and not before:
                        slugs_meta.setdefault(s, {"slug": s})
    except Exception as exc:
        console.print(f"[yellow]Warning: sitemap check failed for {source.display_name}: {exc}[/yellow]")

    # Also inspect any pre-existing local files (in case 0-byte or corrupt files exist on disk)
    for existing_file in source.api_posts_dir.glob("*.json"):
        if "__" in existing_file.stem:
            s = existing_file.stem.split("__", 1)[1]
            if s and not after and not before:
                slugs_meta.setdefault(s, {"slug": s})

    saved_paths: list[Path] = []
    total = len(slugs_meta)
    console.print(f"[cyan]Fetching/verifying {total} post JSON records for {source.display_name}...[/cyan]")

    for idx, (slug, _meta) in enumerate(slugs_meta.items(), 1):
        existing = sorted(source.api_posts_dir.glob(f"*__{slug}.json"))
        if existing and not force:
            epath = existing[0]
            if epath.stat().st_size > 0:
                try:
                    content = json.loads(epath.read_text(encoding="utf-8"))
                    is_bad, _reason = is_post_truncated_or_invalid(content, has_auth_cookie=has_auth)
                    if not is_bad:
                        saved_paths.append(epath)
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
            if idx % 20 == 0:
                body_len = len(data.get("body_html") or "")
                console.print(f"  [{idx}/{total}] Saved {out_path.name} (len={body_len})")
            time.sleep(0.25)
        except Exception as exc:
            console.print(f"  [red][{idx}/{total}] Error fetching {slug}: {exc}[/red]")

    return saved_paths


def _discover_publication_id(source: SourceConfig, sess: requests.Session, base: str) -> int | None:
    """Resolve numeric Substack publication_id from local posts or archive endpoint."""
    if source.api_posts_dir.exists():
        for jpath in sorted(source.api_posts_dir.glob("*.json")):
            if jpath.stat().st_size == 0:
                continue
            try:
                d = json.loads(jpath.read_text(encoding="utf-8"))
                pid = d.get("publication_id")
                if pid:
                    return int(pid)
            except Exception:
                continue
    try:
        r = sess.get(f"{base}/api/v1/archive", params={"limit": 1}, timeout=20)
        if r.ok and r.json():
            pid = r.json()[0].get("publication_id")
            if pid:
                return int(pid)
    except Exception:
        pass
    return None


def download_chat_archive(
    source: SourceConfig,
    cookie_name: str | None = None,
    force: bool = False,
) -> dict[str, int]:
    """Download all subscriber chat channels, threads, and nested comment replies for a Substack publication."""
    base = _base_url(source.url)
    sess = _make_session(cookie_name, source.cookie_val, host=base)
    source.chat_dir.mkdir(parents=True, exist_ok=True)

    threads_path = source.chat_dir / "chat_threads.json"
    replies_path = source.chat_dir / "chat_replies.json"

    pub_id = _discover_publication_id(source, sess, base)
    if not pub_id:
        console.print(f"[yellow]Could not determine publication_id for {source.display_name}; skipping chat download.[/yellow]")
        return {"channels": 0, "threads": 0, "replies": 0}

    ch_resp = sess.get(f"{base}/api/v1/chat/publications/{pub_id}/channels", timeout=25)
    if not ch_resp.ok:
        console.print(f"[yellow]Chat channels endpoint returned HTTP {ch_resp.status_code} for {source.display_name}.[/yellow]")
        return {"channels": 0, "threads": 0, "replies": 0}

    channels_raw = ch_resp.json()
    channels = channels_raw if isinstance(channels_raw, list) else channels_raw.get("channels", [])
    if not channels:
        return {"channels": 0, "threads": 0, "replies": 0}

    existing_threads_by_id: dict[str, dict] = {}
    if threads_path.exists() and not force:
        try:
            for item in json.loads(threads_path.read_text(encoding="utf-8")):
                cp = item.get("communityPost") or item
                tid = cp.get("id")
                if tid:
                    existing_threads_by_id[str(tid)] = item
        except Exception:
            existing_threads_by_id = {}

    all_threads_by_id: dict[str, dict] = dict(existing_threads_by_id)
    for ch in channels:
        ch_id = ch.get("id")
        if not ch_id:
            continue
        cursor_before: str | None = None
        seen_cursors: set[str] = set()
        while True:
            params: dict[str, str | int] = {"limit": 50}
            if cursor_before:
                params["before"] = cursor_before
            r = sess.get(f"{base}/api/v1/chat/channels/{ch_id}/posts", params=params, timeout=25)
            if not r.ok:
                break
            payload = r.json()
            posts = payload.get("posts", payload) if isinstance(payload, dict) else payload
            if not isinstance(posts, list) or not posts:
                break

            oldest_ts: str | None = None
            new_in_page = 0
            for item in posts:
                cp = item.get("communityPost") or item
                tid = str(cp.get("id") or "")
                created = str(cp.get("created_at") or "")
                if tid:
                    if tid not in all_threads_by_id or force:
                        new_in_page += 1
                    all_threads_by_id[tid] = item
                if created and (oldest_ts is None or created < oldest_ts):
                    oldest_ts = created

            more = payload.get("more") if isinstance(payload, dict) else (len(posts) >= 50)
            if not more or not oldest_ts or oldest_ts in seen_cursors:
                break
            if not force and new_in_page == 0 and existing_threads_by_id:
                break
            seen_cursors.add(oldest_ts)
            cursor_before = oldest_ts
            time.sleep(0.15)

    sorted_threads = sorted(
        all_threads_by_id.values(),
        key=lambda x: str((x.get("communityPost") or x).get("created_at") or ""),
        reverse=True,
    )
    threads_path.write_text(json.dumps(sorted_threads, indent=2, ensure_ascii=False), encoding="utf-8")

    # Fetch nested comments/replies for all threads with comment_count > 0
    replies_by_thread: dict[str, list[dict]] = {}
    if replies_path.exists() and not force:
        try:
            loaded = json.loads(replies_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                replies_by_thread = loaded
        except Exception:
            replies_by_thread = {}

    for item in sorted_threads:
        cp = item.get("communityPost") or item
        tid = str(cp.get("id") or "")
        expected_count = int(cp.get("comment_count") or 0)
        if not tid or expected_count <= 0:
            continue
        cached = replies_by_thread.get(tid)
        if not force and cached is not None and len(cached) >= expected_count:
            continue

        try:
            merged_by_cid: dict[str, dict] = {}
            if cached and not force:
                for c_item in cached:
                    c_inner = c_item.get("comment") or c_item
                    cid = str(c_inner.get("id") or "")
                    if cid:
                        merged_by_cid[cid] = c_item

            cursor_after: str | None = None
            seen_after: set[str] = set()
            while True:
                c_params: dict[str, str | int] = {"limit": 50}
                if cursor_after:
                    c_params["after"] = cursor_after
                rc = sess.get(f"{base}/api/v1/community/posts/{tid}/comments", params=c_params, timeout=25)
                if not rc.ok:
                    break
                cdata = rc.json()
                comments = (
                    cdata.get("replies") or cdata.get("comments") or []
                    if isinstance(cdata, dict)
                    else cdata
                )
                if not isinstance(comments, list) or not comments:
                    break
                newest_ts: str | None = None
                for c_item in comments:
                    c_inner = c_item.get("comment") or c_item
                    cid = str(c_inner.get("id") or "")
                    cts = str(c_inner.get("created_at") or "")
                    if cid:
                        merged_by_cid[cid] = c_item
                    if cts and (newest_ts is None or cts > newest_ts):
                        newest_ts = cts

                more_after = bool(cdata.get("moreAfter") or cdata.get("more")) if isinstance(cdata, dict) else (len(comments) >= 50)
                if not more_after or not newest_ts or newest_ts in seen_after:
                    break
                seen_after.add(newest_ts)
                cursor_after = newest_ts
                time.sleep(0.1)

            if merged_by_cid:
                replies_by_thread[tid] = sorted(
                    merged_by_cid.values(),
                    key=lambda x: str((x.get("comment") or x).get("created_at") or ""),
                )
            time.sleep(0.1)
        except Exception as exc:
            console.print(f"[yellow]Warning: failed fetching comments for thread {tid}: {exc}[/yellow]")

    replies_path.write_text(json.dumps(replies_by_thread, indent=2, ensure_ascii=False), encoding="utf-8")
    total_replies = sum(len(v) for v in replies_by_thread.values())
    console.print(
        f"[green]Saved chat archive for {source.display_name}: "
        f"{len(channels)} channels, {len(sorted_threads)} threads, {total_replies} replies.[/green]"
    )
    return {"channels": len(channels), "threads": len(sorted_threads), "replies": total_replies}


def extract_datawrapper_datasets(source: SourceConfig) -> list[dict]:
    """Scan all saved posts for Datawrapper embeds and download CSVs for this source."""
    source.datawrapper_dir.mkdir(parents=True, exist_ok=True)
    sess = _make_session()
    discovered: dict[tuple[str, str], dict] = {}

    for jpath in sorted(source.api_posts_dir.glob("*.json")):
        if jpath.stat().st_size == 0:
            continue
        try:
            data = json.loads(jpath.read_text(encoding="utf-8"))
        except Exception as exc:
            console.print(f"[yellow]Skipping malformed JSON {jpath.name}: {exc}[/yellow]")
            continue
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
