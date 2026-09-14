import os
import asyncio
import random
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")
WEBAPP_URL = "https://cs-farm-bot.onrender.com"  # Твой URL на Render

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- ВЕБ-ИНТЕРФЕЙС (MINI APP) ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>CS2 Lounge Mini App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #0c0d10; color: #fff; padding-bottom: 80px; user-select: none; }

        /* Шапка */
        .header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 12px 16px; background: #12141a; border-bottom: 1px solid #1e222d;
            position: sticky; top: 0; z-index: 100;
        }
        .logo { font-size: 16px; font-weight: 800; color: #f3ba2f; display: flex; align-items: center; gap: 6px; }
        .balance-chip {
            background: #1a1d26; border: 1px solid #2d3345; padding: 6px 12px;
            border-radius: 20px; font-weight: 700; font-size: 13px; color: #f3ba2f;
        }
        .user-avatar { width: 32px; height: 32px; border-radius: 50%; border: 1.5px solid #f3ba2f; }

        /* Страницы */
        .page { display: none; padding: 16px; }
        .page.active { display: block; }

        /* Сетка игр */
        .games-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .game-card {
            background: linear-gradient(145deg, #151821, #1a1e2b); border-radius: 14px;
            padding: 14px; border: 1px solid #222634; text-align: center; cursor: pointer;
        }
        .game-card:active { transform: scale(0.98); }
        .game-icon { font-size: 32px; margin-bottom: 6px; }
        .game-title { font-size: 14px; font-weight: 700; }
        .game-desc { font-size: 10px; color: #6c757d; margin-top: 2px; }

        /* Карточки скинов */
        .skin-card {
            background: #161822; border-radius: 10px; padding: 10px; margin-top: 8px;
            display: flex; align-items: center; gap: 10px; border-left: 4px solid #fff;
        }
        .skin-card.covert { border-left-color: #eb4b4b; }
        .skin-card.classified { border-left-color: #d32ce6; }
        .skin-card.restricted { border-left-color: #8847ff; }
        .skin-card.mil-spec { border-left-color: #4b69ff; }
        .skin-img { width: 50px; height: 40px; object-fit: contain; }

        /* Формы и кнопки */
        .input-field {
            width: 100%; padding: 12px; background: #161822; border: 1px solid #232736;
            color: #fff; border-radius: 10px; margin: 8px 0; font-size: 14px;
        }
        .btn {
            width: 100%; background: #f3ba2f; color: #000; border: none; padding: 12px;
            border-radius: 10px; font-weight: 800; font-size: 14px; cursor: pointer; margin-top: 6px;
        }
        .btn-danger { background: #e53935; color: #fff; }

        /* Мины */
        .mines-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin: 12px 0; }
        .mine-cell {
            aspect-ratio: 1; background: #1a1d26; border: 1px solid #2d3345;
            border-radius: 8px; font-size: 20px; display: flex; align-items: center;
            justify-content: center; cursor: pointer;
        }

        /* Нижнее меню */
        .bottom-nav {
            position: fixed; bottom: 0; left: 0; right: 0;
            background: rgba(18, 20, 26, 0.95); backdrop-filter: blur(10px);
            border-top: 1px solid #1e222d; display: flex; justify-content: space-around;
            padding: 10px 0 16px 0; z-index: 1000;
        }
        .nav-item {
            display: flex; flex-direction: column; align-items: center; gap: 2px;
            color: #6c757d; font-size: 10px; font-weight: 600; cursor: pointer; width: 20%;
        }
        .nav-item.active { color: #f3ba2f; }
    </style>
</head>
<body>

    <!-- Шапка -->
    <div class="header">
        <div class="logo">⚡ CS2 LOUNGE</div>
        <div style="display: flex; align-items: center; gap: 8px;">
            <div class="balance-chip">🪙 <span id="coins-val">1000</span></div>
            <img id="user-avatar" class="user-avatar" src="https://ui-avatars.com/api/?name=U&background=1a1d26&color=f3ba2f" alt="avatar">
        </div>
    </div>

    <!-- 1. ГЛАВНАЯ (ИГРЫ) -->
    <div id="page-games" class="page active">
        <div class="games-grid">
            <div class="game-card" onclick="switchPage('cases')">
                <div class="game-icon">📦</div>
                <div class="game-title">Кейсы</div>
                <div class="game-desc">Все категории CS2</div>
            </div>
            <div class="game-card" onclick="switchPage('crash')">
                <div class="game-icon">📈</div>
                <div class="game-title">Краш</div>
                <div class="game-desc">Успей забрать занос</div>
            </div>
            <div class="game-card" onclick="switchPage('mines')">
                <div class="game-icon">💣</div>
                <div class="game-title">Мины</div>
                <div class="game-desc">Не наступи на бомбу</div>
            </div>
            <div class="game-card" onclick="switchPage('upgrader')">
                <div class="game-icon">⚡</div>
                <div class="game-title">Апгрейдер</div>
                <div class="game-desc">Обнови свой скин</div>
            </div>
        </div>
    </div>

    <!-- 2. КЕЙСЫ -->
    <div id="page-cases" class="page">
        <h3>📦 Выберите кейс</h3>
        <div class="games-grid" style="margin-top:10px;">
            <div class="game-card" onclick="openCase('weapon')">
                <div class="game-title">Оружейный</div>
                <div class="game-desc">100 🪙</div>
            </div>
            <div class="game-card" onclick="openCase('knife')">
                <div class="game-title">🗡 Ножевой</div>
                <div class="game-desc">500 🪙</div>
            </div>
        </div>
        <div id="case-result" style="margin-top:15px;"></div>
    </div>

    <!-- 3. КРАШ -->
    <div id="page-crash" class="page" style="text-align:center;">
        <h3>📈 Краш Игра</h3>
        <h1 id="crash-mult" style="font-size:42px; color:#28a745; margin:15px 0;">x1.00</h1>
        <button id="crash-btn" class="btn" onclick="handleCrash()">Ставка (50 🪙)</button>
    </div>

    <!-- 4. МИНЫ -->
    <div id="page-mines" class="page">
        <h3>💣 Игра Мины</h3>
        <p style="font-size:12px; color:#6c757d;">Открывайте ячейки и забирайте занос!</p>
        <div class="mines-grid" id="mines-grid"></div>
        <button class="btn" onclick="initMines()">Новая игра (50 🪙)</button>
    </div>

    <!-- 5. ДОНАТ / ПРОМО -->
    <div id="page-donate" class="page">
        <h3>💎 Пополнение & Промокоды</h3>
        <input id="promo-code" type="text" placeholder="Введите промокод" class="input-field">
        <button class="btn" onclick="usePromo()">Активировать промокод</button>
        <hr style="border-color:#222634; margin:15px 0;">
        <button class="btn" style="background:#28a745; color:#fff;" onclick="tg.showAlert('Для доната напишите создателю бота!')">💎 Пополнить баланс</button>
    </div>

    <!-- 6. ПРОФИЛЬ / ИНВЕНТАРЬ -->
    <div id="page-profile" class="page">
        <h3>🎒 Мой Инвентарь</h3>
        <div id="inv-list"><p style="color:#6c757d; margin-top:10px;">Инвентарь пуст.</p></div>
    </div>

    <!-- Нижнее меню -->
    <div class="bottom-nav">
        <div class="nav-item active" onclick="switchNav('games', this)"><span>🎮</span><span>Игры</span></div>
        <div class="nav-item" onclick="switchNav('donate', this)"><span>💎</span><span>Донат</span></div>
        <div class="nav-item" onclick="switchNav('profile', this)"><span>🎒</span><span>Скины</span></div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        let coins = 1000;
        let inventory = [];

        if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
            const u = tg.initDataUnsafe.user;
            if (u.photo_url) document.getElementById('user-avatar').src = u.photo_url;
        }

        function updateUI() { document.getElementById('coins-val').innerText = coins; }

        function switchPage(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById('page-' + pageId).classList.add('active');
        }

        function switchNav(pageId, el) {
            switchPage(pageId);
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            el.classList.add('active');
        }

        // Шансы и Скины
        const skinsDB = [
            { name: "AWP | Dragon Lore", type: "covert", price: 3000, chance: 0.02, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZFCb4d11VJ8x45bf4-te358X54iXdd83Hdd434g184451R42f46_n36f_45_282f9" },
            { name: "AK-47 | Neon Rider", type: "classified", price: 800, chance: 0.10, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZFCb4d11VJ8x45bf4-te358X5cI3Bf71Hdd434g184451R42f46_n36f_45_282f9" },
            { name: "M4A4 | Evil Daimyo", type: "restricted", price: 200, chance: 0.30, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZFCb4d11VJ8x45bf4-te358X54d434g184451R42f46_n36f_45_282f9" },
            { name: "USP-S | Lead Conduit", type: "mil-spec", price: 50, chance: 0.58, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZFCb4d11VJ8x45bf4-te358X54d321g184451R42f46_n36f_45_282f9" }
        ];

        function openCase(type) {
            const cost = type === 'knife' ? 500 : 100;
            if (coins < cost) { tg.showAlert("Не хватает монет!"); return; }
            coins -= cost;
            updateUI();

            const rand = Math.random();
            let cumulative = 0;
            let drop = skinsDB[skinsDB.length - 1];

            for (let item of skinsDB) {
                cumulative += item.chance;
                if (rand <= cumulative) { drop = item; break; }
            }

            inventory.push(drop);
            document.getElementById('case-result').innerHTML = `
                <div class="skin-card ${drop.type}">
                    <img class="skin-img" src="${drop.img}">
                    <div><div><b>${drop.name}</b></div><div style="color:#f3ba2f;">${drop.price} 🪙</div></div>
                </div>
            `;
            renderInv();
        }

        function renderInv() {
            const list = document.getElementById('inv-list');
            if (inventory.length === 0) return;
            list.innerHTML = "";
            inventory.forEach(item => {
                list.innerHTML += `
                    <div class="skin-card ${item.type}">
                        <img class="skin-img" src="${item.img}">
                        <div><div><b>${item.name}</b></div><div style="color:#f3ba2f;">${item.price} 🪙</div></div>
                    </div>
                `;
            });
        }

        // Мины
        function initMines() {
            if (coins < 50) { tg.showAlert("Не хватает монет!"); return; }
            coins -= 50; updateUI();
            const grid = document.getElementById('mines-grid');
            grid.innerHTML = "";
            const bombIndex = Math.floor(Math.random() * 25);
            for(let i=0; i<25; i++) {
                const cell = document.createElement('div');
                cell.className = 'mine-cell';
                cell.onclick = () => {
                    if (i === bombIndex) {
                        cell.innerText = "💥"; cell.style.background = "#e53935";
                        tg.showAlert("БУМ! Вы подорвались!");
                    } else {
                        cell.innerText = "💎"; cell.style.background = "#28a745";
                        coins += 20; updateUI();
                    }
                };
                grid.appendChild(cell);
            }
        }

        function usePromo() {
            const code = document.getElementById('promo-code').value.trim();
            if (code.toLowerCase() === 'start') {
                coins += 500; updateUI();
                tg.showAlert("Промокод активирован! +500 монет!");
            } else {
                tg.showAlert("Неверный промокод!");
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_CODE

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🎮 Открыть CS2 Lounge Mini App", 
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])
    await message.answer(
        "👋 **Добро пожаловать в CS2 Lounge!**\n\n"
        "🎮 Нажимай кнопку ниже, чтобы запустить Mini App:\n"
        "• Открывай кейсы с реальными шансами\n"
        "• Играй в Краш, Мины и Апгрейдер\n"
        "• Активируй промокоды и забирай заносы!",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    await message.answer("🏆 **Топ-5 игроков сезона:**\n1. Clean#смешарик — 15,400 🪙\n2. Alex — 12,100 🪙\n3. CS_GOAT — 9,800 🪙\n4. Trader99 — 8,500 🪙\n5. DragonKing — 7,200 🪙")

@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer("ℹ️ **Помощь:**\nИспользуй команду /start или нажимай синюю кнопку «Играть» в меню, чтобы открыть приложение.")

# --- ЗАПУСК И БОТА, И ВЕБ-СЕРВЕРА ---
async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
    server = uvicorn.Server(config)
    await asyncio.gather(
        server.serve(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
