import os
import asyncio
import sqlite3
import logging
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardRemove
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- НАСТРОЙКИ ПРИЛОЖЕНИЯ ---
TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СВОЙ_ТОКЕН_ЗДЕСЬ")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://cs-farm-bot.onrender.com")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

# --- БАЗА ДАННЫХ (SQLite) ---
DB_FILE = "catalog.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subtitle TEXT,
            tags TEXT,
            version TEXT,
            description TEXT,
            image_id TEXT,
            file_id_1 TEXT NOT NULL,
            file_name_1 TEXT,
            file_id_2 TEXT,
            file_name_2 TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- FSM ДЛЯ ДОБАВЛЕНИЯ ФАЙЛОВ АДМИНОМ ---
class AddItemState(StatesGroup):
    file1 = State()
    file1_name = State()
    file2_choice = State()
    file2 = State()
    file2_name = State()
    title = State()
    subtitle = State()
    tags = State()
    version = State()
    description = State()
    image = State()

# --- БОТ КОМАНДЫ ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    clean_msg = await message.answer("🔄 Обновляем интерфейс...", reply_markup=ReplyKeyboardRemove())
    await clean_msg.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🚀 Открыть Каталог Софта",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])
    await message.answer(
        "👋 **Добро пожаловать в CyberStore!**\n\n"
        "Жми кнопку ниже, чтобы открыть каталог софта, читать инструкции и скачивать файлы напрямую в этот чат.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(Command("admin"))
async def admin_cmd(message: types.Message, state: FSMContext):
    await message.answer("📥 **Загрузка софта в каталог.**\n\nОтправь **первый (основной) файл**.")
    await state.set_state(AddItemState.file1)

@dp.message(AddItemState.file1)
async def process_file1(message: types.Message, state: FSMContext):
    file_id = message.document.file_id if message.document else (message.video.file_id if message.video else (message.audio.file_id if message.audio else None))
    if not file_id:
        await message.answer("⚠️ Пожалуйста, отправь документ или файл!")
        return

    await state.update_data(file_id_1=file_id)
    await message.answer("🏷 Напиши название для **первой кнопки** (например: *Скачать APK* или *Основной софт*):")
    await state.set_state(AddItemState.file1_name)

@dp.message(AddItemState.file1_name)
async def process_file1_name(message: types.Message, state: FSMContext):
    await state.update_data(file_name_1=message.text)
    await message.answer("📎 Нужен ли **второй файл** для этой позиции? Напиши `Да` или `-` (нет):")
    await state.set_state(AddItemState.file2_choice)

@dp.message(AddItemState.file2_choice)
async def process_file2_choice(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    if text in ["да", "yes", "+"]:
        await message.answer("📥 Отправь **второй файл**:")
        await state.set_state(AddItemState.file2)
    else:
        await state.update_data(file_id_2=None, file_name_2=None)
        await message.answer("✏️ Введи **Название софта** (например: *Axiom Soft*):")
        await state.set_state(AddItemState.title)

@dp.message(AddItemState.file2)
async def process_file2(message: types.Message, state: FSMContext):
    file_id = message.document.file_id if message.document else (message.video.file_id if message.video else (message.audio.file_id if message.audio else None))
    if not file_id:
        await message.answer("⚠️ Пожалуйста, отправь документ или файл!")
        return

    await state.update_data(file_id_2=file_id)
    await message.answer("🏷 Напиши название для **второй кнопки** (например: *Скачать Кэш / Инжектор*):")
    await state.set_state(AddItemState.file2_name)

@dp.message(AddItemState.file2_name)
async def process_file2_name(message: types.Message, state: FSMContext):
    await state.update_data(file_name_2=message.text)
    await message.answer("✏️ Введи **Название софта** (например: *Axiom Soft*):")
    await state.set_state(AddItemState.title)

@dp.message(AddItemState.title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("📝 Введи **Подзаголовок** (например: *Чит для iOS / PC*):")
    await state.set_state(AddItemState.subtitle)

@dp.message(AddItemState.subtitle)
async def process_subtitle(message: types.Message, state: FSMContext):
    await state.update_data(subtitle=message.text)
    await message.answer("🏷 Введи **Теги** через запятую (например: *iOS, TrollStore, PC*):")
    await state.set_state(AddItemState.tags)

@dp.message(AddItemState.tags)
async def process_tags(message: types.Message, state: FSMContext):
    await state.update_data(tags=message.text)
    await message.answer("📌 Введи **Версию** (например: *v0.39.2*):")
    await state.set_state(AddItemState.version)

@dp.message(AddItemState.version)
async def process_version(message: types.Message, state: FSMContext):
    await state.update_data(version=message.text)
    await message.answer("📖 Введи **Подробное описание / Инструкцию по установке**:")
    await state.set_state(AddItemState.description)

@dp.message(AddItemState.description)
async def process_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("🖼 **Отправь картинку/скриншот** для баннера (или знак `-` если без картинки):")
    await state.set_state(AddItemState.image)

@dp.message(AddItemState.image)
async def process_img(message: types.Message, state: FSMContext):
    image_id = message.photo[-1].file_id if message.photo else None
    if not image_id and message.text and message.text.strip() != "-":
        await message.answer("⚠️ Пожалуйста, отправь именно **картинку** или знак `-`!")
        return

    data = await state.get_data()
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO items (title, subtitle, tags, version, description, image_id, file_id_1, file_name_1, file_id_2, file_name_2)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['title'], data['subtitle'], data['tags'], data['version'], 
        data['description'], image_id, 
        data['file_id_1'], data.get('file_name_1', 'Скачать файл 1'), 
        data.get('file_id_2'), data.get('file_name_2')
    ))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer("✅ **Софт успешно добавлен в каталог Mini App!**")

# --- FASTAPI ПРИЛОЖЕНИЕ & ЭНДПОИНТЫ ---

@app.get("/api/items")
async def get_items():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, subtitle, tags, version, description, image_id, file_name_1, file_id_2, file_name_2 FROM items ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    items = []
    for r in rows:
        item = dict(r)
        item['has_second_file'] = bool(item['file_id_2'])
        if item['image_id']:
            try:
                file_info = await bot.get_file(item['image_id'])
                item['image_url'] = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
            except Exception:
                item['image_url'] = "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=800"
        else:
            item['image_url'] = "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=800"
        items.append(item)
        
    return items

@app.post("/api/download")
async def download_file(data: dict = Body(...)):
    item_id = data.get("id")
    user_id = data.get("user_id")
    file_num = data.get("file_num", 1)

    if not item_id or not user_id:
        raise HTTPException(status_code=400, detail="Missing data")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if file_num == 2:
        cursor.execute("SELECT file_id_2, file_name_2 FROM items WHERE id = ?", (item_id,))
    else:
        cursor.execute("SELECT file_id_1, file_name_1 FROM items WHERE id = ?", (item_id,))
    
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="File not found")

    file_id, file_label = row
    try:
        await bot.send_document(chat_id=user_id, document=file_id, caption=f"📥 **{file_label}**\nУдачной установки!")
        return {"success": True}
    except Exception as e:
        logging.error(f"Error sending file: {e}")
        return {"success": False, "error": str(e)}

# --- FRONTEND ИНТЕРФЕЙС (HTML/CSS/JS) ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>CyberStore Mini App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #090a10; color: #f1f3f9; padding-bottom: 85px; user-select: none; }

        .header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 16px; background: #11131d; border-bottom: 1px solid #1c1f2e;
            position: sticky; top: 0; z-index: 100;
        }
        .brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 18px; color: #a855f7; }
        .brand-icon {
            width: 32px; height: 32px; background: linear-gradient(135deg, #a855f7, #6366f1);
            border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px;
        }
        .header-actions { display: flex; gap: 8px; }
        .icon-btn {
            width: 38px; height: 38px; background: #181b28; border: 1px solid #272c40;
            border-radius: 10px; color: #a0aec0; display: flex; align-items: center; justify-content: center; font-size: 16px;
        }

        .search-container { padding: 14px 16px 6px 16px; display: flex; gap: 8px; }
        .search-box {
            flex: 1; background: #131622; border: 1px solid #22273b; border-radius: 14px;
            padding: 10px 14px; display: flex; align-items: center; gap: 10px; color: #a0aec0;
        }
        .search-input { background: transparent; border: none; color: #fff; outline: none; width: 100%; font-size: 14px; }

        .catalog { padding: 12px 16px; display: flex; flex-direction: column; gap: 18px; }

        .item-card {
            background: #11131f; border-radius: 20px; overflow: hidden;
            border: 1px solid #1f2436; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .banner-container { width: 100%; height: 180px; position: relative; background: #181b28; }
        .banner-img { width: 100%; height: 100%; object-fit: cover; }
        
        .card-body { padding: 16px; }
        .item-title { font-size: 20px; font-weight: 800; color: #fff; margin-bottom: 4px; }
        .item-subtitle { font-size: 13px; color: #8c9bce; margin-bottom: 10px; }

        .tags-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
        .tag-pill {
            background: rgba(168, 85, 247, 0.12); border: 1px solid rgba(168, 85, 247, 0.3);
            color: #c084fc; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 8px;
        }
        .version-pill { background: #181b28; color: #718096; border: 1px solid #272c40; font-size: 11px; padding: 4px 8px; border-radius: 8px; }

        .details-btn {
            background: none; border: none; color: #a0aec0; font-size: 13px; font-weight: 600;
            display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 6px 0; margin-bottom: 10px;
        }
        .details-content {
            display: none; background: #0b0d16; border-radius: 12px; padding: 12px;
            font-size: 12px; color: #a0aec0; line-height: 1.5; margin-bottom: 14px; border: 1px solid #1a1e2e;
        }
        .details-content.open { display: block; }

        /* Контейнер кнопок скачивания */
        .download-group { display: flex; flex-direction: column; gap: 8px; }
        .download-btn {
            width: 100%; background: linear-gradient(135deg, #a855f7, #7c3aed);
            color: #fff; border: none; padding: 12px; border-radius: 14px;
            font-size: 14px; font-weight: 800; display: flex; align-items: center;
            justify-content: center; gap: 8px; cursor: pointer; box-shadow: 0 4px 15px rgba(168, 85, 247, 0.2);
        }
        .download-btn.secondary {
            background: #181b28; border: 1px solid #272c40; color: #a0aec0; box-shadow: none;
        }
        .download-btn:active { transform: scale(0.98); }

        .bottom-nav {
            position: fixed; bottom: 0; left: 0; right: 0;
            background: rgba(17, 19, 31, 0.95); backdrop-filter: blur(12px);
            border-top: 1px solid #1c1f2e; display: flex; justify-content: space-around;
            padding: 12px 0 20px 0; z-index: 1000;
        }
        .nav-link {
            display: flex; flex-direction: column; align-items: center; gap: 4px;
            color: #64748b; font-size: 11px; font-weight: 700; cursor: pointer; width: 45%;
        }
        .nav-link.active { color: #a855f7; }
        .nav-icon { font-size: 20px; }

        /* Модальное окно */
        .modal-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(4, 5, 10, 0.92); backdrop-filter: blur(10px);
            display: flex; align-items: center; justify-content: center;
            z-index: 9999; padding: 20px;
        }
        .modal-card {
            background: #11131f; border: 1px solid #272c40; border-radius: 24px;
            padding: 24px; max-width: 400px; width: 100%; box-shadow: 0 10px 40px rgba(0,0,0,0.8);
        }
        .modal-title { font-size: 20px; font-weight: 800; color: #fff; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
        .modal-body {
            font-size: 13px; color: #94a3b8; line-height: 1.6; margin-bottom: 20px;
            max-height: 220px; overflow-y: auto; padding-right: 6px;
        }
        .modal-body ul { margin-left: 18px; margin-top: 8px; }
        .modal-body li { margin-bottom: 6px; }

        .checkbox-container {
            display: flex; align-items: center; gap: 10px; margin-bottom: 20px;
            font-size: 13px; color: #cbd5e1; cursor: pointer; user-select: none;
        }
        .checkbox-container input { width: 18px; height: 18px; accent-color: #a855f7; cursor: pointer; }

        .accept-btn {
            width: 100%; background: #272c40; color: #64748b; border: none;
            padding: 14px; border-radius: 14px; font-size: 15px; font-weight: 800;
            cursor: not-allowed; transition: all 0.2s ease;
        }
        .accept-btn.active {
            background: linear-gradient(135deg, #a855f7, #7c3aed);
            color: #fff; cursor: pointer; box-shadow: 0 4px 15px rgba(168, 85, 247, 0.4);
        }
    </style>
</head>
<body>

    <div id="disclaimer-modal" class="modal-overlay">
        <div class="modal-card">
            <div class="modal-title">⚠️ Ответственность</div>
            <div class="modal-body">
                Используя данное приложение, вы подтверждаете, что делаете это исключительно на свой страх и риск:
                <ul>
                    <li><b>Личная ответственность:</b> Вы самостоятельно отвечаете за загрузку, установку и последствия использования файлов.</li>
                    <li><b>Принцип «Как есть»:</b> Софт предоставляется без гарантий. Разработчики не несут ответственности за блокировки или сбои устройств.</li>
                    <li><b>Цифровая гигиена:</b> Всегда соблюдайте инструкции по установке.</li>
                </ul>
            </div>
            <label class="checkbox-container">
                <input type="checkbox" id="agree-checkbox" onchange="toggleAcceptBtn()">
                <span>Я согласен и принимаю все риски</span>
            </label>
            <button id="accept-btn" class="accept-btn" disabled onclick="closeDisclaimer()">🚀 Войти в каталог</button>
        </div>
    </div>

    <div class="header">
        <div class="brand">
            <div class="brand-icon">⚡</div>
            <span>CyberStore</span>
        </div>
        <div class="header-actions">
            <div class="icon-btn">👤</div>
            <div class="icon-btn">☰</div>
        </div>
    </div>

    <div class="search-container">
        <div class="search-box">
            <span>🔍</span>
            <input id="search" type="text" class="search-input" placeholder="Поиск по каталогу..." oninput="filterItems()">
        </div>
    </div>

    <div id="catalog" class="catalog">
        <p style="text-align:center; color:#64748b; margin-top:30px;">Загрузка каталога...</p>
    </div>

    <div class="bottom-nav">
        <div class="nav-link active">
            <span class="nav-icon">📁</span>
            <span>Библиотека</span>
        </div>
        <div class="nav-link">
            <span class="nav-icon">👤</span>
            <span>Профиль</span>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        let allItems = [];

        if(localStorage.getItem('disclaimer_accepted') === 'true') {
            document.getElementById('disclaimer-modal').style.display = 'none';
        }

        function toggleAcceptBtn() {
            const checked = document.getElementById('agree-checkbox').checked;
            const btn = document.getElementById('accept-btn');
            if(checked) {
                btn.classList.add('active');
                btn.disabled = false;
            } else {
                btn.classList.remove('active');
                btn.disabled = true;
            }
        }

        function closeDisclaimer() {
            localStorage.setItem('disclaimer_accepted', 'true');
            document.getElementById('disclaimer-modal').style.display = 'none';
            tg.HapticFeedback.notificationOccurred('success');
        }

        async function loadCatalog() {
            try {
                const res = await fetch('/api/items');
                allItems = await res.json();
                renderCatalog(allItems);
            } catch(e) {
                document.getElementById('catalog').innerHTML = '<p style="text-align:center; color:#ef4444;">Ошибка загрузки каталога</p>';
            }
        }

        function renderCatalog(items) {
            const container = document.getElementById('catalog');
            if(items.length === 0) {
                container.innerHTML = '<p style="text-align:center; color:#64748b; margin-top:30px;">Файлов пока нет</p>';
                return;
            }

            container.innerHTML = items.map(item => `
                <div class="item-card">
                    <div class="banner-container">
                        <img class="banner-img" src="${item.image_url}" alt="banner">
                    </div>
                    <div class="card-body">
                        <div class="item-title">${item.title}</div>
                        <div class="item-subtitle">${item.subtitle || ''}</div>

                        <div class="tags-row">
                            ${(item.tags || '').split(',').map(t => `<span class="tag-pill">${t.trim()}</span>`).join('')}
                            ${item.version ? `<span class="version-pill">${item.version}</span>` : ''}
                        </div>

                        <button class="details-btn" onclick="toggleDetails(${item.id})">
                            <span id="arrow-${item.id}">▼</span> Подробнее / Инструкция
                        </button>

                        <div id="desc-${item.id}" class="details-content">
                            ${item.description || 'Описание отсутствует.'}
                        </div>

                        <div class="download-group">
                            <button class="download-btn" onclick="downloadItem(${item.id}, 1)">
                                📥 ${item.file_name_1 || 'Скачать файл'}
                            </button>
                            ${item.has_second_file ? `
                                <button class="download-btn secondary" onclick="downloadItem(${item.id}, 2)">
                                    📦 ${item.file_name_2 || 'Дополнительный файл'}
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function toggleDetails(id) {
            const el = document.getElementById(`desc-${id}`);
            const arrow = document.getElementById(`arrow-${id}`);
            if(el.classList.contains('open')) {
                el.classList.remove('open');
                arrow.innerText = '▼';
            } else {
                el.classList.add('open');
                arrow.innerText = '▲';
            }
        }

        function filterItems() {
            const query = document.getElementById('search').value.toLowerCase();
            const filtered = allItems.filter(i => 
                i.title.toLowerCase().includes(query) || 
                (i.tags && i.tags.toLowerCase().includes(query))
            );
            renderCatalog(filtered);
        }

        async function downloadItem(id, fileNum) {
            const userId = tg.initDataUnsafe?.user?.id;
            if(!userId) {
                tg.showAlert("Запустите приложение внутри Telegram!");
                return;
            }

            tg.HapticFeedback.impactOccurred('medium');
            tg.showAlert("📥 Бот уже отправляет файл вам в личные сообщения!");

            await fetch('/api/download', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: id, user_id: userId, file_num: fileNum })
            });
        }

        loadCatalog();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_CODE

# --- СТАРТ СЕРВЕРА ---
async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
    server = uvicorn.Server(config)
    await asyncio.gather(
        server.serve(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
