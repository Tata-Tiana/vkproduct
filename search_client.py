from config import MANUAL_SOURCE_URLS, SORT_SOURCE_ALIASES
from parser_utils import deduplicate_urls


def search_sort_sources(sort_name, limit):
    candidate_keys = [sort_name]
    candidate_keys.extend(SORT_SOURCE_ALIASES.get(sort_name, []))

    manual_urls = []
    for key in candidate_keys:
        manual_urls.extend(MANUAL_SOURCE_URLS.get(key, []))

    if not manual_urls:
        print(f"Нет ручных URL для сорта: {sort_name}", flush=True)
        return []

    if len(candidate_keys) > 1:
        print(
            f"Ищем источники для {sort_name} с учетом алиасов: {', '.join(candidate_keys[1:])}",
            flush=True,
        )

    urls = deduplicate_urls(manual_urls)
    return urls[:limit]
