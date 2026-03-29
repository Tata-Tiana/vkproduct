import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from config import (
    DEFAULT_PRODUCT_TYPE,
    EXCLUDED_DOMAINS,
    IMAGE_SEARCH_TOP_N,
    LOCAL_PHOTOS_ROOT,
    MAX_AGGREGATED_TEXT_CHARS,
    MAX_PHOTOS_PER_SORT,
    MAX_PHOTOS_PER_SOURCE,
    MAX_SOURCE_TEXT_CHARS,
    PREFERRED_DOMAINS,
    REQUEST_TIMEOUT,
    SALES_TAIL_TEMPLATES,
    SEARCH_RESULTS_LIMIT,
    SORTS_TO_PROCESS,
    USER_AGENT,
)
from image_search_client import search_sort_image_urls
from llm_client import LLMClient
from models import ProductDraftUpdate
from parser_utils import (
    aggregate_sources_text,
    build_source_name,
    slugify_sort_name,
    truncate_text,
)
from prompts import PROMPT_VERSION
from scraper import (
    detect_source_type,
    download_binary,
    download_html,
    extract_image_urls,
    extract_main_text,
    extract_title,
)
from search_client import search_sort_sources
from supabase_client import SupabaseClient
from vk_client import VKClient


def build_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--sort")

    rebuild_parser = subparsers.add_parser("rebuild")
    rebuild_parser.add_argument("--sort", required=True)

    sources_parser = subparsers.add_parser("sources")
    sources_parser.add_argument("--sort", required=True)

    photos_parser = subparsers.add_parser("photos")
    photos_parser.add_argument("--sort", required=True)
    photos_parser.add_argument("--mode", choices=["page", "query"], default="page")
    photos_parser.add_argument("--limit", type=int)

    photos_local_parser = subparsers.add_parser("photos-local")
    photos_local_parser.add_argument("--sort", required=True)

    vk_categories_parser = subparsers.add_parser("vk-categories")
    vk_categories_parser.add_argument("--count", type=int)
    vk_categories_parser.add_argument("--offset", type=int)
    vk_categories_parser.add_argument("--lang", default="ru")

    vk_add_product_parser = subparsers.add_parser("vk-add-product")
    vk_add_product_parser.add_argument("--sort", required=True)
    vk_add_product_parser.add_argument("--owner-id", type=int, required=True)
    vk_add_product_parser.add_argument("--category-id", type=int, default=10003)
    vk_add_product_parser.add_argument("--price", type=float)
    vk_add_product_parser.add_argument("--old-price", type=float)

    return parser


def load_settings(require_supabase=True, require_openai=True):
    load_dotenv()

    env = {
        "supabase_url": os.getenv("SUPABASE_URL", "").strip(),
        "supabase_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        "openai_api_key": os.getenv("OPENAI_API_KEY", "").strip(),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        "serpapi_api_key": os.getenv("SERPAPI_API_KEY", "").strip(),
        "vk_token": os.getenv("VK_TOKEN", "").strip(),
        "vk_api_version": os.getenv("VK_API_VERSION", "5.199").strip(),
    }

    required_keys = set()
    if require_supabase:
        required_keys.update({"supabase_url", "supabase_key"})
    if require_openai:
        required_keys.add("openai_api_key")

    missing = [key for key in required_keys if not env.get(key)]
    if missing:
        raise ValueError(f"Не заполнены переменные окружения: {', '.join(missing)}")

    return env


def is_url_allowed(url):
    lowered = url.lower()
    return not any(domain in lowered for domain in EXCLUDED_DOMAINS)


def sort_urls(urls):
    preferred = []
    other = []

    for url in urls:
        if any(domain in url.lower() for domain in PREFERRED_DOMAINS):
            preferred.append(url)
        else:
            other.append(url)

    return preferred + other


def get_target_sorts(single_sort=None):
    if single_sort:
        return [single_sort]
    return SORTS_TO_PROCESS


def get_sales_tail_template(product_type):
    return SALES_TAIL_TEMPLATES.get(product_type, "").strip()


def build_final_description(vk_full_description, sales_tail_template):
    main_text = (vk_full_description or "").strip()
    tail = (sales_tail_template or "").strip()

    if main_text and tail:
        return f"{main_text}\n\n{tail}"
    return main_text or tail


def clean_name_part(value):
    if value is None:
        return None

    normalized = " ".join(str(value).strip().split())
    return normalized or None


def build_vk_title(sort_name, product_type, card):
    name_ru = clean_name_part(getattr(card, "name_ru", None))
    name_en = clean_name_part(getattr(card, "name_en", None))
    fallback_name = clean_name_part(sort_name) or "Без названия"

    if product_type == "petunia":
        base_name = name_ru or fallback_name
        if name_en and name_en.casefold() != base_name.casefold():
            return f"Рассада петунии {base_name} ({name_en})"
        return f"Рассада петунии {base_name}"

    if product_type == "tomato":
        base_name = name_ru or fallback_name
        return f"Рассада томата {base_name}"

    return clean_name_part(getattr(card, "vk_title", None)) or fallback_name


def build_draft_update(sort_name, card, aggregated_text, product_type):
    structured = card.model_dump(exclude_none=True)
    sales_tail_template = get_sales_tail_template(product_type)
    vk_final_description = build_final_description(
        card.vk_full_description,
        sales_tail_template,
    )
    vk_title = build_vk_title(sort_name, product_type, card)
    structured["vk_title"] = vk_title

    return ProductDraftUpdate(
        **structured,
        sales_tail_template=sales_tail_template,
        vk_final_description=vk_final_description,
        parsed_description_raw=aggregated_text,
        ai_description_structured=structured,
        ai_description_vk=vk_final_description,
        ai_prompt_version=PROMPT_VERSION,
        status="ai_ready",
    )


def build_sort_photo_dir(sort_name):
    return Path(LOCAL_PHOTOS_ROOT) / slugify_sort_name(sort_name)


def resolve_vk_price(draft, cli_price=None):
    if cli_price is not None:
        return cli_price

    draft_price = draft.get("price")
    if draft_price is None:
        raise ValueError(
            "Цена не передана через --price и не заполнена в vk_products_drafts.price"
        )

    try:
        return float(draft_price)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Некорректная цена в vk_products_drafts.price: {draft_price}"
        ) from error


def extract_market_item_id(vk_response):
    if isinstance(vk_response, dict):
        item_id = vk_response.get("market_item_id")
        if item_id is None:
            raise ValueError(f"VK вернул неожиданный ответ market.add: {vk_response}")
        return item_id

    if isinstance(vk_response, int):
        return vk_response

    raise ValueError(f"VK вернул неожиданный тип ответа market.add: {vk_response!r}")


def show_local_photos(sort_name):
    photo_dir = build_sort_photo_dir(sort_name)
    if not photo_dir.exists():
        print(f"Локальная папка с фото не найдена: {photo_dir}", flush=True)
        return {"sort_processed": 1, "photos_found": 0, "errors": 1}

    files = sorted(path for path in photo_dir.iterdir() if path.is_file())
    if not files:
        print(f"В папке нет файлов: {photo_dir}", flush=True)
        return {"sort_processed": 1, "photos_found": 0, "errors": 1}

    print(f"Локальная папка фото: {photo_dir}", flush=True)
    print(f"Абсолютный путь: {photo_dir.resolve()}", flush=True)
    for index, path in enumerate(files, start=1):
        print(f"{index}. {path.name}", flush=True)

    return {"sort_processed": 1, "photos_found": len(files), "errors": 0}


def show_vk_categories(vk_client, count, offset, lang):
    response = vk_client.get_market_categories(
        lang=lang,
        count=count,
        offset=offset,
    )
    items = response.get("items", [])
    total_count = response.get("count", len(items))

    print(
        f"VK market categories: total={total_count}, returned={len(items)}, "
        f"offset={offset}, lang={lang}",
        flush=True,
    )
    for item in items:
        section = item.get("section") or {}
        section_name = section.get("name")
        line = f"{item.get('id')}: {item.get('name')}"
        if section_name:
            line += f" | section: {section_name}"
        print(line, flush=True)

    return {
        "categories_found": len(items),
        "total_count": total_count,
        "errors": 0,
    }


def upload_market_photos(vk_client, owner_id, photo_files):
    group_id = abs(owner_id)
    uploaded_photo_ids = []

    for index, photo_path in enumerate(photo_files):
        is_main = len(uploaded_photo_ids) == 0
        print(f"Загружаем фото в VK: {photo_path.name}", flush=True)
        upload_server = vk_client.get_market_upload_server(
            group_id=group_id,
            main_photo=is_main,
        )
        upload_payload = vk_client.upload_photo_to_url(
            upload_server["upload_url"],
            photo_path,
        )
        if not all(key in upload_payload for key in ("photo", "server", "hash")):
            print(
                f"Пропускаем фото {photo_path.name}: VK upload server вернул "
                f"неполный ответ {sorted(upload_payload.keys())}",
                flush=True,
            )
            continue

        saved = vk_client.save_market_photo(
            group_id=group_id,
            photo=upload_payload["photo"],
            server=upload_payload["server"],
            hash_value=upload_payload["hash"],
            crop_data=upload_payload.get("crop_data"),
            crop_hash=upload_payload.get("crop_hash"),
        )
        if not saved:
            raise RuntimeError(f"VK не вернул сохраненную фотографию для {photo_path.name}")

        uploaded_photo_ids.append(saved[0]["id"])

    if not uploaded_photo_ids:
        raise RuntimeError("Не удалось загрузить ни одной фотографии в VK Market")

    return uploaded_photo_ids


def add_vk_product(sort_name, supabase, vk_client, owner_id, category_id, price, old_price=None):
    draft = supabase.get_product_draft(sort_name)
    if not draft:
        raise ValueError(f"Черновик не найден для сорта: {sort_name}")

    if (draft.get("status") or "").strip() != "ai_ready":
        raise ValueError(
            f"Сорт {sort_name} еще не готов к публикации: status={draft.get('status')}"
        )

    title = (draft.get("vk_title") or "").strip()
    description = (
        draft.get("vk_final_description")
        or draft.get("vk_full_description")
        or ""
    ).strip()
    if not title:
        raise ValueError(f"У сорта {sort_name} нет vk_title")
    if len(description) < 10:
        raise ValueError(f"У сорта {sort_name} слишком короткое описание для VK Market")

    photo_dir = build_sort_photo_dir(sort_name)
    if not photo_dir.exists():
        raise ValueError(f"Папка с фото не найдена: {photo_dir}")

    photo_files = sorted(path for path in photo_dir.iterdir() if path.is_file())
    if not photo_files:
        raise ValueError(f"В папке {photo_dir} нет фото для публикации")

    resolved_price = resolve_vk_price(draft, price)
    limited_photos = photo_files[:5]
    photo_ids = upload_market_photos(vk_client, owner_id, limited_photos)
    main_photo_id = photo_ids[0]
    additional_photo_ids = photo_ids[1:]

    vk_response = vk_client.add_market_product(
        owner_id=owner_id,
        name=title,
        description=description,
        category_id=category_id,
        price=resolved_price,
        main_photo_id=main_photo_id,
        photo_ids=additional_photo_ids,
        old_price=old_price,
    )
    item_id = extract_market_item_id(vk_response)

    supabase.update_product_draft(
        draft["id"],
        {
            "vk_product_id": item_id,
            "vk_category_id": category_id,
            "vk_sync_status": "published",
        },
    )

    print(
        f"Товар добавлен в VK Market: item_id={item_id}, owner_id={owner_id}, "
        f"category_id={category_id}",
        flush=True,
    )
    return {
        "item_id": item_id,
        "photos_uploaded": len(photo_ids),
        "errors": 0,
    }


def guess_extension(image_url, content_type):
    lowered_url = (image_url or "").lower()
    lowered_type = (content_type or "").lower()

    if ".png" in lowered_url or "image/png" in lowered_type:
        return ".png"
    if ".webp" in lowered_url or "image/webp" in lowered_type:
        return ".webp"
    if ".avif" in lowered_url or "image/avif" in lowered_type:
        return ".avif"
    return ".jpg"


def download_image_urls_to_dir(sort_name, image_urls, limit):
    photo_dir = build_sort_photo_dir(sort_name)
    photo_dir.mkdir(parents=True, exist_ok=True)
    saved_photos = 0
    seen_image_urls = set()

    for image_url in image_urls:
        if saved_photos >= limit:
            break
        if image_url in seen_image_urls:
            continue

        seen_image_urls.add(image_url)
        try:
            content, content_type = download_binary(image_url, REQUEST_TIMEOUT, USER_AGENT)
            if not content or len(content) < 2048:
                print(f"Пропускаем слишком маленькое изображение: {image_url}", flush=True)
                continue

            extension = guess_extension(image_url, content_type)
            filename = f"{saved_photos + 1:02d}{extension}"
            destination = photo_dir / filename
            destination.write_bytes(content)
            saved_photos += 1
            print(f"Сохранили фото: {destination}", flush=True)
        except Exception as error:
            print(f"Ошибка загрузки фото {image_url}: {error}", flush=True)

    if saved_photos == 0:
        print(f"Не удалось сохранить фото для сорта: {sort_name}", flush=True)
        return {"sort_processed": 1, "photos_saved": 0, "errors": 1}

    print(f"Фото сохранены в папку: {build_sort_photo_dir(sort_name)}", flush=True)
    return {"sort_processed": 1, "photos_saved": saved_photos, "errors": 0}


def download_sort_photos_by_page(sort_name, limit):
    candidate_urls = search_sort_sources(sort_name, SEARCH_RESULTS_LIMIT)
    candidate_urls = [url for url in sort_urls(candidate_urls) if is_url_allowed(url)]

    if not candidate_urls:
        print(f"Нет candidate URLs для фото сорта: {sort_name}", flush=True)
        return {"sort_processed": 1, "photos_saved": 0, "errors": 1}

    image_urls = []

    for page_url in candidate_urls:
        if len(image_urls) >= limit:
            break

        print(f"Ищем фото на странице: {page_url}", flush=True)
        try:
            html = download_html(page_url, REQUEST_TIMEOUT, USER_AGENT)
            extracted = extract_image_urls(
                html,
                page_url,
                limit=MAX_PHOTOS_PER_SOURCE,
            )
        except Exception as error:
            print(f"Ошибка получения фото со страницы {page_url}: {error}", flush=True)
            continue

        if not extracted:
            print(f"Фото не найдены: {page_url}", flush=True)
            continue

        image_urls.extend(extracted)

    return download_image_urls_to_dir(sort_name, image_urls, limit)


def download_sort_photos_by_query(sort_name, serpapi_api_key, limit):
    print(f"Ищем фото по запросу для сорта: {sort_name}", flush=True)
    image_urls = search_sort_image_urls(
        sort_name=sort_name,
        serpapi_api_key=serpapi_api_key,
        limit=limit,
    )
    if not image_urls:
        print(f"Поиск картинок ничего не вернул для сорта: {sort_name}", flush=True)
        return {"sort_processed": 1, "photos_saved": 0, "errors": 1}

    return download_image_urls_to_dir(sort_name, image_urls, limit)


def scrape_and_store_sources(sort_name, draft, supabase):
    candidate_urls = search_sort_sources(sort_name, SEARCH_RESULTS_LIMIT)
    candidate_urls = [url for url in sort_urls(candidate_urls) if is_url_allowed(url)]

    if not candidate_urls:
        print(f"Нет candidate URLs для сорта: {sort_name}", flush=True)
        return [], 0

    print(f"Найдено candidate URLs: {len(candidate_urls)}", flush=True)
    saved_sources = 0

    for url in candidate_urls:
        print(f"Скрапим URL: {url}", flush=True)
        try:
            html = download_html(url, REQUEST_TIMEOUT, USER_AGENT)
            title = extract_title(html)
            text = extract_main_text(html, url)
            cleaned_text = truncate_text(text, MAX_SOURCE_TEXT_CHARS)

            if not cleaned_text:
                print(f"Пустой текст после очистки: {url}", flush=True)
                continue

            inserted = supabase.insert_source(
                product_id=draft["id"],
                source_url=url,
                source_name=build_source_name(url),
                source_type=detect_source_type(url),
                source_title=title,
                parsed_text_raw=cleaned_text,
            )
            if inserted:
                saved_sources += 1
        except Exception as error:
            print(f"Ошибка обработки URL {url}: {error}", flush=True)

    return supabase.get_selected_sources(draft["id"]), saved_sources


def rebuild_from_sources(sort_name, supabase, llm):
    draft = supabase.get_or_create_product_draft(sort_name, DEFAULT_PRODUCT_TYPE)
    product_type = draft.get("product_type") or DEFAULT_PRODUCT_TYPE
    selected_sources = supabase.get_selected_sources(draft["id"])

    if not selected_sources:
        print(f"Нет выбранных источников для сорта: {sort_name}", flush=True)
        return {
            "sort_processed": 1,
            "sources_saved": 0,
            "cards_updated": 0,
            "errors": 1,
        }

    aggregated_text = aggregate_sources_text(selected_sources, MAX_AGGREGATED_TEXT_CHARS)
    if not aggregated_text:
        print(f"Не удалось собрать агрегированный текст для сорта: {sort_name}", flush=True)
        return {
            "sort_processed": 1,
            "sources_saved": 0,
            "cards_updated": 0,
            "errors": 1,
        }

    try:
        card = llm.build_product_card(sort_name, aggregated_text, product_type=product_type)
    except Exception as error:
        print(f"LLM не смог пересобрать карточку для {sort_name}: {error}", flush=True)
        return {
            "sort_processed": 1,
            "sources_saved": 0,
            "cards_updated": 0,
            "errors": 1,
        }

    payload = build_draft_update(sort_name, card, aggregated_text, product_type)
    supabase.update_product_draft(draft["id"], payload)
    print(f"Карточка обновлена: {sort_name}", flush=True)
    return {
        "sort_processed": 1,
        "sources_saved": 0,
        "cards_updated": 1,
        "errors": 0,
    }


def run_sort(sort_name, supabase, llm):
    print(f"Обрабатываем сорт: {sort_name}", flush=True)
    draft = supabase.get_or_create_product_draft(sort_name, DEFAULT_PRODUCT_TYPE)
    product_type = draft.get("product_type") or DEFAULT_PRODUCT_TYPE
    selected_sources, saved_sources = scrape_and_store_sources(sort_name, draft, supabase)

    if not selected_sources:
        print(f"Нет выбранных источников после скрапинга для сорта: {sort_name}", flush=True)
        return {
            "sort_processed": 1,
            "sources_saved": saved_sources,
            "cards_updated": 0,
            "errors": 1,
        }

    aggregated_text = aggregate_sources_text(selected_sources, MAX_AGGREGATED_TEXT_CHARS)
    if not aggregated_text:
        print(f"Пустой агрегированный текст для сорта: {sort_name}", flush=True)
        return {
            "sort_processed": 1,
            "sources_saved": saved_sources,
            "cards_updated": 0,
            "errors": 1,
        }

    try:
        card = llm.build_product_card(
            sort_name,
            aggregated_text,
            product_type=product_type,
        )
    except Exception as error:
        print(f"LLM не смог собрать карточку для {sort_name}: {error}", flush=True)
        return {
            "sort_processed": 1,
            "sources_saved": saved_sources,
            "cards_updated": 0,
            "errors": 1,
        }

    payload = build_draft_update(sort_name, card, aggregated_text, product_type)
    supabase.update_product_draft(draft["id"], payload)
    print(f"Карточка сохранена: {sort_name}", flush=True)
    return {
        "sort_processed": 1,
        "sources_saved": saved_sources,
        "cards_updated": 1,
        "errors": 0,
    }


def show_sources(sort_name, supabase):
    draft = supabase.get_product_draft(sort_name)
    if not draft:
        print(f"Черновик не найден для сорта: {sort_name}", flush=True)
        return

    sources = supabase.get_all_sources(draft["id"])
    if not sources:
        print(f"Источники не найдены для сорта: {sort_name}", flush=True)
        return

    print(f"Источники для {sort_name}:", flush=True)
    for index, row in enumerate(sources, start=1):
        print(
            f"{index}. {row.get('source_url')} | {row.get('source_title')} | "
            f"is_selected={row.get('is_selected')}",
            flush=True,
        )


def main():
    parser = build_parser()
    args = parser.parse_args()

    settings = load_settings(
        require_supabase=args.command in {"run", "rebuild", "sources", "vk-add-product"},
        require_openai=args.command in {"run", "rebuild"},
    )
    supabase = None
    llm = None
    vk_client = None
    if args.command in {"run", "rebuild", "sources"}:
        supabase = SupabaseClient(settings["supabase_url"], settings["supabase_key"])
    if args.command in {"run", "rebuild"}:
        llm = LLMClient(settings["openai_api_key"], settings["openai_model"])
    if args.command in {"vk-categories", "vk-add-product"}:
        if not settings["vk_token"]:
            raise ValueError("Не заполнена переменная окружения: VK_TOKEN")
        vk_client = VKClient(settings["vk_token"], settings["vk_api_version"])
    if args.command == "vk-add-product":
        supabase = SupabaseClient(settings["supabase_url"], settings["supabase_key"])

    try:
        if args.command == "run":
            summary = {
                "sort_processed": 0,
                "sources_saved": 0,
                "cards_updated": 0,
                "errors": 0,
            }
            for sort_name in get_target_sorts(args.sort):
                result = run_sort(sort_name, supabase, llm)
                for key in summary:
                    summary[key] += result.get(key, 0)
            print(
                "SUMMARY: "
                f"sorts={summary['sort_processed']}, "
                f"sources_saved={summary['sources_saved']}, "
                f"cards_updated={summary['cards_updated']}, "
                f"errors={summary['errors']}",
                flush=True,
            )
            return

        if args.command == "rebuild":
            result = rebuild_from_sources(args.sort, supabase, llm)
            if result:
                print(
                    "SUMMARY: "
                    f"sorts={result['sort_processed']}, "
                    f"sources_saved={result['sources_saved']}, "
                    f"cards_updated={result['cards_updated']}, "
                    f"errors={result['errors']}",
                    flush=True,
                )
            return

        if args.command == "sources":
            show_sources(args.sort, supabase)
            return

        if args.command == "photos":
            limit = args.limit or (IMAGE_SEARCH_TOP_N if args.mode == "query" else MAX_PHOTOS_PER_SORT)
            if args.mode == "query":
                result = download_sort_photos_by_query(
                    args.sort,
                    settings["serpapi_api_key"],
                    limit,
                )
            else:
                result = download_sort_photos_by_page(args.sort, limit)
            print(
                "SUMMARY: "
                f"sorts={result['sort_processed']}, "
                f"photos_saved={result['photos_saved']}, "
                f"errors={result['errors']}",
                flush=True,
            )
            return

        if args.command == "photos-local":
            result = show_local_photos(args.sort)
            print(
                "SUMMARY: "
                f"sorts={result['sort_processed']}, "
                f"photos_found={result['photos_found']}, "
                f"errors={result['errors']}",
                flush=True,
            )
            return

        if args.command == "vk-categories":
            result = show_vk_categories(
                vk_client,
                count=args.count,
                offset=args.offset,
                lang=args.lang,
            )
            print(
                "SUMMARY: "
                f"categories_found={result['categories_found']}, "
                f"total_count={result['total_count']}, "
                f"errors={result['errors']}",
                flush=True,
            )
            return

        if args.command == "vk-add-product":
            result = add_vk_product(
                sort_name=args.sort,
                supabase=supabase,
                vk_client=vk_client,
                owner_id=args.owner_id,
                category_id=args.category_id,
                price=args.price,
                old_price=args.old_price,
            )
            print(
                "SUMMARY: "
                f"item_id={result['item_id']}, "
                f"photos_uploaded={result['photos_uploaded']}, "
                f"errors={result['errors']}",
                flush=True,
            )
            return
    except Exception as error:
        print(f"Ошибка выполнения пайплайна: {error}", flush=True)
        print(
            "Проверьте .env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY, "
            "а также доступ к сети и корректность DNS.",
            flush=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
