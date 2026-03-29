import requests

from config import SORT_IMAGE_QUERY_ALIASES


def build_image_queries(sort_name):
    queries = [sort_name]
    queries.extend(SORT_IMAGE_QUERY_ALIASES.get(sort_name, []))

    result = []
    seen = set()
    for query in queries:
        normalized = (query or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def search_sort_image_urls(sort_name, serpapi_api_key, limit=20):
    if not serpapi_api_key:
        raise ValueError("Для поиска картинок по запросу нужен SERPAPI_API_KEY в .env")

    image_urls = []
    seen = set()

    for query in build_image_queries(sort_name):
        response = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_images",
                "q": query,
                "ijn": "0",
                "api_key": serpapi_api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        for item in payload.get("images_results", []):
            candidate = item.get("original") or item.get("image") or item.get("thumbnail")
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            image_urls.append(candidate)
            if len(image_urls) >= limit:
                return image_urls

    return image_urls
