import re
from html import unescape
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


MAX_HTML_CHARS = 2_000_000
MIN_TEXT_CHARS = 40


def normalize_url(value: str) -> str:
    url = value.strip()
    if not url:
        raise ValueError("url is required")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("只支持 http 或 https URL。")
    return url


def source_platform_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or "web"


def html_to_text(html: str) -> tuple[str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    for selector in [
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "iframe",
        "nav",
        "footer",
        "header",
        "form",
    ]:
        for node in soup.select(selector):
            node.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else None
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return title, unescape(text).strip()


def strip_html_tags(html: str) -> str:
    _, text = html_to_text(html)
    return text


async def fetch_public_page(url: str, timeout: float = 18) -> dict:
    normalized = normalize_url(url)
    headers = {
        "User-Agent": "GlobalContextDB/0.1 local desktop capture",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = await client.get(normalized)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "xml" not in content_type and "text/plain" not in content_type:
            raise ValueError(f"暂不支持这个内容类型：{content_type or 'unknown'}")
        html = response.text[:MAX_HTML_CHARS]

    title, text = html_to_text(html)
    if len(text) < MIN_TEXT_CHARS:
        raise ValueError("页面正文太少，可能是空页面、登录页或脚本渲染页面。")

    return {
        "url": str(response.url),
        "title": title or str(response.url),
        "text": text,
        "html": html,
        "source_platform": source_platform_from_url(str(response.url)),
    }
