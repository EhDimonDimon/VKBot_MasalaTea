
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from dotenv import load_dotenv
import logging
import time
import os
from VK_Database import *
from VK_Search_engine import *


# Загружаем переменные из .env
load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Инициализация VK бота
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# Словарь для хранения данных пользователей
user_data = {}
user_state = {}

# Словарь для хранения ID последнего сообщения (для редактирования)
user_last_message_id = {}

# Пагинация для ингредиентов
user_ingredient_page = {}
INGREDIENTS_PER_PAGE = 8

# Пагинация для блюд в категории
user_current_category = {}
user_category_page = {}
DISHES_PER_PAGE = 6

# Пагинация для найденных блюд (по ингредиентам)
user_possible_dishes_page = {}
POSSIBLE_DISHES_PER_PAGE = 6

# Ингредиенты из Database.py
ingredients_list = ingredients
menu_dict = menu
categories = menu_categories


def init_user_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "selected_ingredients": set(),
            "started": False,
            "current_mode": None,
            "possible_dishes": [],
            "last_category": None,
            "last_dish_list": None
        }
    if user_id not in user_state:
        user_state[user_id] = None


def send_message(user_id, message, keyboard=None):
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": 0
    }
    if keyboard:
        params["keyboard"] = keyboard.get_keyboard()
    response = vk.messages.send(**params)
    if isinstance(response, int):
        user_last_message_id[user_id] = response
    return response


def edit_message(user_id, message, keyboard=None):
    """Редактирует последнее сообщение пользователя"""
    message_id = user_last_message_id.get(user_id)
    if not message_id:
        return send_message(user_id, message, keyboard)

    params = {
        "peer_id": user_id,
        "message_id": message_id,
        "message": message,
        "random_id": 0
    }
    if keyboard:
        params["keyboard"] = keyboard.get_keyboard()
    try:
        vk.messages.edit(**params)
    except Exception:
        return send_message(user_id, message, keyboard)
    return message_id


def get_selected_text(user_id):
    """Возвращает текст с выбранными ингредиентами"""
    selected = user_data[user_id]["selected_ingredients"]
    if selected:
        return f"📋 Выбрано:\n{', '.join(selected)}"
    return "📋 Пока ничего не выбрано"


# ==================== КЛАВИАТУРЫ ====================

def inline_start():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🚀 Start", color=VkKeyboardColor.POSITIVE)
    return keyboard


def inline_menu():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Меню бота", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Поиск рецепта", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Ингредиенты", color=VkKeyboardColor.PRIMARY)
    return keyboard


def inline_categories():
    keyboard = VkKeyboard(one_time=False)
    categories_list = list(categories.keys())
    for i, category in enumerate(categories_list):
        keyboard.add_button(category, color=VkKeyboardColor.PRIMARY)
        if (i + 1) % 3 == 0 and i + 1 < len(categories_list):
            keyboard.add_line()
    keyboard.add_line()
    keyboard.add_button("🔙 Начать заново", color=VkKeyboardColor.PRIMARY)
    return keyboard


def inline_dishes_by_category(user_id, category):
    keyboard = VkKeyboard(one_time=False)

    dishes = categories.get(category, [])
    current_page = user_category_page.get(user_id, {}).get(category, 0)

    start_idx = current_page * DISHES_PER_PAGE
    end_idx = min(start_idx + DISHES_PER_PAGE, len(dishes))

    for i, dish in enumerate(dishes[start_idx:end_idx]):
        keyboard.add_button(dish, color=VkKeyboardColor.PRIMARY)
        if (i + 1) % 2 == 0 and i + 1 < len(dishes[start_idx:end_idx]):
            keyboard.add_line()

    if len(dishes) > DISHES_PER_PAGE:
        keyboard.add_line()
        if current_page > 0:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
        if current_page < (len(dishes) + DISHES_PER_PAGE - 1) // DISHES_PER_PAGE - 1:
            keyboard.add_button("Вперед ➡️", color=VkKeyboardColor.PRIMARY)

    keyboard.add_line()
    keyboard.add_button("🔙 К категориям", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🔙 Начать заново", color=VkKeyboardColor.PRIMARY)

    return keyboard


def inline_ingredients(user_id):
    keyboard = VkKeyboard(one_time=False)

    current_page = user_ingredient_page.get(user_id, 0)
    total_pages = (len(ingredients_list) + INGREDIENTS_PER_PAGE - 1) // INGREDIENTS_PER_PAGE
    start_idx = current_page * INGREDIENTS_PER_PAGE
    end_idx = min(start_idx + INGREDIENTS_PER_PAGE, len(ingredients_list))

    row_count = 0
    for i, ingredient in enumerate(ingredients_list[start_idx:end_idx]):
        if ingredient in user_data[user_id]["selected_ingredients"]:
            keyboard.add_button(f"✅ {ingredient}", color=VkKeyboardColor.PRIMARY)
        else:
            keyboard.add_button(ingredient, color=VkKeyboardColor.PRIMARY)

        row_count += 1
        if row_count % 2 == 0 and i + 1 < len(ingredients_list[start_idx:end_idx]):
            keyboard.add_line()

    keyboard.add_line()

    if current_page > 0:
        keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
    if current_page < total_pages - 1:
        keyboard.add_button("Вперед ➡️", color=VkKeyboardColor.PRIMARY)

    keyboard.add_line()
    keyboard.add_button("📋 Показать список", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("✅ Готово", color=VkKeyboardColor.PRIMARY)

    return keyboard


def inline_possible_dishes(user_id):
    keyboard = VkKeyboard(one_time=False)

    possible_dishes = user_data[user_id].get("possible_dishes", [])
    if not possible_dishes:
        keyboard.add_button("😕 Нет подходящих блюд", color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button("🔙 Начать заново", color=VkKeyboardColor.PRIMARY)
        return keyboard

    current_page = user_possible_dishes_page.get(user_id, 0)

    start_idx = current_page * POSSIBLE_DISHES_PER_PAGE
    end_idx = min(start_idx + POSSIBLE_DISHES_PER_PAGE, len(possible_dishes))

    count = 0
    for i, dish in enumerate(possible_dishes[start_idx:end_idx]):
        keyboard.add_button(dish, color=VkKeyboardColor.PRIMARY)
        count += 1
        if count % 2 == 0 and i + 1 < len(possible_dishes[start_idx:end_idx]):
            keyboard.add_line()

    if len(possible_dishes) > POSSIBLE_DISHES_PER_PAGE:
        keyboard.add_line()
        if current_page > 0:
            keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY)
        if current_page < (len(possible_dishes) + POSSIBLE_DISHES_PER_PAGE - 1) // POSSIBLE_DISHES_PER_PAGE - 1:
            keyboard.add_button("Вперед ➡️", color=VkKeyboardColor.PRIMARY)

    keyboard.add_line()
    keyboard.add_button("🔙 К ингредиентам", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🔙 Начать заново", color=VkKeyboardColor.PRIMARY)

    return keyboard


def inline_recipe_actions(user_id):
    """Клавиатура для показа рецепта (с возвратом к списку блюд)"""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🔙 К списку блюд", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🔙 Начать заново", color=VkKeyboardColor.PRIMARY)
    return keyboard


def inline_site():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("eda.ru", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("1000.menu", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("iamcook.ru", color=VkKeyboardColor.PRIMARY)
    return keyboard


def inline_back_to_menu():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🔙 Начать заново", color=VkKeyboardColor.PRIMARY)
    return keyboard


# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

def handle_description(user_id):
    text = ("Этот бот:\n"
            "- предложит рецепты блюд из своего меню, которое периодически пополняется;\n"
            "- поможет найти ссылку на рецепт приготовления желаемого блюда;\n"
            "- подберёт рецепты блюд на основе ингредиентов, которые есть у тебя дома;\n\n"
            "Взаимодействие с ботом очень простое: читай, выбирай и жмакай по кнопкам;\n\n"
            "Команды, которые можно вводить в сообщениях:\n"
            "- 0 - перебрасывает в описание бота;\n"
            "- 1 - перебрасывает в меню бота;\n"
            "- 2 - перебрасывает в поиск рецептов;\n"
            "- 3 - перебрасывает в ингредиенты;\n"
            "- любая буква алфавита - перебрасывает в самое начало работы с ботом;\n"
            "- название блюда из меню бота - если ты знаешь точное название блюда из меню бота, то можешь его ввести с заглавной буквы в сообщении, и бот тебе сразу предоставит его рецепт.")
    send_message(user_id, text)


def handle_start(user_id):
    init_user_data(user_id)
    user_data[user_id]["current_mode"] = None
    text = ("Жмакни по нужной кнопке внизу экрана:\n\n"
            "🔹 Меню бота - выбор рецепта из меню бота\n\n"
            "🔹 Поиск рецепта - поиск рецептов по названию блюда\n\n"
            "🔹 Ингредиенты - выбор ингредиентов, а бот подберет все рецепты блюд из своего меню\n\n"
            "Чтобы перейти в описание бота, отправь сообщение: 0")
    send_message(user_id, text, keyboard=inline_menu())


def handle_one(user_id):
    user_data[user_id]["current_mode"] = "menu"
    send_message(user_id, "🔹 Выбери категорию:", keyboard=inline_categories())


def handle_category_selection(user_id, category):
    dishes = categories.get(category, [])
    if not dishes:
        send_message(user_id, f"❌ В категории '{category}' пока нет блюд", keyboard=inline_categories())
        return

    user_data[user_id]["current_mode"] = "category"
    user_current_category[user_id] = category
    user_data[user_id]["last_category"] = category

    if user_id not in user_category_page:
        user_category_page[user_id] = {}
    if category not in user_category_page[user_id]:
        user_category_page[user_id][category] = 0

    send_message(user_id, f"🔹 {category}:", keyboard=inline_dishes_by_category(user_id, category))


def handle_category_pagination(user_id, direction):
    category = user_current_category.get(user_id)
    if not category:
        return

    dishes = categories.get(category, [])
    if not dishes:
        return

    if user_id not in user_category_page:
        user_category_page[user_id] = {}
    if category not in user_category_page[user_id]:
        user_category_page[user_id][category] = 0

    current = user_category_page[user_id][category]
    total_pages = (len(dishes) + DISHES_PER_PAGE - 1) // DISHES_PER_PAGE

    if direction == "next" and current < total_pages - 1:
        user_category_page[user_id][category] = current + 1
    elif direction == "prev" and current > 0:
        user_category_page[user_id][category] = current - 1

    edit_message(user_id, f"🔹 {category}:", keyboard=inline_dishes_by_category(user_id, category))


def handle_two(user_id):
    init_user_data(user_id)
    user_data[user_id]["current_mode"] = "search"
    send_message(user_id, "🔹 Выбери сайт внизу экрана:", keyboard=inline_site())


def handle_three(user_id):
    init_user_data(user_id)
    user_data[user_id]["current_mode"] = "ingredients"
    user_data[user_id]["selected_ingredients"].clear()
    user_ingredient_page[user_id] = 0
    send_message(user_id, get_selected_text(user_id), keyboard=inline_ingredients(user_id))


def handle_dish_selection(user_id, dish_name):
    if dish_name in menu_dict:
        dish = menu_dict[dish_name]
        ingredients_for_dish = "\n🔸".join(dish["ингредиенты"])
        recipe = "\n🔸".join(dish["рецепт"])
        message = (f"🍽 {dish_name} 🍽\n\n"
                   f"📝 ИНГРЕДИЕНТЫ:\n🔸{ingredients_for_dish}\n\n"
                   f"👨‍🍳 СПОСОБ ПРИГОТОВЛЕНИЯ:\n🔸{recipe}")

        # Сохраняем текущий список блюд для возврата
        current_mode = user_data[user_id]["current_mode"]
        if current_mode == "possible_dishes":
            user_data[user_id]["last_dish_list"] = "possible"
        elif current_mode == "category":
            user_data[user_id]["last_dish_list"] = user_current_category.get(user_id)

        send_message(user_id, message, keyboard=inline_recipe_actions(user_id))


def handle_back_to_dishes(user_id):
    """Возвращает пользователя к списку блюд"""
    last_dish_list = user_data[user_id].get("last_dish_list")

    # Если были в списке возможных блюд (по ингредиентам)
    if last_dish_list == "possible":
        user_data[user_id]["current_mode"] = "possible_dishes"
        send_message(user_id, "🔹 Ты можешь приготовить:", keyboard=inline_possible_dishes(user_id))
    # Если были в категории меню
    elif last_dish_list and last_dish_list in categories:
        user_data[user_id]["current_mode"] = "category"
        user_current_category[user_id] = last_dish_list
        send_message(user_id, f"🔹 {last_dish_list}:", keyboard=inline_dishes_by_category(user_id, last_dish_list))
    else:
        # Если не можем определить - возвращаем в главное меню
        handle_start(user_id)


def handle_ingredient_selection(user_id, ingredient):
    if ingredient.startswith("✅ "):
        ingredient = ingredient[2:]

    if ingredient in user_data[user_id]["selected_ingredients"]:
        user_data[user_id]["selected_ingredients"].remove(ingredient)
    else:
        user_data[user_id]["selected_ingredients"].add(ingredient)

    edit_message(user_id, get_selected_text(user_id), keyboard=inline_ingredients(user_id))


def handle_ingredients_done(user_id):
    selected = user_data[user_id]["selected_ingredients"]
    if not selected:
        send_message(user_id, "❌ Ничего не выбрано!", keyboard=inline_ingredients(user_id))
        return

    if user_id in user_ingredient_page:
        del user_ingredient_page[user_id]

    selected_ingredients(user_id, selected)


def handle_back_to_ingredients(user_id):
    """Возвращает пользователя к редактированию списка ингредиентов"""
    user_data[user_id]["current_mode"] = "ingredients"
    user_ingredient_page[user_id] = 0
    send_message(user_id, get_selected_text(user_id), keyboard=inline_ingredients(user_id))


def selected_ingredients(user_id, selected):
    possible_dishes = []
    for name_dish, preparation in menu_dict.items():
        dish_ingredients = set(preparation["ингредиенты"])
        if dish_ingredients.issubset(selected):
            possible_dishes.append(name_dish)

    selected_str = ", ".join(selected)
    send_message(user_id, f"📋 Список выбранных продуктов:\n{selected_str}")

    # Специальные комбинации (шутки)
    if selected_str == 'вода':
        send_message(user_id, "Пей вода, ешь вода - ср..ть не будешь никогда!", keyboard=inline_back_to_menu())
        return
    elif selected_str == 'хлеб':
        send_message(user_id, "Хлеб - всему голова!", keyboard=inline_back_to_menu())
        return
    elif selected_str == 'соль':
        send_message(user_id, "Однократное употребление 250 грамм соли, приводит к летальному исходу!\n"
                              "P.S. Пищевой соли, если что.", keyboard=inline_back_to_menu())
        return
    elif set(selected) == {'соль', 'хлеб'}:
        send_message(user_id, "Хлеб с солью доедаешь? Тяжёлые у тебя времена. Могу только посочувствовать😢", keyboard=inline_back_to_menu())
        return
    elif set(selected) == {'вода', 'хлеб'}:
        send_message(user_id, "Хлеб с водой - это уже каша! Приятного аппетита!", keyboard=inline_back_to_menu())
        return
    elif set(selected) == {'вода', 'соль'}:
        send_message(user_id, "Соль в воде – это как шутка: если мало – не смешно, если много – неприятно.", keyboard=inline_back_to_menu())
        return
    elif set(selected) == {'соль', 'хлеб', 'вода'}:
        send_message(user_id, "А если ещё и свечи найдёшь, то можно устроить незабываемый ужин при свечах. Think about it!😄", keyboard=inline_back_to_menu())
        return

    # Сохраняем найденные блюда и показываем первую страницу
    user_data[user_id]["possible_dishes"] = possible_dishes
    user_possible_dishes_page[user_id] = 0
    user_data[user_id]["current_mode"] = "possible_dishes"

    if possible_dishes:
        send_message(user_id, "🔹 Ты можешь приготовить:", keyboard=inline_possible_dishes(user_id))
    else:
        send_message(user_id, "😕 Ничего не могу предложить. Просто съешь выбранные продукты!",
                     keyboard=inline_back_to_menu())


def handle_possible_dishes_pagination(user_id, direction):
    current_page = user_possible_dishes_page.get(user_id, 0)
    possible_dishes = user_data[user_id].get("possible_dishes", [])
    total_pages = (
                              len(possible_dishes) + POSSIBLE_DISHES_PER_PAGE - 1) // POSSIBLE_DISHES_PER_PAGE if possible_dishes else 1

    if direction == "next" and current_page < total_pages - 1:
        user_possible_dishes_page[user_id] = current_page + 1
    elif direction == "prev" and current_page > 0:
        user_possible_dishes_page[user_id] = current_page - 1

    edit_message(user_id, "🔹 Ты можешь приготовить:", keyboard=inline_possible_dishes(user_id))


# ==================== ПОИСК РЕЦЕПТОВ НА САЙТАХ ====================

def handle_site_selection(user_id, site_name):
    site_map = {
        "eda.ru": "eda.ru",
        "1000.menu": "1000.menu",
        "iamcook.ru": "iamcook.ru"
    }
    site = site_map.get(site_name, site_name)
    send_message(user_id, f"Отлично! Буду искать на {site}\nТеперь напиши название блюда:")
    user_state[user_id] = f"waiting_for_recipe_name:{site}"


def search_recipe_on_site(user_id, text, site):
    input_text = text.strip().lower()

    if input_text in ["/start", "start", "меню"]:
        handle_start(user_id)
        return
    elif input_text in ["/one", "1"]:
        handle_one(user_id)
        return
    elif input_text in ["/two", "2"]:
        handle_two(user_id)
        return
    elif input_text in ["/three", "3"]:
        handle_three(user_id)
        return

    send_message(user_id, "🔎 Ищу рецепты ...")
    recipes = search_recipes(input_text, site)

    if recipes == ["Рецепты не найдены!"]:
        send_message(user_id, "❌ Рецепты не найдены!\nПроверь правильность написания или введи другое название:")
        user_state[user_id] = f"waiting_for_recipe_name:{site}"
    else:
        result_text = "\n\n".join(recipes)
        send_message(user_id, f"🔍 Результаты поиска:\n\n{result_text}", keyboard=inline_back_to_menu())
        user_state[user_id] = None


# ==================== ОСНОВНОЙ ЦИКЛ ====================

def handle_text_message(user_id, text):
    text_lower = text.lower().strip()

    if len(text_lower) == 1 and text_lower.isalpha():
        handle_start(user_id)
        return

    if text_lower in ["start", "меню", "начать", "s", "м"]:
        handle_start(user_id)
        return
    elif text_lower == "0":
        handle_description(user_id)
        return
    elif text_lower in ["/one", "1"]:
        handle_one(user_id)
        return
    elif text_lower in ["/two", "2"]:
        handle_two(user_id)
        return
    elif text_lower in ["/three", "3"]:
        handle_three(user_id)
        return
    elif text_lower in ["начать заново", "🔙 начать заново"]:
        user_current_category.pop(user_id, None)
        user_data[user_id].pop("current_mode", None)
        handle_start(user_id)
        return
    elif text_lower in ["к категориям", "🔙 к категориям"]:
        user_data[user_id]["current_mode"] = "menu"
        handle_one(user_id)
        return
    elif text_lower in ["к ингредиентам", "🔙 к ингредиентам"]:
        handle_back_to_ingredients(user_id)
        return
    elif text_lower in ["к списку блюд", "🔙 к списку блюд"]:
        handle_back_to_dishes(user_id)
        return

    current_state = user_state.get(user_id)
    if current_state and current_state.startswith("waiting_for_recipe_name:"):
        site = current_state.split(":")[1]
        search_recipe_on_site(user_id, text, site)
    else:
        send_message(user_id, f"❓ Что за '{text}'?\nНажми /start для начала.", keyboard=inline_back_to_menu())


def handle_button_press(user_id, button_text):
    init_user_data(user_id)

    if button_text == "🚀 Start":
        handle_start(user_id)
        return True

    if button_text == "Меню бота":
        handle_one(user_id)
        return True
    elif button_text == "Поиск рецепта":
        handle_two(user_id)
        return True
    elif button_text == "Ингредиенты":
        handle_three(user_id)
        return True

    # Категории
    if button_text in categories:
        handle_category_selection(user_id, button_text)
        return True
    elif button_text == "🔙 К категориям":
        user_current_category.pop(user_id, None)
        user_data[user_id]["current_mode"] = "menu"
        handle_one(user_id)
        return True
    elif button_text == "🔙 К ингредиентам":
        handle_back_to_ingredients(user_id)
        return True
    elif button_text == "🔙 К списку блюд":
        handle_back_to_dishes(user_id)
        return True

    # Пагинация
    if button_text in ["Вперед ➡️", "⬅️ Назад"]:
        current_mode = user_data[user_id].get("current_mode", "")

        # Если в режиме найденных блюд
        if current_mode == "possible_dishes":
            if button_text == "Вперед ➡️":
                handle_possible_dishes_pagination(user_id, "next")
            else:
                handle_possible_dishes_pagination(user_id, "prev")
            return True

        # Если в режиме ингредиентов
        elif current_mode == "ingredients":
            current_page = user_ingredient_page.get(user_id, 0)
            total_pages = (len(ingredients_list) + INGREDIENTS_PER_PAGE - 1) // INGREDIENTS_PER_PAGE

            if button_text == "Вперед ➡️":
                if current_page < total_pages - 1:
                    user_ingredient_page[user_id] = current_page + 1
                    edit_message(user_id, get_selected_text(user_id), keyboard=inline_ingredients(user_id))
            else:
                if current_page > 0:
                    user_ingredient_page[user_id] = current_page - 1
                    edit_message(user_id, get_selected_text(user_id), keyboard=inline_ingredients(user_id))
            return True

        # Если в режиме категорий
        elif current_mode == "category":
            if button_text == "Вперед ➡️":
                handle_category_pagination(user_id, "next")
            else:
                handle_category_pagination(user_id, "prev")
            return True

    # Выбор сайта
    if button_text in ["eda.ru", "1000.menu", "iamcook.ru"]:
        user_data[user_id]["current_mode"] = "search"
        handle_site_selection(user_id, button_text)
        return True

    if button_text == "📋 Показать список":
        selected = user_data[user_id]["selected_ingredients"]
        if selected:
            selected_str = ", ".join(selected)
            send_message(user_id, f"📋 Выбрано:\n{selected_str}")
        else:
            send_message(user_id, "📋 Сейчас список пуст. Выбери ингредиенты на страницах ниже!")
        return True

    if button_text == "✅ Готово":
        handle_ingredients_done(user_id)
        return True

    if button_text == "🔙 Начать заново":
        user_current_category.pop(user_id, None)
        user_data[user_id].pop("current_mode", None)
        handle_start(user_id)
        return True

    # Выбор блюда из меню или из найденных
    if button_text in menu_dict:
        handle_dish_selection(user_id, button_text)
        return True

    if button_text in user_data[user_id].get("possible_dishes", []):
        handle_dish_selection(user_id, button_text)
        return True

    if button_text in ingredients_list or button_text.startswith("✅ "):
        handle_ingredient_selection(user_id, button_text)
        return True

    return False


def setup_logging():
    logging.basicConfig(
        level=logging.ERROR,
        filename="bot_errors.log",
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s"
    )


def main():
    setup_logging()
    print("🤖 VK Бот запущен и готов к работе!")
    print("Ожидание сообщений...")

    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    user_id = event.user_id
                    init_user_data(user_id)

                    if event.text:
                        message_text = event.text.strip()

                        if not user_data[user_id].get("started"):
                            user_data[user_id]["started"] = True
                            send_message(user_id, "🍳 Привет!\nНажми кнопку, чтобы начать:", keyboard=inline_start())
                        elif not handle_button_press(user_id, message_text):
                            handle_text_message(user_id, message_text)

        except vk_api.exceptions.ApiError as e:
            logging.error(f"VK ApiError: {e}")
            print(f"VK ApiError: {e}")
            time.sleep(5)
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            print(f"Ошибка: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()





