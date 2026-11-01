import html
import logging
import os
import secrets
import string
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    Update,
)
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("file-gate")

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip()
}
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "10000"))
MAX_STARS_PRICE = 100_000


def normalize_database_url(url: str) -> str:
    """asyncpg receives SSL separately; remove provider SSL query options."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in {"sslmode", "channel_binding"}
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class AdminFlow(StatesGroup):
    waiting_file = State()
    waiting_extra_decision = State()
    waiting_second_file = State()
    waiting_price_mode = State()
    waiting_price = State()


router = Router()
dp = Dispatcher()
dp.include_router(router)
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
pool: asyncpg.Pool | None = None
bot_username = ""


async def db() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    return pool


async def init_db() -> None:
    p = await db()
    await p.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            token TEXT PRIMARY KEY,
            owner_id BIGINT NOT NULL,
            source_chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            second_source_chat_id BIGINT,
            second_message_id BIGINT,
            second_title TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            downloads BIGINT NOT NULL DEFAULT 0
        );
        ALTER TABLE files ADD COLUMN IF NOT EXISTS second_source_chat_id BIGINT;
        ALTER TABLE files ADD COLUMN IF NOT EXISTS second_message_id BIGINT;
        ALTER TABLE files ADD COLUMN IF NOT EXISTS second_title TEXT;
        ALTER TABLE files ADD COLUMN IF NOT EXISTS is_premium BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE files ADD COLUMN IF NOT EXISTS price_stars INTEGER NOT NULL DEFAULT 1;

        CREATE TABLE IF NOT EXISTS file_deliveries (
            token TEXT NOT NULL REFERENCES files(token) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'sending', 'paid', 'delivered', 'partial')),
            charge_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (token, user_id)
        );

        -- Legacy required_channels table is no longer used by this version.
        DROP TABLE IF EXISTS required_channels;
        """
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить файл", callback_data="adm:add_file")],
            [InlineKeyboardButton(text="📁 Список файлов", callback_data="adm:files")],
        ]
    )


def file_title(message: Message) -> str:
    media = message.document or message.video or message.audio or message.animation
    if media and getattr(media, "file_name", None):
        return media.file_name
    if message.photo:
        return "Фото"
    if message.video:
        return "Видео"
    if message.audio:
        return message.audio.title or message.audio.file_name or "Аудио"
    if message.voice:
        return "Голосовое сообщение"
    if message.video_note:
        return "Видеосообщение"
    if message.sticker:
        return f"Стикер {message.sticker.emoji or ''}".strip()
    if message.animation:
        return "GIF-анимация"
    return (message.caption or message.text or "Файл").strip()[:120]


def has_supported_content(message: Message) -> bool:
    return any(
        [
            message.document,
            message.photo,
            message.video,
            message.audio,
            message.voice,
            message.video_note,
            message.animation,
            message.sticker,
        ]
    )


def new_token(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def get_file_row(token: str):
    return await (await db()).fetchrow("SELECT * FROM files WHERE token = $1", token)


def upload_decision_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить второй файл", callback_data="upload:second")],
            [InlineKeyboardButton(text="✅ Готово, один файл", callback_data="upload:done")],
        ]
    )


def price_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆓 Бесплатная выдача", callback_data="price:free")],
            [InlineKeyboardButton(text="⭐ Платная выдача (Stars)", callback_data="price:paid")],
        ]
    )


def files_page_keyboard(rows, offset: int, total: int) -> InlineKeyboardMarkup:
    keyboard = []
    for row in rows:
        title = row["title"][:28]
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗑 Удалить: {title}",
                callback_data=f"adm:delete:{row['token']}:{offset}",
            )
        ])
    navigation = []
    if offset > 0:
        navigation.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm:filespage:{max(0, offset - 5)}"))
    if offset + len(rows) < total:
        navigation.append(InlineKeyboardButton(text="Далее ➡️", callback_data=f"adm:filespage:{offset + 5}"))
    if navigation:
        keyboard.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def show_files_page(message: Message, offset: int = 0, *, edit: bool = False) -> None:
    p = await db()
    total = await p.fetchval("SELECT COUNT(*) FROM files")
    if total and offset >= total:
        offset = ((total - 1) // 5) * 5
    rows = await p.fetch(
        "SELECT token,title,second_title,downloads,is_premium,price_stars "
        "FROM files ORDER BY created_at DESC LIMIT 5 OFFSET $1",
        offset,
    )
    if not rows:
        text = "📁 Файлов пока нет." if total == 0 else "На этой странице файлов нет."
        if edit:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
        else:
            await message.answer(text)
        return

    lines = [f"📁 <b>Файлы ({offset + 1}–{offset + len(rows)} из {total}):</b>\n"]
    for number, row in enumerate(rows, start=offset + 1):
        link = f"https://t.me/{bot_username}?start={row['token']}"
        title = html.escape(row["title"])
        if row["second_title"]:
            title += " + " + html.escape(row["second_title"])
        mode = f"⭐ {row['price_stars']} Stars" if row["is_premium"] else "🆓 Бесплатно"
        lines.append(
            f"<b>{number}. {title}</b>\n"
            f"Режим: {mode} · Выдач: {row['downloads']}\n"
            f"Ссылка: <code>{link}</code>\n"
            f"ID: <code>{row['token']}</code>"
        )
    text = "\n\n".join(lines)
    markup = files_page_keyboard(rows, offset, total)
    if edit:
        await message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await message.answer(text, reply_markup=markup, disable_web_page_preview=True)


async def ask_price_mode(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.waiting_price_mode)
    await message.answer(
        "Как выдавать этот набор файлов?\n\n"
        "🆓 Бесплатно — пользователь получает его без оплаты.\n"
        "⭐ Платно — пользователь оплачивает получение Telegram Stars.",
        reply_markup=price_mode_keyboard(),
    )


async def save_upload(
    reply_message: Message,
    owner_id: int,
    state: FSMContext,
    *,
    is_premium: bool,
    price_stars: int,
) -> None:
    data = await state.get_data()
    token = new_token()
    second_source_chat_id, second_message_id, second_title = data.get(
        "second_file", (None, None, None)
    )
    await (await db()).execute(
        """
        INSERT INTO files(
            token, owner_id, source_chat_id, message_id, title,
            second_source_chat_id, second_message_id, second_title,
            is_premium, price_stars
        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        token,
        owner_id,
        data["first_source_chat_id"],
        data["first_message_id"],
        data["first_title"],
        second_source_chat_id,
        second_message_id,
        second_title,
        is_premium,
        price_stars,
    )
    await state.clear()
    link = f"https://t.me/{bot_username}?start={token}"
    names = f"1. {html.escape(data['first_title'])}"
    if second_title:
        names += f"\n2. {html.escape(second_title)}"
    mode = f"⭐ Платная выдача: {price_stars} Stars" if is_premium else "🆓 Бесплатная выдача"
    await reply_message.answer(
        f"✅ Ссылка создана!\n\n<b>Файлы:</b>\n{names}\n\n"
        f"<b>Режим:</b> {mode}\n"
        f"<b>Одна выдача на пользователя:</b> да\n\n"
        f"Ссылка: <code>{link}</code>\n"
        f"ID набора: <code>{token}</code>",
        disable_web_page_preview=True,
    )


async def send_invoice_for_file(user_id: int, token: str, row) -> None:
    payload = f"file:{token}:{user_id}"
    title = "Получение файла"
    description = row["title"]
    if row["second_title"]:
        description += f" + {row['second_title']}"
    description = description[:255]
    await bot.send_invoice(
        chat_id=user_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Выдача файла", amount=int(row["price_stars"]))],
    )


async def notify_existing_claim(user_id: int, status: str, token: str) -> None:
    if status == "delivered":
        await bot.send_message(user_id, "✅ Ты уже получал этот файл. Повторная выдача по этой ссылке недоступна.")
    elif status == "pending":
        row = await get_file_row(token)
        if row:
            await send_invoice_for_file(user_id, token, row)
        else:
            await bot.send_message(user_id, "Этот файл уже удалён.")
    elif status == "paid":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📥 Повторить выдачу", callback_data=f"retry:{token}")]]
        )
        await bot.send_message(
            user_id,
            "⭐ Оплата уже получена, но выдача ещё не завершена. Нажми кнопку, чтобы повторить отправку.",
            reply_markup=keyboard,
        )
    elif status == "sending":
        await bot.send_message(user_id, "⏳ Выдача уже обрабатывается. Не отправляй ссылку повторно.")
    elif status == "partial":
        await bot.send_message(
            user_id,
            "⚠️ Часть набора уже отправлена, но Telegram не смог скопировать все сообщения. "
            "Повторная автоматическая выдача отключена, чтобы не дублировать полученное. Напиши администратору.",
        )


async def deliver_reserved(user_id: int, token: str, *, paid: bool) -> None:
    row = await get_file_row(token)
    if not row:
        await bot.send_message(user_id, "Эта ссылка недействительна или файл удалён.")
        return

    attachments = [(row["source_chat_id"], row["message_id"])]
    if row["second_message_id"] is not None:
        attachments.append((row["second_source_chat_id"], row["second_message_id"]))

    delivered = 0
    try:
        for source_chat_id, message_id in attachments:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
            )
            delivered += 1

        async with (await db()).acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE file_deliveries SET status='delivered', updated_at=NOW() "
                    "WHERE token=$1 AND user_id=$2",
                    token,
                    user_id,
                )
                await conn.execute(
                    "UPDATE files SET downloads=downloads+1 WHERE token=$1",
                    token,
                )
        await bot.send_message(user_id, "✅ Готово! Набор файлов выдан. Повторно получить его по этой ссылке нельзя.")
    except TelegramAPIError:
        log.exception("copyMessage failed for token=%s after %s/%s messages", token, delivered, len(attachments))
        if delivered:
            await (await db()).execute(
                "UPDATE file_deliveries SET status='partial', updated_at=NOW() WHERE token=$1 AND user_id=$2",
                token,
                user_id,
            )
            await bot.send_message(
                user_id,
                f"⚠️ Удалось отправить только часть набора ({delivered}/{len(attachments)}). "
                "Чтобы не выдать первый файл повторно, автоматическая повторная отправка отключена. Напиши администратору.",
            )
        elif paid:
            await (await db()).execute(
                "UPDATE file_deliveries SET status='paid', updated_at=NOW() WHERE token=$1 AND user_id=$2",
                token,
                user_id,
            )
            await bot.send_message(
                user_id,
                "Оплата прошла, но Telegram не смог скопировать файл. Деньги не списываются повторно. "
                "Нажми ссылку ещё раз чуть позже или напиши администратору.",
            )
        else:
            await (await db()).execute(
                "DELETE FROM file_deliveries WHERE token=$1 AND user_id=$2 AND status='sending'",
                token,
                user_id,
            )
            await bot.send_message(
                user_id,
                "Не получилось выдать файл. Возможно, исходное сообщение удалено или Telegram не разрешает копирование. "
                "Попробуй ещё раз позже или напиши администратору.",
            )


async def handle_file_link(user_id: int, token: str) -> None:
    row = await get_file_row(token)
    if not row:
        await bot.send_message(user_id, "Ссылка не найдена или файл был удалён.")
        return

    if row["is_premium"]:
        inserted = await (await db()).fetchrow(
            "INSERT INTO file_deliveries(token,user_id,status) VALUES($1,$2,'pending') "
            "ON CONFLICT(token,user_id) DO NOTHING RETURNING token",
            token,
            user_id,
        )
        if not inserted:
            existing = await (await db()).fetchrow(
                "SELECT status FROM file_deliveries WHERE token=$1 AND user_id=$2",
                token,
                user_id,
            )
            if existing:
                await notify_existing_claim(user_id, existing["status"], token)
                return
        try:
            await send_invoice_for_file(user_id, token, row)
        except TelegramAPIError:
            log.exception("Could not send invoice")
            await bot.send_message(user_id, "Не удалось создать счёт. Попробуй открыть ссылку ещё раз позже.")
        return

    inserted = await (await db()).fetchrow(
        "INSERT INTO file_deliveries(token,user_id,status) VALUES($1,$2,'sending') "
        "ON CONFLICT(token,user_id) DO NOTHING RETURNING token",
        token,
        user_id,
    )
    if not inserted:
        existing = await (await db()).fetchrow(
            "SELECT status FROM file_deliveries WHERE token=$1 AND user_id=$2",
            token,
            user_id,
        )
        if existing:
            await notify_existing_claim(user_id, existing["status"], token)
        return
    await deliver_reserved(user_id, token, paid=False)


@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject):
    if not message.from_user:
        return
    if command.args:
        await handle_file_link(message.from_user.id, command.args.strip())
    else:
        await message.answer("Привет! 👋\nОткрой специальную ссылку на файл, чтобы получить его.")


@router.message(Command("myid"))
async def my_id_handler(message: Message):
    if message.from_user:
        await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>")


@router.message(Command("admin"))
async def admin_handler(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await state.clear()
    await message.answer("⚙️ Панель администратора:", reply_markup=admin_keyboard())


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено. /admin — меню администратора.")


@router.callback_query(F.data.startswith("adm:"))
async def admin_callbacks(callback: CallbackQuery, state: FSMContext):
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    data = callback.data or ""

    if data == "adm:add_file":
        await callback.answer()
        await state.set_state(AdminFlow.waiting_file)
        await callback.message.answer(
            "Отправь первый файл отдельным сообщением. Я сохраню только ID чата и сообщения — "
            "сам файл на Render скачиваться не будет.\n\n/cancel — отмена."
        )
    elif data == "adm:files":
        await callback.answer()
        await show_files_page(callback.message, 0)
    elif data.startswith("adm:filespage:"):
        await callback.answer()
        offset = int(data.rsplit(":", 1)[1])
        await show_files_page(callback.message, offset, edit=True)
    elif data.startswith("adm:delete:"):
        _, _, token, offset_text = data.split(":", 3)
        result = await (await db()).execute("DELETE FROM files WHERE token=$1", token)
        if result.endswith("1"):
            await callback.answer("Файл удалён")
        else:
            await callback.answer("Файл уже удалён или не найден", show_alert=True)
        await show_files_page(callback.message, int(offset_text), edit=True)
    else:
        await callback.answer("Неизвестное действие", show_alert=True)


@router.message(AdminFlow.waiting_file)
async def receive_file(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    if not has_supported_content(message):
        await message.answer("Не вижу файл. Отправь документ, фото, видео или аудио одним сообщением.")
        return
    await state.update_data(
        first_source_chat_id=message.chat.id,
        first_message_id=message.message_id,
        first_title=file_title(message),
    )
    await state.set_state(AdminFlow.waiting_extra_decision)
    await message.answer(
        "✅ Первый файл принят.\n\nНужен ещё один файл для этой же ссылки?",
        reply_markup=upload_decision_keyboard(),
    )


@router.callback_query(F.data.startswith("upload:"))
async def upload_decision_callback(callback: CallbackQuery, state: FSMContext):
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if await state.get_state() != AdminFlow.waiting_extra_decision.state:
        await callback.answer("Действие уже неактуально. Начни заново через /admin.", show_alert=True)
        return
    action = (callback.data or "").split(":", 1)[1]
    if action == "second":
        await state.set_state(AdminFlow.waiting_second_file)
        await callback.answer()
        await callback.message.answer("Отправь второй файл одним сообщением.\n/cancel — отмена.")
    elif action == "done":
        await callback.answer()
        await ask_price_mode(callback.message, state)
    else:
        await callback.answer("Неизвестное действие", show_alert=True)


@router.message(AdminFlow.waiting_second_file)
async def receive_second_file(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    if not has_supported_content(message):
        await message.answer("Не вижу второй файл. Пришли документ, фото, видео или аудио одним сообщением.")
        return
    await state.update_data(second_file=(message.chat.id, message.message_id, file_title(message)))
    await ask_price_mode(message, state)


@router.callback_query(F.data.startswith("price:"))
async def price_mode_callback(callback: CallbackQuery, state: FSMContext):
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    if await state.get_state() != AdminFlow.waiting_price_mode.state:
        await callback.answer("Действие уже неактуально. Начни заново через /admin.", show_alert=True)
        return
    mode = (callback.data or "").split(":", 1)[1]
    await callback.answer()
    if mode == "free":
        await save_upload(callback.message, callback.from_user.id, state, is_premium=False, price_stars=0)
    elif mode == "paid":
        await state.set_state(AdminFlow.waiting_price)
        await callback.message.answer(
            f"Введи стоимость выдачи в Telegram Stars (от 1 до {MAX_STARS_PRICE}).\n/cancel — отмена."
        )


@router.message(AdminFlow.waiting_price)
async def receive_price(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    try:
        price = int(raw)
    except ValueError:
        await message.answer("Введи целое число Stars, например 1 или 10.")
        return
    if not 1 <= price <= MAX_STARS_PRICE:
        await message.answer(f"Цена должна быть от 1 до {MAX_STARS_PRICE} Stars.")
        return
    await save_upload(message, message.from_user.id, state, is_premium=True, price_stars=price)


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    try:
        parts = query.invoice_payload.split(":")
        if len(parts) != 3 or parts[0] != "file":
            await query.answer(ok=False, error_message="Некорректный счёт.")
            return
        token, user_text = parts[1], parts[2]
        if int(user_text) != query.from_user.id:
            await query.answer(ok=False, error_message="Этот счёт создан для другого пользователя.")
            return
        row = await get_file_row(token)
        claim = await (await db()).fetchrow(
            "SELECT status FROM file_deliveries WHERE token=$1 AND user_id=$2",
            token,
            query.from_user.id,
        )
        if not row or not row["is_premium"] or not claim or claim["status"] != "pending":
            await query.answer(ok=False, error_message="Этот счёт уже недействителен. Открой ссылку заново.")
            return
        if query.currency != "XTR" or query.total_amount != int(row["price_stars"]):
            await query.answer(ok=False, error_message="Сумма счёта не совпадает. Открой ссылку заново.")
            return
        await query.answer(ok=True)
    except Exception:
        log.exception("Pre-checkout validation failed")
        try:
            await query.answer(ok=False, error_message="Не удалось проверить оплату. Попробуй позже.")
        except TelegramAPIError:
            pass


async def refund_duplicate_payment(user_id: int, charge_id: str) -> None:
    try:
        await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)
        await bot.send_message(
            user_id,
            "Похоже, оплата прошла повторно. Лишний платёж автоматически возвращён.",
        )
    except TelegramAPIError:
        log.exception("Could not refund duplicate Telegram Stars payment for user %s", user_id)
        await bot.send_message(
            user_id,
            "Получен повторный платёж, но автоматический возврат не удался. Напиши администратору.",
        )


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    if not message.from_user or not message.successful_payment:
        return
    payment = message.successful_payment
    user_id = message.from_user.id
    parts = payment.invoice_payload.split(":")
    if len(parts) != 3 or parts[0] != "file":
        log.error("Unknown successful payment payload: %s", payment.invoice_payload)
        return
    token, user_text = parts[1], parts[2]
    if not user_text.isdigit() or int(user_text) != user_id:
        await refund_duplicate_payment(user_id, payment.telegram_payment_charge_id)
        return

    accepted = False
    duplicate = False
    async with (await db()).acquire() as conn:
        async with conn.transaction():
            claim = await conn.fetchrow(
                "SELECT status,charge_id FROM file_deliveries WHERE token=$1 AND user_id=$2 FOR UPDATE",
                token,
                user_id,
            )
            file_row = await conn.fetchrow("SELECT token FROM files WHERE token=$1", token)
            if claim and file_row and claim["status"] == "pending":
                await conn.execute(
                    "UPDATE file_deliveries SET status='paid',charge_id=$3,updated_at=NOW() "
                    "WHERE token=$1 AND user_id=$2",
                    token,
                    user_id,
                    payment.telegram_payment_charge_id,
                )
                accepted = True
            elif claim and claim["charge_id"] == payment.telegram_payment_charge_id:
                # Telegram may retry the same successful_payment update.
                accepted = claim["status"] in {"paid", "sending", "delivered", "partial"}
            else:
                duplicate = True

    if duplicate or not accepted:
        await refund_duplicate_payment(user_id, payment.telegram_payment_charge_id)
        return
    await message.answer("⭐ Оплата получена! Отправляю твой файл...")
    await deliver_paid_file(user_id, token)


async def deliver_paid_file(user_id: int, token: str) -> None:
    claimed = await (await db()).fetchrow(
        "UPDATE file_deliveries SET status='sending',updated_at=NOW() "
        "WHERE token=$1 AND user_id=$2 AND status='paid' RETURNING token",
        token,
        user_id,
    )
    if not claimed:
        existing = await (await db()).fetchrow(
            "SELECT status FROM file_deliveries WHERE token=$1 AND user_id=$2",
            token,
            user_id,
        )
        if existing:
            await notify_existing_claim(user_id, existing["status"], token)
        return
    await deliver_reserved(user_id, token, paid=True)


@router.callback_query(F.data.startswith("retry:"))
async def retry_paid_delivery(callback: CallbackQuery):
    if not callback.from_user:
        return
    token = (callback.data or "").split(":", 1)[1]
    await callback.answer()
    await deliver_paid_file(callback.from_user.id, token)


@router.message(Command("paysupport"))
async def payment_support_handler(message: Message):
    await message.answer("По вопросам оплаты напиши администратору бота.")


@router.message()
async def fallback(message: Message):
    if message.from_user and is_admin(message.from_user.id):
        await message.answer("Для управления используй /admin. Для отмены действия — /cancel.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool, bot_username
    pool = await asyncpg.create_pool(
        dsn=normalize_database_url(DATABASE_URL),
        ssl="require",
        min_size=1,
        max_size=5,
        command_timeout=30,
    )
    await init_db()
    me = await bot.get_me()
    bot_username = me.username or ""
    base_url = os.getenv("WEBHOOK_URL", "").strip() or os.getenv("RENDER_EXTERNAL_URL", "").strip()
    if not base_url:
        raise RuntimeError("Set WEBHOOK_URL or use Render's RENDER_EXTERNAL_URL")
    base_url = base_url.rstrip("/")
    webhook_path = f"/telegram/{WEBHOOK_SECRET}" if WEBHOOK_SECRET else "/telegram"
    await bot.set_webhook(
        url=base_url + webhook_path,
        secret_token=WEBHOOK_SECRET or None,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=False,
    )
    log.info("Webhook set for %s", base_url + webhook_path)
    try:
        yield
    finally:
        await bot.session.close()
        if pool:
            await pool.close()


app = FastAPI(title="Telegram File Gate", lifespan=lifespan)


@app.get("/")
async def index():
    return {"service": "telegram-file-gate", "status": "ok"}


@app.get("/health")
async def health():
    try:
        await (await db()).fetchval("SELECT 1")
        return {"status": "ok", "database": "ok"}
    except Exception as exc:
        log.exception("Health check failed")
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(exc)[:200]})


@app.post("/telegram")
@app.post("/telegram/{secret}")
async def telegram_webhook(
    request: Request,
    secret: str | None = None,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if WEBHOOK_SECRET:
        if secret != WEBHOOK_SECRET or x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        log.exception("Failed to process Telegram update")
    return {"ok": True}
