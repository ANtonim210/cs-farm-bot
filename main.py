import asyncio
import logging
import os
import secrets
import string
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("file-gate")

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
}
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "10000"))


def normalize_database_url(url: str) -> str:
    """asyncpg uses ssl=... separately; remove provider's sslmode query option."""
    parts = urlsplit(url.replace("postgres://", "postgresql://", 1))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in {"sslmode", "channel_binding"}]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class AdminFlow(StatesGroup):
    waiting_file = State()
    waiting_extra_decision = State()
    waiting_second_file = State()
    waiting_channel_id = State()
    waiting_channel_link = State()
    waiting_delete_token = State()


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
    await p.execute("""
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
        CREATE TABLE IF NOT EXISTS required_channels (
            id BIGSERIAL PRIMARY KEY,
            chat_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            invite_url TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def chat_target(value: str):
    """Convert numeric Telegram chat IDs from PostgreSQL text to int."""
    return int(value) if value.lstrip("-").isdigit() else value


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить файл", callback_data="adm:add_file")],
        [InlineKeyboardButton(text="📁 Список файлов", callback_data="adm:files")],
        [InlineKeyboardButton(text="➕ Добавить канал", callback_data="adm:add_channel")],
        [InlineKeyboardButton(text="📢 Список каналов", callback_data="adm:channels")],
        [InlineKeyboardButton(text="🗑 Удалить файл", callback_data="adm:delete_file")],
    ])


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
    return any([
        message.document, message.photo, message.video, message.audio,
        message.voice, message.video_note, message.animation, message.sticker,
    ])


def new_token(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def get_file_row(token: str):
    return await (await db()).fetchrow("SELECT * FROM files WHERE token = $1", token)


async def check_user_subscriptions(user_id: int) -> tuple[bool, list[asyncpg.Record]]:
    channels = await (await db()).fetch("SELECT * FROM required_channels ORDER BY id")
    missing = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_target(channel["chat_id"]), user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                missing.append(channel)
            elif member.status == ChatMemberStatus.RESTRICTED and not getattr(member, "is_member", False):
                missing.append(channel)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            log.warning("Cannot check membership for channel %s: %s", channel["chat_id"], exc)
            raise RuntimeError(
                f"Не могу проверить канал {channel['title']}. Добавь бота администратором канала."
            ) from exc
    return not missing, missing


def subscription_keyboard(channels, token: str) -> InlineKeyboardMarkup:
    rows = []
    for channel in channels:
        rows.append([InlineKeyboardButton(text=f"Подписаться: {channel['title'][:45]}", url=channel["invite_url"])])
    rows.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data=f"check:{token}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def deliver_file(user_id: int, token: str) -> None:
    row = await get_file_row(token)
    if not row:
        await bot.send_message(user_id, "Эта ссылка недействительна или файл удалён.")
        return

    # Copy each original Telegram message directly inside Telegram. Nothing is
    # downloaded to Render; a single link may contain one or two messages.
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
        await (await db()).execute("UPDATE files SET downloads = downloads + 1 WHERE token = $1", token)
    except TelegramBadRequest:
        log.exception("copyMessage failed for token=%s after %s/%s messages", token, delivered, len(attachments))
        if delivered:
            await bot.send_message(
                user_id,
                f"Первый файл отправлен, но второй скопировать не удалось ({delivered}/{len(attachments)}). "
                "Сообщи администратору."
            )
        else:
            await bot.send_message(
                user_id,
                "Не получилось выдать файл. Возможно, исходное сообщение удалено "
                "или Telegram не разрешает его копирование. Сообщи администратору."
            )


async def handle_file_link(user_id: int, token: str) -> None:
    row = await get_file_row(token)
    if not row:
        await bot.send_message(user_id, "Ссылка не найдена или файл был удалён.")
        return
    try:
        subscribed, missing = await check_user_subscriptions(user_id)
    except RuntimeError as exc:
        await bot.send_message(user_id, f"⚠️ {exc}")
        return
    if not subscribed:
        await bot.send_message(
            user_id,
            "Чтобы получить файл, подпишись на обязательные каналы и нажми «Проверить подписку».",
            reply_markup=subscription_keyboard(missing, token),
        )
        return
    await deliver_file(user_id, token)


@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject):
    if not message.from_user:
        return
    if command.args:
        await handle_file_link(message.from_user.id, command.args.strip())
    else:
        await message.answer(
            "Привет! 👋\nОткрой специальную ссылку на файл, чтобы получить его."
        )


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
    action = callback.data.split(":", 1)[1]
    await callback.answer()
    if action == "add_file":
        await state.set_state(AdminFlow.waiting_file)
        await callback.message.answer(
            "Отправь мне файл одним сообщением. Я сохраню только ID чата и сообщения — "
            "сам файл на Render скачиваться не будет.\n\n/cancel — отмена."
        )
    elif action == "files":
        rows = await (await db()).fetch("SELECT token, title, second_title, downloads, created_at FROM files ORDER BY created_at DESC LIMIT 50")
        if not rows:
            await callback.message.answer("Файлов пока нет.")
            return
        text = "📁 <b>Последние файлы:</b>\n\n"
        for row in rows:
            link = f"https://t.me/{bot_username}?start={row['token']}"
            extra_title = row["second_title"] if "second_title" in row.keys() else None
            label = f"{row['title']} + {extra_title}" if extra_title else row["title"]
            text += f"• <b>{label}</b> — {row['downloads']} выдач\n<code>{link}</code>\nID: <code>{row['token']}</code>\n\n"
        await callback.message.answer(text, disable_web_page_preview=True)
    elif action == "add_channel":
        await state.set_state(AdminFlow.waiting_channel_id)
        await callback.message.answer(
            "Пришли @username публичного канала или числовой chat_id приватного канала.\n"
            "Бот должен быть администратором канала.\n/cancel — отмена."
        )
    elif action == "channels":
        rows = await (await db()).fetch("SELECT * FROM required_channels ORDER BY id")
        if not rows:
            await callback.message.answer("Обязательных каналов пока нет.")
            return
        text = "📢 <b>Обязательные каналы:</b>\n\n"
        for row in rows:
            text += f"• {row['title']}\nID: <code>{row['chat_id']}</code>\nСсылка: {row['invite_url']}\n\n"
        text += "Удаление: /delchannel ID"
        await callback.message.answer(text, disable_web_page_preview=True)
    elif action == "delete_file":
        await state.set_state(AdminFlow.waiting_delete_token)
        await callback.message.answer("Пришли ID файла из списка. /cancel — отмена.")


def upload_decision_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить второй файл", callback_data="upload:second")],
        [InlineKeyboardButton(text="✅ Готово, только один файл", callback_data="upload:done")],
    ])


async def save_upload(
    reply_message: Message,
    owner_id: int,
    state: FSMContext,
    second: tuple[int, int, str] | None = None,
) -> None:
    data = await state.get_data()
    token = new_token()
    first_title = data["first_title"]
    second_source_chat_id, second_message_id, second_title = second or (None, None, None)

    await (await db()).execute(
        "INSERT INTO files(token, owner_id, source_chat_id, message_id, title, "
        "second_source_chat_id, second_message_id, second_title) "
        "VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
        token,
        owner_id,
        data["first_source_chat_id"],
        data["first_message_id"],
        first_title,
        second_source_chat_id,
        second_message_id,
        second_title,
    )
    await state.clear()
    link = f"https://t.me/{bot_username}?start={token}"
    files_text = f"1. {first_title}"
    if second_title:
        files_text += f"\n2. {second_title}"
    await reply_message.answer(
        f"✅ Ссылка создана!\n\n<b>Файлы:</b>\n{files_text}\n\n"
        f"Ссылка для выдачи обоих файлов:\n<code>{link}</code>\n\n"
        f"ID набора: <code>{token}</code>",
        disable_web_page_preview=True,
    )


@router.message(AdminFlow.waiting_file)
async def receive_file(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    if not has_supported_content(message):
        await message.answer("Это не похоже на файл/медиа. Отправь документ, фото, видео или аудио одним сообщением.")
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
        await callback.answer("Это действие уже неактуально. Начни добавление заново через /admin.", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]
    if action == "second":
        await state.set_state(AdminFlow.waiting_second_file)
        await callback.answer()
        await callback.message.answer("Отправь второй файл одним сообщением.\n/cancel — отмена.")
    elif action == "done":
        await callback.answer()
        await save_upload(callback.message, callback.from_user.id, state)
    else:
        await callback.answer("Неизвестное действие", show_alert=True)


@router.message(AdminFlow.waiting_second_file)
async def receive_second_file(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    if not has_supported_content(message):
        await message.answer("Не вижу файл. Пришли второй документ, фото, видео или аудио одним сообщением.")
        return

    await save_upload(
        message,
        message.from_user.id,
        state,
        second=(message.chat.id, message.message_id, file_title(message)),
    )


@router.message(AdminFlow.waiting_channel_id)
async def receive_channel_id(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    chat_ref = (message.text or "").strip()
    if not chat_ref:
        await message.answer("Пришли @username или числовой chat_id.")
        return
    try:
        chat = await bot.get_chat(chat_target(chat_ref))
        # Ensure bot can inspect members; admins need to add bot to the channel.
        me = await bot.get_me()
        bot_member = await bot.get_chat_member(chat.id, me.id)
        if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await message.answer("Сначала добавь бота администратором этого канала, затем повтори добавление.")
            return
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        await message.answer(f"Не удалось получить канал или проверить права бота: {exc}\nПроверь chat_id и права администратора.")
        return
    await state.update_data(channel_id=str(chat.id), channel_title=chat.title or chat.username or str(chat.id))
    await state.set_state(AdminFlow.waiting_channel_link)
    default_link = f"https://t.me/{chat.username}" if chat.username else ""
    await message.answer(
        "Теперь пришли ссылку, по которой пользователь сможет вступить в канал.\n"
        + (f"Для публичного канала можно отправить: {default_link}\n" if default_link else "")
        + "Для приватного канала пришли invite link."
    )


@router.message(AdminFlow.waiting_channel_link)
async def receive_channel_link(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    invite = (message.text or "").strip()
    if not (invite.startswith("https://t.me/") or invite.startswith("http://t.me/")):
        await message.answer("Нужна ссылка Telegram вида https://t.me/имя_канала или https://t.me/+приглашение.")
        return
    data = await state.get_data()
    try:
        await (await db()).execute(
            "INSERT INTO required_channels(chat_id, title, invite_url) VALUES($1,$2,$3) "
            "ON CONFLICT(chat_id) DO UPDATE SET title=EXCLUDED.title, invite_url=EXCLUDED.invite_url",
            data["channel_id"], data["channel_title"], invite,
        )
    except Exception:
        log.exception("Failed to save channel")
        await message.answer("Не удалось сохранить канал. Попробуй ещё раз.")
        return
    await state.clear()
    await message.answer(f"✅ Канал добавлен в проверку: <b>{data['channel_title']}</b>")


@router.message(AdminFlow.waiting_delete_token)
async def delete_file_by_token(message: Message, state: FSMContext):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    token = (message.text or "").strip()
    result = await (await db()).execute("DELETE FROM files WHERE token = $1", token)
    await state.clear()
    if result.endswith("1"):
        await message.answer("✅ Файл и его ссылка удалены.")
    else:
        await message.answer("Файл с таким ID не найден.")


@router.message(Command("delchannel"))
async def delete_channel_command(message: Message, command: CommandObject):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    channel_id = (command.args or "").strip()
    if not channel_id:
        await message.answer("Формат: /delchannel -1001234567890")
        return
    result = await (await db()).execute("DELETE FROM required_channels WHERE chat_id = $1", channel_id)
    await message.answer("✅ Канал удалён." if result.endswith("1") else "Канал не найден.")


@router.callback_query(F.data.startswith("check:"))
async def check_subscription_callback(callback: CallbackQuery):
    if not callback.from_user:
        return
    token = callback.data.split(":", 1)[1]
    try:
        subscribed, missing = await check_user_subscriptions(callback.from_user.id)
    except RuntimeError as exc:
        await callback.answer("Ошибка проверки", show_alert=True)
        await callback.message.answer(f"⚠️ {exc}")
        return
    if not subscribed:
        await callback.answer("Подписка пока не найдена. Подпишись и попробуй ещё раз.", show_alert=True)
        return
    await callback.answer("Подписка подтверждена!")
    await deliver_file(callback.from_user.id, token)


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
async def telegram_webhook(request: Request, secret: str | None = None,
                           x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    if WEBHOOK_SECRET:
        if secret != WEBHOOK_SECRET or x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        log.exception("Failed to process Telegram update")
        # Return 200 to avoid endless retries for malformed/unprocessable updates.
    return {"ok": True}
