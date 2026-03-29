SORTS_TO_PROCESS = [
    "Tidal Silver",
]

SORT_SOURCE_ALIASES = {
    "Tidal Silver": [
        "Tidal Wave Silver",
        "Тайдал Сильвер",
        "Тайдал Вейв Сильвер",
    ],
    "Опера Блю": [
        "Opera Blue",
        "Opera Supreme Blue",
        "Опера Суприм Блю",
    ],
}

SORT_IMAGE_QUERY_ALIASES = {
    "Tidal Silver": [
        "Тайдал Сильвер петуния",
        "Тайдал Вейв Сильвер петуния",
        "Tidal Wave Silver petunia",
    ],
    "Опера Блю": [
        "Опера Блю петуния",
        "Опера Суприм Блю петуния",
        "Opera Supreme Blue petunia",
    ],
}

SEARCH_RESULTS_LIMIT = 5
REQUEST_TIMEOUT = 20
MAX_PHOTOS_PER_SORT = 12
MAX_PHOTOS_PER_SOURCE = 5
IMAGE_SEARCH_TOP_N = 20
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

EXCLUDED_DOMAINS = [
    "vk.com",
    "youtube.com",
    "youtu.be",
    "t.me",
    "instagram.com",
    "facebook.com",
]

PREFERRED_DOMAINS = [
    "panamseed.com",
    "syngentaflowers.com",
    "ballseed.com",
    "provenwinners.com",
    "floranova.com",
]

MAX_SOURCE_TEXT_CHARS = 6000
MAX_AGGREGATED_TEXT_CHARS = 18000
LOCAL_PHOTOS_ROOT = "local_photos"

DEFAULT_PRODUCT_TYPE = "petunia"

SALES_TAIL_TEMPLATES = {
    "petunia": (
        "В сообществе весь каталог ампельных петуний на этот сезон. "
        "Пишите, какие у вас кашпо, ящики или вазоны — подберу сорт под ваши цели. "
        "Петунии все очень разные, и важно подобрать им правильный объем."
    ),
    "tomato": (
        "Есть и другие сорта томатов. "
        "Если нужно, подберу под теплицу или открытый грунт. Пишите в сообщения."
    ),
}

MANUAL_SOURCE_URLS = {
    "Tidal Silver": [
        "https://www.panamseed.com/Products/048601894005061/spreading-petunia-tidal-wave-silver/",
        "https://www.wavegardening.com/en-us/Flowers/PlantInformation?phid=048601894005061",
        "https://www.botanichka.ru/article/5-samyh-moshhnyh-ampelnyh-petunij-kotorye-mozhno-vyrastit-iz-semyan/",
        "https://www.botanichka.ru/article/neotrazimaya-sortoseriya-petunij-tajdal-vejv-osobennosti-sorta-i-uhoda-za-czvetkom/",
        "https://www.vseprofsemena.ru/product_info.php?products_id=183",
    ],
    "Опера Блю": [
        "https://www.rhs.org.uk/plants/265703/petunia-multiflora-opera-supreme-blue/details",
        "https://ogorodum.ru/petunija-opera.html",
        "https://ilimas.ru/petunia-opera.html",
        "https://petunias.ru/categories/opera-supreme",
        "https://www.thaiseed.co.th/en/product/petunia-opera-supreme-blue/",
    ],
}
