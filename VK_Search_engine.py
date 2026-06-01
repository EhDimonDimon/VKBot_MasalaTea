
import os                           # Для работы с операционной системой, с файлами и директориями
import requests                     # Для отправки HTTP-запросов, для работы с веб-страницами и API
from dotenv import load_dotenv      # Загружаем переменные окружения
import logging                      # Для логирования ошибок в файл


# Загружаем переменные из .env
load_dotenv()

# Используем Google Custom Search API для поиска и получения ссылок:

def search_recipes(query, site):
    api_key = os.getenv("API_KEY")                # Ключ доступа к Google Custom Search API
    cx = os.getenv("CX")                     # CX (Search Engine ID) – ID поисковой системы
    # Добавляем фильтр по сайту в поисковый запрос (intitle для поиска только в заголовках)
    url = f"https://www.googleapis.com/customsearch/v1?q=intitle:{query}+site:{site}&key={api_key}&cx={cx}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()                         # Проверяем, нет ли ошибки HTTP
        data = response.json()                              # Конвертируем JSON-строку в объект Python (dict или list)
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка запроса к Google API: {e}")
        return ["⚠ Ошибка при поиске рецептов. Попробуйте позже."]

    # Обрабатываем результаты поиска
    recipes = []
    for item in data.get('items', []):
        title = item.get('title')
        link = item.get('link')
        if title and link: # Добавляем заголовок и ссылку, только если оба значения существуют. Иные варианты пропускаем
            recipes.append(f"🔸 {title} - {link}")

    return recipes if recipes else ["Рецепты не найдены!"]


