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

INITIAL_SKINS = [
    ("P250 | Sand Dune", 100, "⚪ Ширпотреб"),
    ("AK-47 | Safari Mesh", 150, "⚪ Ширпотреб"),
    ("Glock-18 | High Beam", 250, "🟦 Армейское"),
    ("AWP | Pit Viper", 350, "🟦 Армейское"),
    ("M4A4 | Magnesium", 450, "🟦 Армейское"),
    ("Desert Eagle | Light Rail", 600, "🟪 Запрещенное"),
    ("USP-S | Cyrex", 800, "🟪 Запрещенное"),
    ("AK-47 | Rat Rod", 1000, "🟪 Запрещенное"),
    ("AWP | Atheris", 1200, "🟪 Запрещенное"),
    ("M4A1-S | Nightmare", 1500, "🟪 Запрещенное"),
    ("AK-47 | Redline", 2000, "💖 Засекреченное"),
    ("AWP | Redline", 2500, "💖 Засекреченное"),
    ("Desert Eagle | Code Red", 3000, "💖 Засекреченное"),
    ("M4A4 | Neo-Noir", 3500, "💖 Засекреченное"),
    ("USP-S | Kill Confirmed", 4500, "💖 Засекреченное"),
    ("AK-47 | The Empress", 6000, "🔴 Тайное"),
    ("M4A1-S | Printstream", 7500, "🔴 Тайное"),
    ("AWP | Asiimov", 9000, "🔴 Тайное"),
    ("AK-47 | Fire Serpent", 15000, "🔴 Тайное"),
    ("AWP | Dragon Lore", 30000, "🔴 Тайное"),
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
]


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
        f"🛒 <b>Магазин</b> — покупай редкие скины\n"
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
        k in m.text for k in ["Фармить", "Магазин", "Профиль", "Топ 10", "Промокод"]
    )
)
def menu_handler(message):
    check_user_exists(message.from_user.id, message.from_user.first_name)
    text = message.text

    if "Фармить" in text:
        farm_logic(message)
    elif "Магазин" in text:
        show_shop(message)
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
        "🛒 <b>КАТАЛОГ СКИНОВ CS2</b>\nВыбери скин для покупки:",
        parse_mode="HTML",
        reply_markup=markup,
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
        text += "\n".join([f"• {item}" for item in inventory])
    else:
        text += "<i>Пусто. Купи что-нибудь в магазине!</i>"

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
        text += f"{icon} <b>{name}</b> — {val} 💰\n"

    bot.send_message(message.chat.id, text, parse_mode="HTML")


def prompt_promo(message):
    msg = bot.send_message(
        message.chat.id, "🎟 <b>Введи промокод:</b>", parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_promo)


def process_promo(message):
    if not message.text:
        return

    # Если пользователь нажало кнопку меню вместо ввода кода — перенаправляем
    if any(
        k in message.text
        for k in ["Фармить", "Магазин", "Профиль", "Топ 10", "Промокод"]
    ):
        menu_handler(message)
        return

    code = message.text.strip().upper()
    user_id = message.from_user.id

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reward, max_activations, used_count FROM promocodes WHERE"
            " code = ?",
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
        f"🎉 <b>Промокод активирован!</b>\nТебе зачислено: <b>+{reward}</b>"
        " монет! 💰",
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
            "❌ Использование: /addpromo [КОД] [СУММА] [АКТИВАЦИИ]\nПример:"
            " /addpromo GIFT1000 1000 10",
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
            "INSERT OR REPLACE INTO promocodes (code, reward, max_activations,"
            " used_count) VALUES (?, ?, ?, 0)",
            (code, int(reward), int(max_act)),
        )
        conn.commit()

    bot.send_message(
        message.chat.id,
        f"✅ Промокод <b>{code}</b> создан!\n💰 Награда: {reward} монет\n👥 Лимит:"
        f" {max_act} человек",
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
    if call.data == "ignore":
        bot.answer_callback_query(call.id)
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
    print("🚀 Ошибки кнопок устранены! Бот готов к работе.")
    bot.remove_webhook()
bot.infinity_polling(skip_pending=True)
