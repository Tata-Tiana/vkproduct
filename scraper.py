import re
from urllib.parse import urljoin, urlparse

import requests
import tldextract
from bs4 import BeautifulSoup
from readability import Document

_TLD_EXTRACT = tldextract.TLDExtract(suffix_list_urls=None, cache_dir=None)


def normalize_whitespace(text):
    text = text or ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def download_html(url, timeout, user_agent):
    headers = {
        "User-Agent": user_agent,
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.encoding or response.apparent_encoding
    return response.text


def download_binary(url, timeout, user_agent):
    headers = {
        "User-Agent": user_agent,
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.content, response.headers.get("Content-Type", "")


def extract_title(html):
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.text:
        return normalize_whitespace(soup.title.text)
    meta_title = soup.find("meta", attrs={"property": "og:title"})
    if meta_title and meta_title.get("content"):
        return normalize_whitespace(meta_title["content"])
    h1 = soup.find("h1")
    if h1 and h1.text:
        return normalize_whitespace(h1.text)
    return ""


def extract_main_text(html, url):
    try:
        readable_html = Document(html).summary()
    except Exception:
        readable_html = html

    soup = BeautifulSoup(readable_html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    lines = []
    seen = set()
    for line in soup.get_text("\n").splitlines():
        cleaned = normalize_whitespace(line)
        if len(cleaned) < 30:
            continue
        lowered = cleaned.lower()
        if any(
            bad_word in lowered
            for bad_word in ["cookie", "меню", "навигац", "каталог", "корзин", "войти"]
        ):
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        lines.append(cleaned)

    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)

    if len(text) < 120:
        return ""

    return text


def is_probably_photo_url(url):
    lowered = url.lower()
    if any(
        bad_word in lowered
        for bad_word in ["logo", "icon", "sprite", "banner", "placeholder", "favicon"]
    ):
        return False

    return any(ext in lowered for ext in [".jpg", ".jpeg", ".png", ".webp", ".avif"])


def extract_image_urls(html, page_url, limit=5):
    soup = BeautifulSoup(html, "lxml")
    candidates = []

    meta_image = soup.find("meta", attrs={"property": "og:image"})
    if meta_image and meta_image.get("content"):
        candidates.append(urljoin(page_url, meta_image["content"]))

    for img in soup.find_all("img"):
        raw_url = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-original")
            or img.get("data-lazy-src")
        )
        if not raw_url:
            continue

        resolved = urljoin(page_url, raw_url)
        if not is_probably_photo_url(resolved):
            continue

        alt_text = (img.get("alt") or "").lower()
        class_text = " ".join(img.get("class", [])).lower()
        if any(bad_word in alt_text for bad_word in ["logo", "icon"]):
            continue
        if any(bad_word in class_text for bad_word in ["logo", "icon", "avatar"]):
            continue

        candidates.append(resolved)

    result = []
    seen = set()
    for url in candidates:
        normalized = url.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break

    return result


def detect_source_type(url):
    lowered_url = url.lower()
    hostname = _TLD_EXTRACT(url).domain.lower()
    path = urlparse(lowered_url).path

    if any(word in path for word in ["/product", "/catalog", "/shop"]):
        return "shop"
    if any(word in lowered_url for word in ["/forum", "forum."]):
        return "forum"
    if any(word in path for word in ["/blog", "/article", "/news"]):
        return "blog"
    if any(word in hostname for word in ["market", "ozon", "wildberries", "avito"]):
        return "marketplace"
    if any(word in path for word in ["/catalog", "/variety", "/series"]):
        return "catalog"
    return "other"
