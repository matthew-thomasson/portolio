from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import SourceConfig

CASHTAG_RE = re.compile(r'data-component-name="CashtagToDOM"', re.IGNORECASE)
STOCKTICKER_RE = re.compile(r'data-component-name="StockTicker[^"]*"', re.IGNORECASE)
IMAGE_TAG_RE = re.compile(r"<img\b", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass
class SourceAnomaly:
    severity: str  # "CRITICAL", "WARNING", "INFO"
    category: str  # "EMPTY_FILE", "CORRUPT_JSON", "PAYWALL_STUB", "EMPTY_NEWSLETTER_BODY", "MEDIA_ONLY_POST", "MISSING_CHAT_REPLIES", "DUPLICATE_ID", "MALFORMED_TIMESTAMP", "IMAGE_REVIEW_LIMITATION", "CORRUPT_CSV"
    item_id: str
    file_path: str
    detail: str


@dataclass
class SourceIngestionReport:
    source_key: str
    source_name: str
    is_valid: bool
    author_user_ids: list[int]
    author_handles: list[str]
    posts_total_files: int
    posts_valid_count: int
    posts_newsletter_count: int
    posts_media_only_count: int
    posts_paid_count: int
    posts_paywall_truncated_count: int
    posts_empty_or_corrupt_count: int
    cashtag_widgets_count: int
    stock_ticker_widgets_count: int
    chat_threads_count: int
    chat_author_threads_count: int
    chat_threads_with_comments: int
    chat_threads_missing_replies: int
    chat_replies_total_count: int
    chat_author_replies_count: int
    datawrapper_csv_count: int
    datawrapper_corrupt_count: int
    anomalies: list[SourceAnomaly] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_publication_authors(source: SourceConfig) -> tuple[set[int], set[str]]:
    """Automatically identify publication author user IDs and handles from archived posts and admin chat roles."""
    author_ids: set[int] = set()
    author_handles: set[str] = set()

    if source.api_posts_dir.exists():
        for jpath in sorted(source.api_posts_dir.glob("*.json")):
            if jpath.stat().st_size == 0:
                continue
            try:
                data = json.loads(jpath.read_text(encoding="utf-8"))
            except Exception:
                continue
            for byline in data.get("publishedBylines") or []:
                if not isinstance(byline, dict):
                    continue
                uid = byline.get("id")
                if uid is not None:
                    try:
                        author_ids.add(int(uid))
                    except (TypeError, ValueError):
                        pass
                handle = str(byline.get("handle") or "").strip().lower()
                if handle:
                    author_handles.add(handle)

    threads_file = source.chat_dir / "chat_threads.json"
    if not threads_file.exists():
        threads_file = source.base_dir / "chat_threads.json"
    if threads_file.exists() and threads_file.stat().st_size > 0:
        try:
            threads = json.loads(threads_file.read_text(encoding="utf-8"))
            if isinstance(threads, list):
                for item in threads:
                    cp = item.get("communityPost") or item
                    role = str(cp.get("pub_role") or item.get("pubRole") or "").lower()
                    user = cp.get("user") or item.get("user") or {}
                    u_role = str(user.get("pubRole") or user.get("role") or role).lower()
                    if u_role in ("admin", "owner", "author", "contributor"):
                        uid = user.get("id") or cp.get("user_id")
                        if uid is not None:
                            try:
                                author_ids.add(int(uid))
                            except (TypeError, ValueError):
                                pass
                        handle = str(user.get("handle") or "").strip().lower()
                        if handle:
                            author_handles.add(handle)
        except Exception:
            pass

    return author_ids, author_handles


def validate_source_archive(source: SourceConfig, save_report: bool = True) -> SourceIngestionReport:
    """Perform explicit, non-silent completeness and integrity validation on all raw source files."""
    anomalies: list[SourceAnomaly] = []
    author_ids, author_handles = discover_publication_authors(source)

    posts_total = 0
    posts_valid = 0
    posts_newsletter = 0
    posts_media_only = 0
    posts_paid = 0
    posts_paywall_truncated = 0
    posts_empty_or_corrupt = 0
    cashtag_count = 0
    stockticker_count = 0
    seen_post_ids: set[str] = set()

    if source.api_posts_dir.exists():
        for jpath in sorted(source.api_posts_dir.glob("*.json")):
            posts_total += 1
            rel_path = str(jpath.relative_to(source.base_dir))
            if jpath.stat().st_size == 0:
                posts_empty_or_corrupt += 1
                anomalies.append(
                    SourceAnomaly(
                        severity="CRITICAL",
                        category="EMPTY_FILE",
                        item_id=jpath.stem,
                        file_path=rel_path,
                        detail="0-byte post JSON file; re-run downloader with force/repair.",
                    )
                )
                continue

            try:
                data = json.loads(jpath.read_text(encoding="utf-8"))
            except Exception as exc:
                posts_empty_or_corrupt += 1
                anomalies.append(
                    SourceAnomaly(
                        severity="CRITICAL",
                        category="CORRUPT_JSON",
                        item_id=jpath.stem,
                        file_path=rel_path,
                        detail=f"Invalid JSON syntax: {exc}",
                    )
                )
                continue

            if not isinstance(data, dict):
                posts_empty_or_corrupt += 1
                anomalies.append(
                    SourceAnomaly(
                        severity="CRITICAL",
                        category="CORRUPT_JSON",
                        item_id=jpath.stem,
                        file_path=rel_path,
                        detail="Post JSON root is not an object.",
                    )
                )
                continue

            pid = str(data.get("id") or data.get("slug") or jpath.stem)
            slug = str(data.get("slug") or jpath.stem)
            if pid in seen_post_ids:
                anomalies.append(
                    SourceAnomaly(
                        severity="WARNING",
                        category="DUPLICATE_ID",
                        item_id=slug,
                        file_path=rel_path,
                        detail=f"Duplicate post ID {pid} encountered in archive.",
                    )
                )
            seen_post_ids.add(pid)

            pdate = str(data.get("post_date") or "")
            if not ISO_DATE_RE.match(pdate):
                anomalies.append(
                    SourceAnomaly(
                        severity="WARNING",
                        category="MALFORMED_TIMESTAMP",
                        item_id=slug,
                        file_path=rel_path,
                        detail=f"Missing or malformed post_date: '{pdate}'",
                    )
                )

            ptype = str(data.get("type") or "newsletter").lower()
            audience = str(data.get("audience") or "everyone").lower()
            title = str(data.get("title") or "")
            body = str(data.get("body_html") or "")

            if audience == "only_paid":
                posts_paid += 1

            cashtag_count += len(CASHTAG_RE.findall(body))
            stockticker_count += len(STOCKTICKER_RE.findall(body))

            if ptype in ("podcast", "video") and len(body.strip()) < 300:
                posts_media_only += 1
                posts_valid += 1
                if any(k in title.lower() for k in ("buy", "bought", "selling", "sold", "portfolio", "stock")):
                    anomalies.append(
                        SourceAnomaly(
                            severity="INFO",
                            category="MEDIA_ONLY_POST",
                            item_id=slug,
                            file_path=rel_path,
                            detail=f"Audio/video post ({ptype}) '{title}' has minimal HTML body ({len(body)} chars); trade details if any reside in audio/video.",
                        )
                    )
                continue

            posts_newsletter += 1
            if not body.strip():
                posts_empty_or_corrupt += 1
                anomalies.append(
                    SourceAnomaly(
                        severity="CRITICAL" if audience == "only_paid" else "WARNING",
                        category="EMPTY_NEWSLETTER_BODY",
                        item_id=slug,
                        file_path=rel_path,
                        detail=f"Newsletter post '{title}' ({audience}) has empty body_html.",
                    )
                )
                continue

            if audience == "only_paid":
                m_jump = re.search(r'<div[^>]*data-component-name="PaywallToDOM"[^>]*></div>', body, re.IGNORECASE)
                is_paywall_stub = bool(data.get("paywallInfo")) or ("paywall-preview" in body.lower())
                if m_jump and not is_paywall_stub:
                    after_jump = body[m_jump.end():].strip()
                    if not after_jump:
                        plain_words = len(re.sub(r"<[^>]+>", " ", body).split())
                        expected_words = int(data.get("wordcount") or 0)
                        if (expected_words > 0 and plain_words < expected_words * 0.75) or (expected_words == 0 and len(body) < 5000):
                            is_paywall_stub = True
                if is_paywall_stub:
                    posts_paywall_truncated += 1
                    anomalies.append(
                        SourceAnomaly(
                            severity="CRITICAL",
                            category="PAYWALL_STUB",
                            item_id=slug,
                            file_path=rel_path,
                            detail=f"Paid post '{title}' is truncated at paywall ({len(body)} chars).",
                        )
                    )
                    continue

            # Flag portfolio review posts that embed screenshots/images instead of HTML tables
            if any(k in title.lower() or k in slug.lower() for k in ("portfolio review", "trade review", "portfolio update")):
                img_cnt = len(IMAGE_TAG_RE.findall(body))
                has_html_table = "<table" in body.lower() or "datawrapper" in body.lower()
                if img_cnt > 0 and not has_html_table:
                    anomalies.append(
                        SourceAnomaly(
                            severity="INFO",
                            category="IMAGE_REVIEW_LIMITATION",
                            item_id=slug,
                            file_path=rel_path,
                            detail=f"Review post '{title}' contains {img_cnt} embedded image(s) and no HTML/Datawrapper table; full holdings table may be inside an image.",
                        )
                    )

            posts_valid += 1

    # Validate Chat Threads & Replies
    chat_threads_count = 0
    chat_author_threads_count = 0
    chat_threads_with_comments = 0
    chat_threads_missing_replies = 0
    chat_replies_total = 0
    chat_author_replies = 0

    threads_path = source.chat_dir / "chat_threads.json"
    if not threads_path.exists() and (source.base_dir / "chat_threads.json").exists():
        threads_path = source.base_dir / "chat_threads.json"

    replies_path = source.chat_dir / "chat_replies.json"

    replies_map: dict[str, list[dict]] = {}
    if replies_path.exists():
        if replies_path.stat().st_size == 0:
            anomalies.append(
                SourceAnomaly(
                    severity="CRITICAL",
                    category="EMPTY_FILE",
                    item_id="chat_replies",
                    file_path=str(replies_path.relative_to(source.base_dir)),
                    detail="chat_replies.json is 0 bytes.",
                )
            )
        else:
            try:
                loaded_rep = json.loads(replies_path.read_text(encoding="utf-8"))
                if isinstance(loaded_rep, dict):
                    replies_map = loaded_rep
                else:
                    anomalies.append(
                        SourceAnomaly(
                            severity="CRITICAL",
                            category="CORRUPT_JSON",
                            item_id="chat_replies",
                            file_path=str(replies_path.relative_to(source.base_dir)),
                            detail="chat_replies.json root must be a dict mapping thread_id -> comments list.",
                        )
                    )
            except Exception as exc:
                anomalies.append(
                    SourceAnomaly(
                        severity="CRITICAL",
                        category="CORRUPT_JSON",
                        item_id="chat_replies",
                        file_path=str(replies_path.relative_to(source.base_dir)),
                        detail=f"Invalid JSON in chat_replies.json: {exc}",
                    )
                )

    seen_thread_ids: set[str] = set()
    if threads_path.exists():
        if threads_path.stat().st_size == 0:
            anomalies.append(
                SourceAnomaly(
                    severity="CRITICAL",
                    category="EMPTY_FILE",
                    item_id="chat_threads",
                    file_path=str(threads_path.relative_to(source.base_dir)),
                    detail="chat_threads.json is 0 bytes.",
                )
            )
        else:
            try:
                threads_list = json.loads(threads_path.read_text(encoding="utf-8"))
                if not isinstance(threads_list, list):
                    anomalies.append(
                        SourceAnomaly(
                            severity="CRITICAL",
                            category="CORRUPT_JSON",
                            item_id="chat_threads",
                            file_path=str(threads_path.relative_to(source.base_dir)),
                            detail="chat_threads.json root must be a list.",
                        )
                    )
                    threads_list = []

                for item in threads_list:
                    cp = item.get("communityPost") or item
                    tid = str(cp.get("id") or "")
                    if tid:
                        if tid in seen_thread_ids:
                            anomalies.append(
                                SourceAnomaly(
                                    severity="WARNING",
                                    category="DUPLICATE_ID",
                                    item_id=tid,
                                    file_path=str(threads_path.relative_to(source.base_dir)),
                                    detail=f"Duplicate chat thread ID {tid}.",
                                )
                            )
                        seen_thread_ids.add(tid)

                    chat_threads_count += 1
                    user = cp.get("user") or item.get("user") or {}
                    uid = user.get("id") or cp.get("user_id")
                    uhandle = str(user.get("handle") or "").strip().lower()
                    is_auth = (uid is not None and int(uid) in author_ids) or (uhandle and uhandle in author_handles)
                    if is_auth:
                        chat_author_threads_count += 1

                    created = str(cp.get("created_at") or "")
                    if not ISO_DATE_RE.match(created):
                        anomalies.append(
                            SourceAnomaly(
                                severity="WARNING",
                                category="MALFORMED_TIMESTAMP",
                                item_id=tid or "unknown_thread",
                                file_path=str(threads_path.relative_to(source.base_dir)),
                                detail=f"Chat thread has invalid created_at '{created}'.",
                            )
                        )

                    ccount = int(cp.get("comment_count") or 0)
                    if ccount > 0:
                        chat_threads_with_comments += 1
                        fetched_list = replies_map.get(tid)
                        if fetched_list is None:
                            chat_threads_missing_replies += 1
                            anomalies.append(
                                SourceAnomaly(
                                    severity="WARNING",
                                    category="MISSING_CHAT_REPLIES",
                                    item_id=tid,
                                    file_path=str(threads_path.relative_to(source.base_dir)),
                                    detail=f"Thread {tid} reports comment_count={ccount} but has no entry in chat_replies.json.",
                                )
                            )
                        elif ccount > 50 and len(fetched_list) <= 50:
                            chat_threads_missing_replies += 1
                            anomalies.append(
                                SourceAnomaly(
                                    severity="WARNING",
                                    category="TRUNCATED_CHAT_REPLIES",
                                    item_id=tid,
                                    file_path=str(threads_path.relative_to(source.base_dir)),
                                    detail=f"Thread {tid} reports comment_count={ccount} but only {len(fetched_list)} replies were fetched (pagination truncated at 50).",
                                )
                            )
            except Exception as exc:
                anomalies.append(
                    SourceAnomaly(
                        severity="CRITICAL",
                        category="CORRUPT_JSON",
                        item_id="chat_threads",
                        file_path=str(threads_path.relative_to(source.base_dir)),
                        detail=f"Invalid JSON in chat_threads.json: {exc}",
                    )
                )

    def _walk_comments(comments: list[dict]) -> None:
        nonlocal chat_replies_total, chat_author_replies
        for c in comments:
            if not isinstance(c, dict):
                continue
            chat_replies_total += 1
            c_inner = c.get("comment") if isinstance(c.get("comment"), dict) else c
            c_user = c.get("user") if isinstance(c.get("user"), dict) else (c_inner.get("user") or {})
            c_uid = c_user.get("id") or c_inner.get("user_id")
            c_handle = str(c_user.get("handle") or "").strip().lower()
            if (c_uid is not None and int(c_uid) in author_ids) or (c_handle and c_handle in author_handles):
                chat_author_replies += 1
            children = c.get("children") or c.get("replies") or c_inner.get("children") or []
            if isinstance(children, list) and children:
                _walk_comments(children)

    for _tid, clist in replies_map.items():
        if isinstance(clist, list):
            _walk_comments(clist)

    # Validate Datawrapper CSVs
    dw_count = 0
    dw_corrupt = 0
    if source.datawrapper_dir.exists():
        for cpath in sorted(source.datawrapper_dir.glob("*.csv")):
            dw_count += 1
            rel_cpath = str(cpath.relative_to(source.base_dir))
            if cpath.stat().st_size == 0:
                dw_corrupt += 1
                anomalies.append(
                    SourceAnomaly(
                        severity="CRITICAL",
                        category="CORRUPT_CSV",
                        item_id=cpath.stem,
                        file_path=rel_cpath,
                        detail="Datawrapper CSV is 0 bytes.",
                    )
                )
                continue
            try:
                with cpath.open("r", encoding="utf-8", errors="replace") as fh:
                    reader = list(csv.reader(fh))
                if len(reader) < 2:
                    dw_corrupt += 1
                    anomalies.append(
                        SourceAnomaly(
                            severity="WARNING",
                            category="CORRUPT_CSV",
                            item_id=cpath.stem,
                            file_path=rel_cpath,
                            detail="Datawrapper CSV has header only or no data rows.",
                        )
                    )
            except Exception as exc:
                dw_corrupt += 1
                anomalies.append(
                    SourceAnomaly(
                        severity="CRITICAL",
                        category="CORRUPT_CSV",
                        item_id=cpath.stem,
                        file_path=rel_cpath,
                        detail=f"Failed parsing Datawrapper CSV: {exc}",
                    )
                )

    has_critical = any(a.severity == "CRITICAL" for a in anomalies)
    report = SourceIngestionReport(
        source_key=source.key,
        source_name=source.display_name,
        is_valid=(posts_valid > 0 and not has_critical),
        author_user_ids=sorted(author_ids),
        author_handles=sorted(author_handles),
        posts_total_files=posts_total,
        posts_valid_count=posts_valid,
        posts_newsletter_count=posts_newsletter,
        posts_media_only_count=posts_media_only,
        posts_paid_count=posts_paid,
        posts_paywall_truncated_count=posts_paywall_truncated,
        posts_empty_or_corrupt_count=posts_empty_or_corrupt,
        cashtag_widgets_count=cashtag_count,
        stock_ticker_widgets_count=stockticker_count,
        chat_threads_count=chat_threads_count,
        chat_author_threads_count=chat_author_threads_count,
        chat_threads_with_comments=chat_threads_with_comments,
        chat_threads_missing_replies=chat_threads_missing_replies,
        chat_replies_total_count=chat_replies_total,
        chat_author_replies_count=chat_author_replies,
        datawrapper_csv_count=dw_count,
        datawrapper_corrupt_count=dw_corrupt,
        anomalies=anomalies,
    )

    if save_report:
        source.data_dir.mkdir(parents=True, exist_ok=True)
        out_path = source.data_dir / "ingestion_report.json"
        out_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    return report
