import re
from typing import Iterable

import tldextract

_TLD_EXTRACT = tldextract.TLDExtract(suffix_list_urls=None, cache_dir=None)


def truncate_text(text, limit):
    clean_text = (text or "").strip()
    if len(clean_text) <= limit:
        return clean_text

    return clean_text[:limit].rstrip() + "..."


def build_source_name(url):
    extracted = _TLD_EXTRACT(url)
    if extracted.domain:
        return extracted.domain
    return url


def deduplicate_urls(urls: Iterable[str]):
    result = []
    seen = set()

    for url in urls:
        normalized = (url or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    return result


def aggregate_sources_text(source_rows, total_limit):
    parts = []
    current_size = 0

    for row in source_rows:
        source_url = row.get("source_url", "")
        source_title = row.get("source_title") or ""
        parsed_text = row.get("parsed_text_raw") or ""

        block = (
            f"URL: {source_url}\n"
            f"TITLE: {source_title}\n"
            f"TEXT:\n{parsed_text}\n"
        )

        if current_size >= total_limit:
            break

        allowed = total_limit - current_size
        if len(block) > allowed:
            block = block[:allowed].rstrip()

        parts.append(block)
        current_size += len(block)

    return "\n\n---\n\n".join(parts).strip()


def slugify_sort_name(sort_name: str) -> str:
    normalized = (sort_name or "").strip().lower()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_") or "unknown_sort"
