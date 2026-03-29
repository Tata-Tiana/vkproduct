<div align="center">

# VK Product Parser

### Автоматизация карточек товаров для VK Market

<p>
  Python-проект для полуавтоматического наполнения карточек товаров по сортам петуний и томатов:
  от поиска источников и генерации описания до локальных фото и публикации в VK Market.
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/OpenAI-API-412991?style=flat-square" alt="OpenAI API" />
  <img src="https://img.shields.io/badge/Supabase-Storage%20%26%20Data-3ECF8E?style=flat-square&logo=supabase&logoColor=white" alt="Supabase" />
  <img src="https://img.shields.io/badge/VK-Market-0077FF?style=flat-square" alt="VK Market" />
</p>

</div>

## Что умеет

- собирает источники по сорту и сохраняет их в Supabase;
- вытягивает и агрегирует полезный текст со страниц;
- генерирует описание карточки через OpenAI;
- унифицирует `vk_title` кодом, а не ответом модели;
- скачивает локальные фото для сорта;
- публикует готовый товар в VK Market.

## Стек

- Python 3.12
- Supabase
- OpenAI API
- VK Market API
- Requests, BeautifulSoup, Pydantic

## Структура

```text
VK_parser_product/
  main.py
  config.py
  prompts.py
  search_client.py
  scraper.py
  parser_utils.py
  llm_client.py
  supabase_client.py
  models.py
  requirements.txt
  .env.example
  README.md
```

## Как создать venv

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

## Как установить зависимости

```bash
pip install -r requirements.txt
```

## Как заполнить .env

Создайте `.env` по примеру:

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
SERPAPI_API_KEY=
VK_TOKEN=
VK_API_VERSION=5.199
```

Минимально нужны:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OPENAI_API_KEY`

Модель можно менять через `OPENAI_MODEL`.

## Как запускать

Обработать все сорта из `config.py`:

```bash
.venv/bin/python main.py run
```

Обработать один сорт:

```bash
.venv/bin/python main.py run --sort "Tidal Silver"
```

Пересобрать карточку из уже сохраненных источников без нового скрапинга:

```bash
.venv/bin/python main.py rebuild --sort "Tidal Silver"
```

Показать сохраненные источники по сорту:

```bash
.venv/bin/python main.py sources --sort "Tidal Silver"
```

Скачать фото сорта в локальную папку проекта:

```bash
.venv/bin/python main.py photos --sort "Tidal Silver"
```

Показать уже скачанные локальные фото по сорту:

```bash
.venv/bin/python main.py photos-local --sort "Tidal Silver"
```

Получить категории VK Market:

```bash
.venv/bin/python main.py vk-categories --count 200 --lang ru
```

Добавить товар в VK Market:

```bash
.venv/bin/python main.py vk-add-product --sort "Tidal Silver" --owner-id <group_owner_id> --category-id 10003
```

Скачать top 20 картинок по поисковому запросу:

```bash
.venv/bin/python main.py photos --sort "Tidal Silver" --mode query --limit 20
```

## Как работает пайплайн

1. `main.py` получает список сортов или один сорт из CLI.
2. `supabase_client.py` получает или создает запись в `vk_products_drafts`.
3. `search_client.py` возвращает candidate URLs.
4. `scraper.py` скачивает HTML и вытягивает очищенный основной текст.
5. `supabase_client.py` сохраняет источники в `vk_product_sources`.
6. `parser_utils.py` агрегирует тексты источников в один блок.
7. `llm_client.py` выбирает нужный промпт через `build_prompt(...)`, отправляет текст в OpenAI и валидирует JSON через Pydantic.
8. `supabase_client.py` обновляет `vk_products_drafts`, а карточка получает `status='ai_ready'`.

Фото сейчас идут отдельным локальным шагом:
- `main.py photos --sort "..."` берет source URLs;
- ищет изображения на страницах;
- сохраняет их в папку `local_photos/<slug_sort_name>/`.

Если нужны именно картинки из поисковой выдачи, а не со страниц-источников:
- используйте `main.py photos --sort "..." --mode query --limit 20`
- для этого нужен `SERPAPI_API_KEY` в `.env`

Для получения категорий VK Market:
- используйте `main.py vk-categories`
- нужен `VK_TOKEN` в `.env`

Для публикации товара в VK Market:
- используйте `main.py vk-add-product`
- нужен `VK_TOKEN` в `.env`
- нужен `owner_id` сообщества, например `-123456789`
- цена берется из `vk_products_drafts.price`, а `--price` можно передать только как ручное переопределение
- у сорта должна быть карточка `ai_ready`
- у сорта должна быть локальная папка с фото

В конце `run` и `rebuild` команда печатает `SUMMARY`:
- сколько сортов обработано;
- сколько источников сохранено;
- сколько карточек обновлено;
- сколько ошибок произошло.

## Где менять список сортов

Список сортов меняется в `config.py`, в `SORTS_TO_PROCESS`.

## Где менять источники

Сейчас проект работает через ручной режим:
- список URL задается в `MANUAL_SOURCE_URLS` в `config.py`;
- функция поиска находится в `search_client.py`.

Если для сорта нет URL, пайплайн пишет понятный лог и пропускает сорт без падения.

Позже можно заменить реализацию поиска внутри `search_client.py` на:
- Google Custom Search
- SerpAPI
- любой другой поисковый движок

Остальной проект переписывать не потребуется, потому что внешний контракт поиска уже выделен отдельно.

## Как устроены промпты

Промпты лежат в `prompts.py`:
- `SYSTEM_PROMPT` для общего стиля;
- `PETUNIA_PROMPT_TEMPLATE` для петуний;
- `TOMATO_PROMPT_TEMPLATE` для томатов;
- `build_prompt(sort_name, raw_text, product_type)` выбирает нужный шаблон.

`llm_client.py` реально использует эти промпты в запросе к OpenAI:
- system prompt передается как `SYSTEM_PROMPT`;
- user prompt собирается через `build_prompt(...)`.

Финальная сборка `vk_title` теперь делается кодом в `main.py`, в функции `build_vk_title(...)`:
- для `product_type='petunia'`: `Рассада петунии {name_ru} ({name_en})`
- если `name_en` нет: `Рассада петунии {name_ru}`
- для `product_type='tomato'`: `Рассада томата {name_ru}`

LLM больше не является источником истины для итогового `vk_title`: он возвращает `name_ru` и `name_en`, а заголовок собирается уже в пайплайне.

Важно: адреса, доставка, самовывоз и акции не должны генерироваться внутри описания сорта. Для этого используется отдельный `sales_tail_template`.

## Smoke-test

Быстрый ручной прогон:

```bash
source .venv/bin/activate
python main.py run --sort "Tidal Silver"
```

Что должно произойти:
- в `vk_products_drafts` должна появиться или обновиться запись по `sort_name="Tidal Silver"`;
- в `vk_product_sources` должны появиться источники для этого сорта;
- в `vk_products_drafts` должны обновиться `vk_title`, `vk_full_description`, `ai_description_structured`, `ai_prompt_version`, `status='ai_ready'`.

Если нужно пересобрать описание без нового скачивания источников:

```bash
python main.py rebuild --sort "Tidal Silver"
```

После `rebuild` проверьте в `vk_products_drafts` поля:
- `vk_title`
- `ai_description_structured`
- `ai_prompt_version='v2'`

Если нужно только посмотреть источники:

```bash
python main.py sources --sort "Tidal Silver"
```

Если нужно скачать фото локально:

```bash
python main.py photos --sort "Tidal Silver"
```

Если нужно просто проверить локальную папку и список файлов:

```bash
python main.py photos-local --sort "Tidal Silver"
```

Команда также показывает абсолютный путь папки, который можно использовать как `local_photos_folder`.

Если нужно получить список категорий VK Market:

```bash
python main.py vk-categories --count 200 --lang ru
```

Если нужно добавить товар в VK Market:

```bash
python main.py vk-add-product --sort "Tidal Silver" --owner-id <group_owner_id> --category-id 10003
```

Если нужен именно поиск картинок по запросу и top 20:

```bash
python main.py photos --sort "Tidal Silver" --mode query --limit 20
```

После этого фото появятся в папке `local_photos`, отдельно для каждого сорта.
