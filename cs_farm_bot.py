import os
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА") # Возьмет токен из Render
WEBAPP_URL = "https://cs-farm-bot.onrender.com"  # Твой URL на Render

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- 1. ВЕБ-СЕРВЕР И MINI APP (ФРОНТЕНД) ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>CS2 CSGO Mini App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', system-ui, sans-serif; }
        body { background: #0f1115; color: #e1e1e6; padding: 12px; }

        /* Шапка профиля */
        .profile-card {
            background: linear-gradient(135deg, #181a20, #222630);
            border-radius: 16px;
            padding: 12px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border: 1px solid #2d323f;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            margin-bottom: 12px;
        }
        .user-info { display: flex; align-items: center; gap: 10px; }
        .avatar { width: 42px; height: 42px; border-radius: 50%; border: 2px solid #ffb703; background: #2a2e3d; }
        .user-name { font-weight: 700; font-size: 15px; color: #fff; }
        .balance-badge {
            background: rgba(255, 183, 3, 0.1);
            border: 1px solid #ffb703;
            color: #ffb703;
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 800;
            font-size: 14px;
        }

        /* Навигация */
        .nav-bar { display: flex; gap: 6px; margin-bottom: 12px; }
        .tab-btn {
            flex: 1; padding: 10px 4px; background: #181a20; border: 1px solid #282c37;
            color: #8b92a5; border-radius: 10px; font-weight: 600; font-size: 12px; cursor: pointer;
        }
        .tab-btn.active { background: #2563eb; color: #fff; border-color: #3b82f6; }

        /* Игровые карточки */
        .card { background: #181a20; border-radius: 16px; padding: 16px; border: 1px solid #242834; display: none; }
        .card.active { display: block; }

        .btn {
            width: 100%; background: #16a34a; color: white; border: none; padding: 14px;
            border-radius: 12px; font-size: 15px; font-weight: 700; cursor: pointer; margin-top: 10px;
        }
        .btn:active { transform: scale(0.98); }
        .btn-danger { background: #dc2626; }

        /* Скины и кейсы */
        .skin-card {
            background: #111318; border-radius: 12px; padding: 10px; margin-top: 10px;
            border-left: 4px solid #3b82f6; display: flex; align-items: center; gap: 12px;
        }
        .skin-card.covert { border-left-color: #eb4b4b; } /* Тайное */
        .skin-card.classified { border-left-color: #d32ce6; } /* Засекреченное */
        .skin-img { width: 64px; height: 48px; object-fit: contain; }
        .skin-title { font-weight: 600; font-size: 13px; }
        .skin-price { color: #ffb703; font-size: 12px; font-weight: 700; }

        /* Краш */
        .crash-box { text-align: center; padding: 20px 0; }
        .crash-mult { font-size: 48px; font-weight: 900; color: #22c55e; margin: 10px 0; }
    </style>
</head>
<body>

    <!-- Шапка Профиля -->
    <div class="profile-card">
        <div class="user-info">
            <img id="user-avatar" class="avatar" src="https://ui-avatars.com/api/?name=User&background=2d323f&color=fff" alt="Avatar">
            <div>
                <div id="user-name" class="user-name">Игрок</div>
                <div style="font-size: 11px; color: #6b7280;">CS2 Inventory</div>
            </div>
        </div>
        <div class="balance-badge">🪙 <span id="coins-val">1000</span></div>
    </div>

    <!-- Навигация -->
    <div class="nav-bar">
        <button class="tab-btn active" onclick="switchTab('cases', this)">📦 Кейсы</button>
        <button class="tab-btn" onclick="switchTab('crash', this)">📈 Краш</button>
        <button class="tab-btn" onclick="switchTab('trade', this)">🔄 Трейд</button>
        <button class="tab-btn" onclick="switchTab('inv', this)">🎒 Скины</button>
    </div>

    <!-- 1. КЕЙСЫ -->
    <div id="cases" class="card active">
        <h3 style="text-align:center;">📦 Киберспортивный Кейс</h3>
        <p style="text-align:center; color:#6b7280; font-size:12px; margin-top:4px;">Стоимость: 100 монет</p>
        
        <div id="case-drop-display" style="min-height: 90px;"></div>
        
        <button class="btn" onclick="openCase()">Открыть за 100 🪙</button>
    </div>

    <!-- 2. КРАШ ИГРА -->
    <div id="crash" class="card">
        <div class="crash-box">
            <div style="color: #6b7280; font-size: 12px;">МНОЖИТЕЛЬ</div>
            <div id="crash-mult" class="crash-mult">x1.00</div>
            <p id="crash-status" style="font-size: 12px; color: #8b92a5;">Сделайте ставку 50 монет</p>
        </div>
        <button id="crash-btn" class="btn" onclick="handleCrashBtn()">Ставка (50 🪙)</button>
    </div>

    <!-- 3. ТРЕЙД -->
    <div id="trade" class="card">
        <h3>🔄 P2P Передача предметов</h3>
        <p style="color:#6b7280; font-size:12px; margin: 6px 0 12px 0;">Отправка монет или предметов по Telegram ID</p>
        <input id="trade-user" type="text" placeholder="ID получателя" style="width:100%; padding:12px; background:#111318; border:1px solid #282c37; color:#fff; border-radius:10px; margin-bottom:10px;">
        <button class="btn" onclick="sendTrade()">Передать</button>
    </div>

    <!-- 4. ИНВЕНТАРЬ -->
    <div id="inv" class="card">
        <h3>🎒 Мои предметы</h3>
        <div id="inv-list">
            <p style="color:#6b7280; text-align:center; margin-top:20px; font-size:13px;">Инвентарь пуст</p>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        let coins = 1000;
        let inventory = [];
        let crashState = "idle"; // idle, running
        let crashTimer = null;
        let currentMult = 1.00;
        let crashPoint = 1.00;

        // Данные пользователя из Telegram
        if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
            const user = tg.initDataUnsafe.user;
            document.getElementById('user-name').innerText = user.first_name;
            if (user.photo_url) {
                document.getElementById('user-avatar').src = user.photo_url;
            }
        }

        function updateUI() {
            document.getElementById('coins-val').innerText = coins;
        }

        function switchTab(tabId, btn) {
            document.querySelectorAll('.card').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
        }

        // База скинов с картинками
        const skins = [
            { name: "AWP | Dragon Lore", type: "covert", price: 3500, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZFCb4d11VJ8x45bf4-te358X54iXdd83Hdd434g184451R42f46_n36f_45_282f9" },
            { name: "AK-47 | Neon Rider", type: "covert", price: 1200, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZFCb4d11VJ8x45bf4-te358X5cI3Bf71Hdd434g184451R42f46_n36f_45_282f9" },
            { name: "M4A4 | Evil Daimyo", type: "classified", price: 300, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZFCb4d11VJ8x45bf4-te358X54d434g184451R42f46_n36f_45_282f9" },
            { name: "USP-S | Lead Conduit", type: "spec", price: 80, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZFCb4d11VJ8x45bf4-te358X54d321g184451R42f46_n36f_45_282f9" }
        ];

        function openCase() {
            if (coins < 100) { tg.showAlert("Недостаточно монет!"); return; }
            coins -= 100;
            updateUI();

            const drop = skins[Math.floor(Math.random() * skins.length)];
            inventory.push(drop);

            const display = document.getElementById('case-drop-display');
            display.innerHTML = `
                <div class="skin-card ${drop.type}">
                    <img class="skin-img" src="${drop.img}" alt="skin">
                    <div>
                        <div class="skin-title">${drop.name}</div>
                        <div class="skin-price">Стоимость: ${drop.price} 🪙</div>
                    </div>
                </div>
            `;
            renderInventory();
        }

        // Логика Краша
        function handleCrashBtn() {
            const btn = document.getElementById('crash-btn');
            const multEl = document.getElementById('crash-mult');
            const statusEl = document.getElementById('crash-status');

            if (crashState === "idle") {
                if (coins < 50) { tg.showAlert("Нужно минимум 50 монет!"); return; }
                coins -= 50;
                updateUI();

                crashState = "running";
                currentMult = 1.00;
                crashPoint = (Math.random() * 2.5 + 1.05).toFixed(2);

                btn.innerText = "Забрать занос!";
                btn.className = "btn btn-danger";
                multEl.style.color = "#22c55e";

                crashTimer = setInterval(() => {
                    currentMult += 0.03;
                    multEl.innerText = 'x' + currentMult.toFixed(2);

                    if (currentMult >= crashPoint) {
                        clearInterval(crashTimer);
                        crashState = "idle";
                        multEl.style.color = "#ef4444";
                        multEl.innerText = "КРАШ x" + crashPoint;
                        statusEl.innerText = "Вы сгорели!";
                        btn.innerText = "Ставка (50 🪙)";
                        btn.className = "btn";
                    }
                }, 100);

            } else if (crashState === "running") {
                clearInterval(crashTimer);
                crashState = "idle";
                const winAmount = Math.floor(50 * currentMult);
                coins += winAmount;
                updateUI();

                multEl.style.color = "#3b82f6";
                statusEl.innerText = `Вы забрали ${winAmount} монет!`;
                btn.innerText = "Ставка (50 🪙)";
                btn.className = "btn";
            }
        }

        function renderInventory() {
            const list = document.getElementById('inv-list');
            if (inventory.length === 0) return;
            list.innerHTML = "";
            inventory.forEach(item => {
                list.innerHTML += `
                    <div class="skin-card ${item.type}">
                        <img class="skin-img" src="${item.img}" alt="skin">
                        <div>
                            <div class="skin-title">${item.name}</div>
                            <div class="skin-price">${item.price} 🪙</div>
                        </div>
                    </div>
                `;
            });
        }

        function sendTrade() {
            const recipient = document.getElementById('trade-user').value;
            if (!recipient) { tg.showAlert("Введите ID получателя!"); return; }
            tg.showAlert(`Запрос на передачу пользователю ${recipient} отправлен!`);
        }
    </script>
</body>
</html>
"""

# Должно стать:
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_CODE

# --- 2. ЛОГИКА ТЕЛЕГРАМ БОТА ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🎮 Открыть Mini App (Казино)", 
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])
    await message.answer(
        "Привет! Нажми кнопку ниже, чтобы запустить Mini App со всеми играми, кейсами и трейдами! 🚀", 
        reply_markup=kb
    )

# --- 3. ЗАПУСК ВСЕГО ВМЕСТЕ ---
async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
    server = uvicorn.Server(config)
    
    # Запускаем сервер и бота одновременно
    await asyncio.gather(
        server.serve(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
