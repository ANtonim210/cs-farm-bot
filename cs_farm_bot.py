import json
import math
import random
import sqlite3
import time
import telebot
from telebot import types
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Заглушка для веб-порта Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Запускаем сервер в фоновом потоке
threading.Thread(target=run_web_server, daemon=True).start()

# ================= НАСТРОЙКИ =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7917555581  # Вставь свой Telegram ID (число)
# =============================================

bot = telebot.TeleBot(TOKEN)
ITEMS_PER_PAGE = 5

# 75+ скинов и ножей
INITIAL_SKINS = [
    # Ширпотреб (⚪)
    ("P250 | Sand Dune", 100, "⚪ Ширпотреб"),
    ("AK-47 | Safari Mesh", 150, "⚪ Ширпотреб"),
    ("PP-Bizon | Sand Dashed", 120, "⚪ Ширпотреб"),
    ("Nova | Sand Dune", 110, "⚪ Ширпотреб"),
    ("P90 | Sand Spray", 130, "⚪ Ширпотреб"),
    ("SSG 08 | Blue Spruce", 140, "⚪ Ширпотреб"),
    ("Galil AR | Sage Spray", 160, "⚪ Ширпотреб"),
    ("FAMAS | Colony", 135, "⚪ Ширпотреб"),
    ("MAC-10 | Tornado", 125, "⚪ Ширпотреб"),
    ("AUG | Contractor", 145, "⚪ Ширпотреб"),
    # Армейское (🟦)
    ("Glock-18 | High Beam", 250, "🟦 Армейское"),
    ("AWP | Pit Viper", 350, "🟦 Армейское"),
    ("M4A4 | Magnesium", 450, "🟦 Армейское"),
    ("USP-S | Forest Leaves", 220, "🟦 Армейское"),
    ("Desert Eagle | Oxide Blaze", 300, "🟦 Армейское"),
    ("MP7 | Urban Hazard", 280, "🟦 Армейское"),
    ("Tec-9 | Ice Cap", 290, "🟦 Армейское"),
    ("P90 | Grim", 320, "🟦 Армейское"),
    ("SG 553 | Cyberforce", 380, "🟦 Армейское"),
    ("MAC-10 | Grassland", 270, "🟦 Армейское"),
    ("MP5-SD | NecroJr", 310, "🟦 Армейское"),
    ("P250 | Visions", 400, "🟦 Армейское"),
    # Запрещенное (🟪)
    ("Desert Eagle | Light Rail", 600, "🟪 Запрещенное"),
    ("USP-S | Cyrex", 800, "🟪 Запрещенное"),
    ("AK-47 | Rat Rod", 1000, "🟪 Запрещенное"),
    ("AWP | Atheris", 1200, "🟪 Запрещенное"),
    ("M4A1-S | Nightmare", 1500, "🟪 Запрещенное"),
    ("M4A4 | Desolate Space", 1400, "🟪 Запрещенное"),
    ("AK-47 | Nightwish", 1600, "🟪 Запрещенное"),
    ("Galil AR | Cerberus", 1100, "🟪 Запрещенное"),
    ("FAMAS | Eye of Athena", 1300, "🟪 Запрещенное"),
    ("AUG | Stymphalian", 950, "🟪 Запрещенное"),
    ("P90 | Asiimov", 1700, "🟪 Запрещенное"),
    ("SSG 08 | Blood in the Water", 1850, "🟪 Запрещенное"),
    # Засекреченное (💖)
    ("AK-47 | Redline", 2000, "💖 Засекреченное"),
    ("AWP | Redline", 2500, "💖 Засекреченное"),
    ("Desert Eagle | Code Red", 3000, "💖 Засекреченное"),
    ("M4A4 | Neo-Noir", 3500, "💖 Засекреченное"),
    ("USP-S | Kill Confirmed", 4500, "💖 Засекреченное"),
    ("M4A4 | Emperor", 3200, "💖 Засекреченное"),
    ("AK-47 | Head Shot", 3800, "💖 Засекреченное"),
    ("MP7 | Abyssal Apparition", 2200, "💖 Засекреченное"),
    ("SG 553 | Integrale", 4100, "💖 Засекреченное"),
    ("AUG | Akihabara Accept", 4800, "💖 Засекреченное"),
    ("P250 | Asiimov", 2600, "💖 Засекреченное"),
    ("Glock-18 | Wasteland Rebel", 3300, "💖 Засекреченное"),
    # Тайное (🔴)
    ("AK-47 | The Empress", 6000, "🔴 Тайное"),
    ("M4A1-S | Printstream", 7500, "🔴 Тайное"),
    ("AWP | Asiimov", 9000, "🔴 Тайное"),
    ("AK-47 | Fire Serpent", 15000, "🔴 Тайное"),
    ("AWP | Dragon Lore", 30000, "🔴 Тайное"),
    ("AWP | Lore", 14000, "🔴 Тайное"),
    ("M4A4 | Temukau", 8500, "🔴 Тайное"),
    ("AK-47 | Inheritance", 11000, "🔴 Тайное"),
    ("AWP | Chrome Cannon", 9500, "🔴 Тайное"),
    ("Zeus x27 | Olympus", 5500, "🔴 Тайное"),
    ("M4A1-S | Player Two", 6800, "🔴 Тайное"),
    ("USP-S | Printstream", 8200, "🔴 Тайное"),
    # Ножи и редкие ★ (🟡)
    ("★ Gut Knife | Doppler", 12000, "🟡★ Нож"),
    ("★ Flip Knife | Tiger Tooth", 15000, "🟡★ Нож"),
    ("★ Huntsman Knife | Fade", 18000, "🟡★ Нож"),
    ("★ Shadow Daggers | Crimson Web", 20000, "🟡★ Нож"),
    ("★ Bowie Knife | Marble Fade", 22000, "🟡★ Нож"),
    ("★ Karambit | Autotronic", 28000, "🟡★ Нож"),
    ("★ Butterfly Knife | Slaughter", 35000, "🟡★ Нож"),
    ("★ M9 Bayonet | Gamma Doppler", 40000, "🟡★ Нож"),
    ("★ Karambit | Fade", 50000, "🟡★ Нож"),
    ("★ Butterfly Knife | Doppler", 65000, "🟡★ Нож"),
    ("★ Kukri Knife | Fade", 45000, "🟡★ Нож"),
    ("★ Skeleton Knife | Case Hardened", 42000, "🟡★ Нож"),
    ("★ Talon Knife | Marble Fade", 48000, "🟡★ Нож"),
    ("★ Stiletto Knife | Tiger Tooth", 31000, "🟡★ Нож"),
    ("★ Ursus Knife | Doppler", 25000, "🟡★ Нож"),
    ("★ Navaja Knife | Crimson Web", 11000, "🟡★ Нож"),
    ("★ Paracord Knife | Slaughter", 29000, "🟡★ Нож"),
    ("★ Nomad Knife | Fade", 38000, "🟡★ Нож"),
    ("★ Classic Knife | Fade", 34000, "🟡★ Нож"),
    ("★ Shadow Daggers | Lore", 21000, "🟡★ Нож"),
]

# Конфигурация 5 кейсов с повышенными шансами на нож в дорогих
CASES_CONFIG = {
    'weapon_case': {
        'name': '📦 Weapon Case',
        'price': 500,
        'drops': [
            {'name': 'Пыльник | Safari Mesh', 'chance': 60, 'type': 'common'},
            {'name': 'MP7 | Urban Hazard', 'chance': 25, 'type': 'uncommon'},
            {'name': 'AK-47 | Redline', 'chance': 10, 'type': 'classified'},
            {'name': 'AWP | Asiimov', 'chance': 2.5, 'type': 'covert'},
            {'name': '🔪 Нож | Karambit | Fade', 'chance': 2.5, 'type': 'knife'}
        ]
    },
    'prisma_case': {
        'name': '💎 Prisma Case',
        'price': 1200,
        'drops': [
            {'name': 'MAC-10 | Grassland', 'chance': 55, 'type': 'common'},
            {'name': 'Desert Eagle | Oxide Blaze', 'chance': 25, 'type': 'uncommon'},
            {'name': 'M4A4 | Emperor', 'chance': 12, 'type': 'classified'},
            {'name': 'M4A1-S | Printstream', 'chance': 4, 'type': 'covert'},
            {'name': '🔪 Нож | Butterfly | Doppler', 'chance': 4, 'type': 'knife'}
        ]
    },
    'dreams_case': {
        'name': '🌙 Dreams & Nightmares',
        'price': 2500,
        'drops': [
            {'name': 'MP5-SD | NecroJr', 'chance': 50, 'type': 'common'},
            {'name': 'P250 | Visions', 'chance': 25, 'type': 'uncommon'},
            {'name': 'AK-47 | Nightwish', 'chance': 13, 'type': 'classified'},
            {'name': 'MP7 | Abyssal Apparition', 'chance': 5, 'type': 'covert'},
            {'name': '🔪 Нож | Butterfly | Lore', 'chance': 7, 'type': 'knife'}
        ]
    },
    'gamma_case': {
        'name': '🟢 Gamma Case',
        'price': 5000,
        'drops': [
            {'name': 'P90 | Grim', 'chance': 45, 'type': 'common'},
            {'name': 'Tec-9 | Ice Cap', 'chance': 25, 'type': 'uncommon'},
            {'name': 'M4A4 | Desolate Space', 'chance': 13, 'type': 'classified'},
            {'name': 'AWP | Lore', 'chance': 5, 'type': 'covert'},
            {'name': '🔪 Нож | M9 Bayonet | Gamma Doppler', 'chance': 12, 'type': 'knife'}
        ]
    },
    'revo_case': {
        'name': '🔥 Revolution Case',
        'price': 10000,
        'drops': [
            {'name': 'MAC-10 | Stalker', 'chance': 40, 'type': 'common'},
            {'name': 'SG 553 | Cyberforce', 'chance': 23, 'type': 'uncommon'},
            {'name': 'AK-47 | Head Shot', 'chance': 12, 'type': 'classified'},
            {'name': 'M4A4 | Temukau', 'chance': 5, 'type': 'covert'},
            {'name': '🔪 Нож | Skeleton Knife | Case Hardened', 'chance': 20, 'type': 'knife'}
        ]
    }
}


def get_db():
    return sqlite3.connect("cs_database.db")


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                last_farm REAL DEFAULT 0,
                inventory TEXT DEFAULT '[]'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shop (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price INTEGER,
                rarity TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                reward INTEGER,
                max_activations INTEGER,
                used_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS promo_uses (
                user_id INTEGER,
                code TEXT,
                PRIMARY KEY (user_id, code)
            )
        """)

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shop")
        if cursor.fetchone()[0] == 0:
            for name, price, rarity in INITIAL_SKINS:
                cursor.execute(
                    "INSERT INTO shop (name, price, rarity) VALUES (?, ?, ?)",
                    (name, price, rarity),
                )
            conn.commit()


def check_user_exists(user_id, username):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username or "Игрок"),
            )
            conn.commit()


def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎮 Фармить", "🛒 Магазин")
    markup.row("📦 Кейсы", "🎯 Апгрейдер")
    markup.row("💣 Мины", "⭐ Донат (Звезды)")
    markup.row("🎒 Профиль", "🏆 Топ 10")
    markup.row("🎟 Промокод")
    return markup


def get_shop_markup(page=0):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, name, price, rarity FROM shop")
        items = cursor.fetchall()

    total_pages = math.ceil(len(items) / ITEMS_PER_PAGE) or 1
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_items = items[start_idx:end_idx]

    markup = types.InlineKeyboardMarkup()

    for item_id, name, price, rarity in current_items:
        btn_text = f"Купить {rarity} {name} — {price} 💰"
        markup.add(
            types.InlineKeyboardButton(
                text=btn_text, callback_data=f"buy_{item_id}_{page}"
            )
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(
                "⬅️ Назад", callback_data=f"page_{page - 1}"
            )
        )

    nav_buttons.append(
        types.InlineKeyboardButton(
            f"Стр. {page + 1}/{total_pages}", callback_data="ignore"
        )
    )

    if page < total_pages - 1:
        nav_buttons.append(
            types.InlineKeyboardButton(
                "Вперед ➡️", callback_data=f"page_{page + 1}"
            )
        )

    markup.row(*nav_buttons)
    return markup, total_pages


@bot.message_handler(commands=["start"])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.first_name or "Игрок"
    check_user_exists(user_id, username)

    text = (
        f"Добро пожаловать в CS2 Симулятор, <b>{username}</b>!\n\n"
        f"Используй кнопки ниже для игры:\n"
        f"🎮 <b>Фармить</b> — получай монеты каждый час\n"
        f"🛒 <b>Магазин</b> — покупай редкие скины (75+ штук)\n"
        f"📦 <b>Кейсы</b> — открывай кейсы с повышенным шансом на нож\n"
        f"🎯 <b>Апгрейдер</b> — рискуй скинами ради крутого апгрейда\n"
        f"💣 <b>Мины</b> — мини-игра Сапер со ставками и множителями\n"
        f"⭐ <b>Донат</b> — покупай валюту за Telegram Stars\n"
        f"🎒 <b>Профиль</b> — смотри свою коллекцию и баланс\n"
        f"🏆 <b>Топ 10</b> — рейтинг самых ценных инвентарей\n"
        f"🎟 <b>Промокод</b> — активируй бонусные коды"
    )

    bot.send_message(
        message.chat.id, text, parse_mode="HTML", reply_markup=main_keyboard()
    )


# Гибкий обработчик меню по ключевым словам
@bot.message_handler(
    func=lambda m: m.text
    and any(
        k in m.text for k in ["Фармить", "Магазин", "Кейсы", "Апгрейдер", "Мины", "Донат (Звезды)", "Профиль", "Топ 10", "Промокод"]
    )
)
def menu_handler(message):
    check_user_exists(message.from_user.id, message.from_user.first_name)
    text = message.text

    if "Фармить" in text:
        farm_logic(message)
    elif "Магазин" in text:
        show_shop(message)
    elif "Кейсы" in text:
        show_cases_menu(message)
    elif "Апгрейдер" in text:
        show_upgrader_menu(message)
    elif "Мины" in text:
        show_mines_menu(message)
    elif "Донат" in text:
        donate_menu_message(message)
    elif "Профиль" in text:
        show_profile(message)
    elif "Топ 10" in text:
        show_top(message)
    elif "Промокод" in text:
        prompt_promo(message)


def farm_logic(message):
    user_id = message.from_user.id
    now = time.time()
    cooldown = 3600

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT balance, last_farm FROM users WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()

        balance, last_farm = row[0], row[1]
        passed = now - last_farm

        if passed < cooldown:
            mins_left = int((cooldown - passed) // 60)
            secs_left = int((cooldown - passed) % 60)
            bot.send_message(
                message.chat.id,
                f"⏳ Кулдаун! Жди еще {mins_left} мин. {secs_left} сек.",
            )
            return

        earned = random.randint(200, 500)
        new_balance = balance + earned
        cursor.execute(
            "UPDATE users SET balance = ?, last_farm = ? WHERE user_id = ?",
            (new_balance, now, user_id),
        )
        conn.commit()

    bot.send_message(
        message.chat.id,
        f"✅ Вы сфармили <b>{earned}</b> монет!\n💰 Баланс: <b>{new_balance}</b>",
        parse_mode="HTML",
    )


def show_shop(message):
    markup, _ = get_shop_markup(page=0)
    bot.send_message(
        message.chat.id,
        "🛒 <b>КАТАЛОГ СКИНОВ CS2 (75+ ПОЗИЦИЙ)</b>\nВыбери скин для покупки:",
        parse_mode="HTML",
        reply_markup=markup,
    )


# --- МЕНЮ КЕЙСОВ ---
def show_cases_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for case_key, case_data in CASES_CONFIG.items():
        markup.add(
            types.InlineKeyboardButton(
                f"{case_data['name']} — 💰 {case_data['price']:,} монет", 
                callback_data=f"open_case_{case_key}"
            )
        )
    bot.send_message(
        message.chat.id,
        "📦 <b>Магазин кейсов</b>\nВыбирай кейс и пытайся выбить нож! В дорогих кейсах шанс на нож выше:",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('open_case_'))
def process_case_opening(call):
    user_id = call.from_user.id
    case_key = call.data.replace('open_case_', '')
    if case_key not in CASES_CONFIG:
        return
        
    case = CASES_CONFIG[case_key]
    price = case['price']
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, inventory FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return
        balance, inv_json = row
        
        if balance < price:
            bot.answer_callback_query(call.id, f"❌ Недостаточно монет! Нужно {price:,} 💰", show_alert=True)
            return
            
        roll = random.uniform(0, 100)
        current_sum = 0
        won_item = case['drops'][0]
        
        for item in case['drops']:
            current_sum += item['chance']
            if roll <= current_sum:
                won_item = item
                break
                
        inventory = json.loads(inv_json)
        inventory.append(won_item['name'])
        
        cursor.execute(
            "UPDATE users SET balance = balance - ?, inventory = ? WHERE user_id = ?",
            (price, json.dumps(inventory, ensure_ascii=False), user_id)
        )
        conn.commit()
        new_balance = balance - price
        
    if won_item['type'] == 'knife':
        text = f"🔥🔥 УЛЬТРА-ДРОП! 🔥🔥\nИз кейса {case['name']} выпал редчайший нож:\n🌟 **{won_item['name']}**"
    else:
        text = f"📦 Открыт {case['name']}\nТебе выпало: **{won_item['name']}**\n💰 Баланс: {new_balance:,}"
        
    bot.answer_callback_query(call.id, "Кейс успешно открыт!")
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")


# --- АПГРЕЙДЕР ---
def show_upgrader_menu(message):
    user_id = message.from_user.id
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT inventory FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row or not json.loads(row[0]):
            bot.send_message(message.chat.id, "🎯 <b>Апгрейдер</b>\n\nТвой инвентарь пуст! Сначала купи скин в магазине или выбей из кейса.", parse_mode="HTML")
            return

        cursor.execute("SELECT name, price, rarity FROM shop")
        shop_items = cursor.fetchall()

    inventory = json.loads(row[0])
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Берем последние 5 уникальных предметов из инвентаря для апгрейда
    unique_inv = list(dict.fromkeys(inventory))[-5:]
    for item_name in unique_inv:
        markup.add(types.InlineKeyboardButton(f"🎯 Апгрейдить: {item_name}", callback_data=f"upg_sel_{item_name}"))

    bot.send_message(
        message.chat.id,
        "🎯 <b>Апгрейдер скинов</b>\nВыбери предмет из своего инвентаря, который хочешь проапгрейдить до более дорогого:",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('upg_sel_'))
def upg_select_item(call):
    item_name = call.data.replace('upg_sel_', '')
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, price, rarity FROM shop")
        shop_items = cursor.fetchall()
    
    price_map = {f"{rarity} {name}": price for name, price, rarity in shop_items}
    item_price = price_map.get(item_name, 500)

    # Находим скины дороже выбранного
    better_items = [(name, price, rarity) for name, price, rarity in shop_items if price > item_price]
    if not better_items:
        bot.answer_callback_query(call.id, "❌ У тебя топовый скин, выше некуда!", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    # Выберем до 5 возможных целей для апгрейда
    sample_targets = random.sample(better_items, min(5, len(better_items)))
    for name, price, rarity in sample_targets:
        target_full = f"{rarity} {name}"
        chance = max(5, min(90, int((item_price / price) * 85)))
        markup.add(types.InlineKeyboardButton(f"{target_full} ({price} 💰) — Шанс: {chance}%", callback_data=f"upg_do_{item_name}_{price}"))

    bot.edit_message_text(
        f"🎯 Выбран скин: <b>{item_name}</b> (≈ {item_price} 💰)\nВыбери цель для апгрейда:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('upg_do_'))
def upg_execute(call):
    parts = call.data.replace('upg_do_', '').rsplit('_', 1)
    if len(parts) != 2:
        return
    item_name, target_price_str = parts
    target_price = int(target_price_str)
    user_id = call.from_user.id

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT inventory FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return
        inventory = json.loads(row[0])
        if item_name not in inventory:
            bot.answer_callback_query(call.id, "❌ У тебя больше нет этого скина!", show_alert=True)
            return

        cursor.execute("SELECT name, price, rarity FROM shop")
        shop_items = cursor.fetchall()
        price_map = {f"{rarity} {name}": price for name, price, rarity in shop_items}
        item_price = price_map.get(item_name, 500)

        chance = max(5, min(90, int((item_price / target_price) * 85)))
        
        # Удаляем скин из инвентаря
        inventory.remove(item_name)
        
        roll = random.randint(1, 100)
        success = roll <= chance

        if success:
            # Ищем скин с целевой ценой
            matching = [f"{rarity} {name}" for name, price, rarity in shop_items if price == target_price]
            won_skin = random.choice(matching) if matching else "★ Butterfly Knife | Doppler"
            inventory.append(won_skin)
            result_text = f"🎉 <b>УСПЕХ! Апгрейд удался!</b>\nТы получил крутой скин: <b>{won_skin}</b>"
        else:
            result_text = f"💥 <b>НЕУДАЧА!</b>\nШанс был {chance}%, скин сгорел..."

        cursor.execute("UPDATE users SET inventory = ? WHERE user_id = ?", (json.dumps(inventory, ensure_ascii=False), user_id))
        conn.commit()

    bot.answer_callback_query(call.id, "Апгрейд завершен!")
    bot.send_message(call.message.chat.id, result_text, parse_mode="HTML")


# --- МИНИ-ИГРА "МИНЫ" (САПЕР) ---
ACTIVE_MINES_GAMES = {}

def show_mines_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Ставка: 500", callback_data="mines_bet_500"),
        types.InlineKeyboardButton("💰 Ставка: 1,000", callback_data="mines_bet_1000"),
        types.InlineKeyboardButton("💰 Ставка: 5,000", callback_data="mines_bet_5000"),
        types.InlineKeyboardButton("💰 Ставка: 10,000", callback_data="mines_bet_10000"),
    )
    bot.send_message(
        message.chat.id,
        "💣 <b>Мини-игра «Мины»</b>\n\nВыбери сумму ставки, чтобы начать игру. На поле запрятаны мины — открывай безопасные ячейки и увеличивай свой выигрыш!",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('mines_bet_'))
def start_mines_game(call):
    bet = int(call.data.replace('mines_bet_', ''))
    user_id = call.from_user.id

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row or row[0] < bet:
            bot.answer_callback_query(call.id, f"❌ Недостаточно монет! Нужно {bet:,} 💰", show_alert=True)
            return
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user_id))
        conn.commit()

    # Создаем поле 3x3 (9 ячеек), из них 2 мины
    mines = set(random.sample(range(9), 2))
    ACTIVE_MINES_GAMES[user_id] = {
        'bet': bet,
        'mines': mines,
        'revealed': set(),
        'multiplier': 1.0
    }

    bot.answer_callback_query(call.id, "Игра начата!")
    send_mines_board(call.message, user_id, edit=False)


def send_mines_board(message, user_id, edit=True):
    game = ACTIVE_MINES_GAMES.get(user_id)
    if not game:
        return

    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for i in range(9):
        if i in game['revealed']:
            buttons.append(types.InlineKeyboardButton("💎", callback_data="mines_noop"))
        else:
            buttons.append(types.InlineKeyboardButton("❓", callback_data=f"mines_click_{i}"))
    
    markup.add(*buttons)
    if len(game['revealed']) > 0:
        current_win = int(game['bet'] * game['multiplier'])
        markup.add(types.InlineKeyboardButton(f"💰 Забрать выигрыш ({current_win:,} 💰)", callback_data="mines_cashout"))

    text = f"💣 <b>Мины | Ставка: {game['bet']:,}</b>\nМножитель: <b>x{game['multiplier']:.2f}</b>\nБезопасных ячеек открыто: {len(game['revealed'])}/7"

    if edit:
        try:
            bot.edit_message_text(text, message.chat.id, message.message_id, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)
    else:
            bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('mines_click_'))
def process_mines_click(call):
    user_id = call.from_user.id
    game = ACTIVE_MINES_GAMES.get(user_id)
    if not game:
        bot.answer_callback_query(call.id, "Игра не найдена. Начни заново!", show_alert=True)
        return

    idx = int(call.data.replace('mines_click_', ''))
    if idx in game['mines']:
        # Подорвался
        bet = game['bet']
        del ACTIVE_MINES_GAMES[user_id]
        bot.answer_callback_query(call.id, "💥 Бум! Ты подорвался на мине!", show_alert=True)
        bot.edit_message_text(f"💥 <b>Ты попался на мину!</b>\nСтавка {bet:,} сгорела.", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        return

    if idx not in game['revealed']:
        game['revealed'].add(idx)
        game['multiplier'] += 0.35

    if len(game['revealed']) >= 7:
        # Победа автоматически
        win = int(game['bet'] * game['multiplier'])
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, user_id))
            conn.commit()
        del ACTIVE_MINES_GAMES[user_id]
        bot.answer_callback_query(call.id, "🎉 Поздравляем, все безопасные ячейки открыты!")
        bot.edit_message_text(f"🏆 <b>ИДЕАЛЬНАЯ ПОБЕДА!</b>\nТы забрал сокровища и выиграл: <b>+{win:,} монет</b> 💰", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        return

    bot.answer_callback_query(call.id, "Чисто! Идем дальше.")
    send_mines_board(call.message, user_id, edit=True)


@bot.callback_query_handler(func=lambda call: call.data == 'mines_cashout')
def process_mines_cashout(call):
    user_id = call.from_user.id
    game = ACTIVE_MINES_GAMES.get(user_id)
    if not game:
        return

    win = int(game['bet'] * game['multiplier'])
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (win, user_id))
        conn.commit()

    del ACTIVE_MINES_GAMES[user_id]
    bot.answer_callback_query(call.id, f"Выигрыш успешно зачислен!")
    bot.edit_message_text(f"✅ <b>Выигрыш забран!</b>\nТвоя добыча: <b>+{win:,} монет</b> 💰", call.message.chat.id, call.message.message_id, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == 'mines_noop')
def mines_noop(call):
    bot.answer_callback_query(call.id, "Эта ячейка уже открыта!")


# --- ДОНАТ ЗА ЗВЕЗДЫ TELEGRAM ---
def donate_menu_message(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⭐ 15 звезд = 10,000 монет", callback_data="pay_stars_15"),
        types.InlineKeyboardButton("⭐ 30 звезд = 30,000 монет", callback_data="pay_stars_30"),
        types.InlineKeyboardButton("⭐ 40 звезд = 50,000 монет", callback_data="pay_stars_40")
    )
    bot.send_message(
        message.chat.id,
        "⭐ <b>Покупка игровой валюты за Telegram Stars</b>\n\nВыбери подходящий пакет:",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_stars_'))
def send_star_invoice(call):
    stars_amount = int(call.data.replace('pay_stars_', ''))
    
    packages = {
        15: {'coins': 10000, 'title': 'Пакет "Старт" (10k монет)'},
        30: {'coins': 30000, 'title': 'Пакет "Медиум" (30k монет)'},
        40: {'coins': 50000, 'title': 'Пакет "Премиум" (50k монет)'}
    }
    
    pkg = packages.get(stars_amount)
    if not pkg:
        return

    prices = [types.LabeledPrice(label="Telegram Stars", amount=stars_amount)]
    
    bot.send_invoice(
        chat_id=call.message.chat.id,
        title=pkg['title'],
        description=f"Пополнение баланса в CS2 симуляторе на {pkg['coins']:,} монет.",
        invoice_payload=f"add_coins_{pkg['coins']}",
        provider_token="",
        currency="XTR",
        prices=prices,
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton(f"Оплатить ⭐ {stars_amount}", pay=True)
        )
    )


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    user_id = message.from_user.id
    
    if payload.startswith("add_coins_"):
        coins_to_add = int(payload.replace("add_coins_", ""))
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (coins_to_add, user_id))
            conn.commit()
        
        bot.send_message(
            message.chat.id,
            f"🎉 <b>Оплата прошла успешно!</b>\nНа твой баланс зачислено: <b>+{coins_to_add:,} монет</b> 💰\nПриятной игры и удачи с ножами!",
            parse_mode="HTML"
        )


def show_profile(message):
    user_id = message.from_user.id
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, balance, inventory FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()

        cursor.execute("SELECT name, price, rarity FROM shop")
        shop_items = cursor.fetchall()
        price_map = {
            f"{rarity} {name}": price for name, price, rarity in shop_items
        }

    username, balance, inv_json = row[0], row[1], row[2]
    inventory = json.loads(inv_json)
    inv_value = sum(price_map.get(item, 0) for item in inventory)

    text = (
        f"👤 <b>Профиль игрока: {username}</b>\n"
        f"💰 Баланс: <b>{balance}</b> монет\n"
        f"💎 Стоимость инвентаря: <b>{inv_value}</b> 💰\n"
        f"📦 Предметов: <b>{len(inventory)}</b>\n\n"
        f"🎒 <b>Инвентарь:</b>\n"
    )

    if inventory:
        text += "\n".join([f"• {item}" for item in inventory[-20:]])
    else:
        text += "<i>Пусто. Купи что-нибудь в магазине или открой кейс!</i>"

    try:
        photos = bot.get_user_profile_photos(user_id)
        if photos.total_count > 0:
            photo_file_id = photos.photos[0][-1].file_id
            bot.send_photo(
                message.chat.id,
                photo_file_id,
                caption=text,
                parse_mode="HTML",
            )
            return
    except Exception:
        pass

    bot.send_message(message.chat.id, text, parse_mode="HTML")


def show_top(message):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, price, rarity FROM shop")
        shop_items = cursor.fetchall()
        price_map = {
            f"{rarity} {name}": price for name, price, rarity in shop_items
        }

        cursor.execute("SELECT username, inventory FROM users")
        users = cursor.fetchall()

    leaderboard = []
    for username, inv_json in users:
        try:
            inventory = json.loads(inv_json)
            inv_value = sum(price_map.get(item, 0) for item in inventory)
        except Exception:
            inv_value = 0
        leaderboard.append((username, inv_value))

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    top_10 = leaderboard[:10]

    text = "🏆 <b>ТОП-10 ИГРОКОВ ПО СТОИМОСТИ ИНВЕНТАРЯ</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]

    for i, (name, val) in enumerate(top_10, 1):
        icon = medals[i - 1] if i <= 3 else f"{i}."
        text += f"{icon} <b>{name}</b> — {val:,} 💰\n"

    bot.send_message(message.chat.id, text, parse_mode="HTML")


def prompt_promo(message):
    msg = bot.send_message(
        message.chat.id, "🎟 <b>Введи промокод:</b>", parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_promo)


def process_promo(message):
    if not message.text:
        return

    if any(
        k in message.text
        for k in ["Фармить", "Магазин", "Кейсы", "Апгрейдер", "Мины", "Донат (Звезды)", "Профиль", "Топ 10", "Промокод"]
    ):
        menu_handler(message)
        return

    code = message.text.strip().upper()
    user_id = message.from_user.id

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reward, max_activations, used_count FROM promocodes WHERE code = ?",
            (code,),
        )
        promo = cursor.fetchone()

        if not promo:
            bot.send_message(
                message.chat.id, "❌ Промокод не найден или устарел."
            )
            return

        reward, max_activations, used_count = promo

        if used_count >= max_activations:
            bot.send_message(
                message.chat.id,
                "❌ Лимит активаций этого промокода исчерпан!",
            )
            return

        cursor.execute(
            "SELECT 1 FROM promo_uses WHERE user_id = ? AND code = ?",
            (user_id, code),
        )
        if cursor.fetchone():
            bot.send_message(
                message.chat.id, "❌ Ты уже активировал этот промокод!"
            )
            return

        cursor.execute(
            "UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?",
            (code,),
        )
        cursor.execute(
            "INSERT INTO promo_uses (user_id, code) VALUES (?, ?)",
            (user_id, code),
        )
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (reward, user_id),
        )
        conn.commit()

    bot.send_message(
        message.chat.id,
        f"🎉 <b>Промокод активирован!</b>\nТебе зачислено: <b>+{reward}</b> монет! 💰",
        parse_mode="HTML",
    )


# --- СКРЫТАЯ АДМИНКА ---
@bot.message_handler(commands=["admin"])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return

    text = (
        "👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n\n"
        "<b>Команды:</b>\n"
        "• <code>/addpromo [КОД] [СУММА] [АКТИВАЦИИ]</code> — создать промокод\n"
        "<i>Пример: /addpromo GIFT1000 1000 10</i>\n\n"
        "• <code>/additem [ЦЕНА] [РЕДКОСТЬ] [НАЗВАНИЕ]</code> — добавить скин\n"
        "<i>Пример: /additem 5000 🔴Тайное AK-47 | Vulcan</i>"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["addpromo"])
def addpromo_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) < 4:
        bot.send_message(
            message.chat.id,
            "❌ Использование: /addpromo [КОД] [СУММА] [АКТИВАЦИИ]\nПример: /addpromo GIFT1000 1000 10",
        )
        return

    code = args[1].upper()
    reward, max_act = args[2], args[3]

    if not reward.isdigit() or not max_act.isdigit():
        bot.send_message(
            message.chat.id, "❌ Сумма и количество должны быть числами!"
        )
        return

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO promocodes (code, reward, max_activations, used_count) VALUES (?, ?, ?, 0)",
            (code, int(reward), int(max_act)),
        )
        conn.commit()

    bot.send_message(
        message.chat.id,
        f"✅ Промокод <b>{code}</b> создан!\n💰 Награда: {reward} монет\n👥 Лимит: {max_act} человек",
        parse_mode="HTML",
    )


@bot.message_handler(commands=["additem"])
def additem_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        bot.send_message(
            message.chat.id,
            "❌ Использование: /additem [ЦЕНА] [РЕДКОСТЬ] [НАЗВАНИЕ]",
        )
        return

    price, rarity, name = args[1], args[2], args[3]

    if not price.isdigit():
        bot.send_message(message.chat.id, "❌ Цена должна быть числом!")
        return

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO shop (name, price, rarity) VALUES (?, ?, ?)",
            (name, int(price), rarity),
        )
        conn.commit()

    bot.send_message(
        message.chat.id,
        f"✅ Скин <b>{rarity} {name}</b> добавлен за {price} монет!",
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "ignore" or call.data.startswith('mines_'):
        return

    if call.data.startswith("page_"):
        page = int(call.data.split("_")[1])
        markup, _ = get_shop_markup(page=page)
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )
        bot.answer_callback_query(call.id)

    elif call.data.startswith("buy_"):
        _, item_id, page = call.data.split("_")
        item_id = int(item_id)
        user_id = call.from_user.id

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, price, rarity FROM shop WHERE item_id = ?",
                (item_id,),
            )
            item = cursor.fetchone()

            if not item:
                bot.answer_callback_query(
                    call.id, "❌ Предмет не найден!", show_alert=True
                )
                return

            item_name, item_price, item_rarity = item

            cursor.execute(
                "SELECT balance, inventory FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return
            balance, inv_json = row

            if balance < item_price:
                bot.answer_callback_query(
                    call.id,
                    f"❌ Недостаточно монет! Нужно {item_price} 💰",
                    show_alert=True,
                )
                return

            inventory = json.loads(inv_json)
            full_item_name = f"{item_rarity} {item_name}"
            inventory.append(full_item_name)

            cursor.execute(
                "UPDATE users SET balance = ?, inventory = ? WHERE user_id = ?",
                (
                    balance - item_price,
                    json.dumps(inventory, ensure_ascii=False),
                    user_id,
                ),
            )
            conn.commit()

        bot.answer_callback_query(
            call.id,
            f"🎉 Успешно куплено: {full_item_name}",
            show_alert=True,
        )


if __name__ == "__main__":
    init_db()
    print("🚀 Бот успешно запущен: 75+ скинов, апгрейдер и мини-игра «Мины» активны!")
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
