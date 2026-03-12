"""URL content extraction for July.

Extracts titles, descriptions and content from URLs.
Special handling for YouTube links (video id, channel, etc.).
Uses only stdlib — no external dependencies.
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request


YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/live/|youtube\.com/embed/)"
    r"([A-Za-z0-9_-]{11})"
)

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
DESC_RE = re.compile(
    r'<meta\s+(?:name|property)=["\'](?:description|og:description)["\']'
    r'\s+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
OG_TITLE_RE = re.compile(
    r'<meta\s+(?:name|property)=["\']og:title["\']'
    r'\s+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
YT_CHANNEL_RE = re.compile(
    r'"ownerChannelName"\s*:\s*"([^"]+)"'
)
YT_DURATION_RE = re.compile(
    r'"lengthSeconds"\s*:\s*"(\d+)"'
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def extract_youtube_id(url: str) -> str | None:
    match = YOUTUBE_RE.search(url)
    return match.group(1) if match else None


def is_youtube_url(url: str) -> bool:
    return extract_youtube_id(url) is not None


def fetch_url_metadata(url: str, timeout: int = 15) -> dict:
    """Fetch basic metadata from a URL.

    Returns a dict with keys: resolved_title, description, content_type,
    youtube_video_id, youtube_channel, youtube_duration, extracted_text, fetch_status.
    """
    result: dict = {
        "url": url,
        "resolved_title": None,
        "description": None,
        "content_type": None,
        "extracted_text": None,
        "youtube_video_id": None,
        "youtube_channel": None,
        "youtube_duration": None,
        "fetch_status": "pending",
    }

    video_id = extract_youtube_id(url)
    if video_id:
        result["youtube_video_id"] = video_id

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            ctype = response.headers.get("Content-Type", "")
            result["content_type"] = ctype

            if "text/html" not in ctype and "text/plain" not in ctype:
                result["fetch_status"] = "fetched_no_html"
                return result

            raw = response.read(512_000)  # max 512 KB
            charset = "utf-8"
            if "charset=" in ctype:
                charset = ctype.split("charset=")[-1].strip().split(";")[0]
            body = raw.decode(charset, errors="replace")

            # Title
            og = OG_TITLE_RE.search(body)
            if og:
                result["resolved_title"] = _clean(og.group(1))
            else:
                title_match = TITLE_RE.search(body)
                if title_match:
                    result["resolved_title"] = _clean(title_match.group(1))

            # Description
            desc_match = DESC_RE.search(body)
            if desc_match:
                result["description"] = _clean(desc_match.group(1))

            # YouTube specifics
            if video_id:
                ch = YT_CHANNEL_RE.search(body)
                if ch:
                    result["youtube_channel"] = ch.group(1)
                dur = YT_DURATION_RE.search(body)
                if dur:
                    secs = int(dur.group(1))
                    mins, secs_rem = divmod(secs, 60)
                    result["youtube_duration"] = f"{mins}m{secs_rem:02d}s"

            # Extracted text — just the first meaningful chunk for non-YouTube
            if not video_id:
                text = _extract_text_from_html(body)
                if text:
                    result["extracted_text"] = text[:2000]

            result["fetch_status"] = "fetched"

    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        result["fetch_status"] = f"error: {exc}"

    return result


def _clean(text: str) -> str:
    return html.unescape(text).strip().replace("\n", " ").replace("\r", "")[:500]


def _extract_text_from_html(body: str) -> str:
    # Remove scripts and styles
    text = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
