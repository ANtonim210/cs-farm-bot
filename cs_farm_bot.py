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
    <title>CS CSGO Casino Mini App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }
        body { background: #121318; color: white; padding: 15px; text-align: center; }
        .card { background: #1c1e24; border-radius: 12px; padding: 15px; margin-bottom: 15px; border: 1px solid #2a2d37; }
        .balance { font-size: 22px; color: #ffb703; font-weight: bold; margin-top: 5px; }
        .nav { display: flex; gap: 8px; margin-bottom: 15px; }
        .tab-btn { flex: 1; padding: 10px; background: #22252e; border: none; color: #8a8f9d; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .tab-btn.active { background: #007bff; color: white; }
        .section { display: none; }
        .section.active { display: block; }
        .btn { width: 100%; background: #28a745; color: white; border: none; padding: 12px; border-radius: 8px; font-size: 16px; font-weight: bold; margin-top: 10px; cursor: pointer; }
        .btn-orange { background: #fd7e14; }
        .item-card { background: #22252e; border-radius: 8px; padding: 10px; margin: 8px 0; display: flex; justify-content: space-between; align-items: center; }
        .item-name { font-weight: bold; }
        .item-price { color: #ffb703; }
    </style>
</head>
<body>

    <div class="card">
        <h3 id="user-name">👤 Игрок</h3>
        <div class="balance">🪙 <span id="coins-val">1000</span> Монет</div>
    </div>

    <!-- Вкладки режимов -->
    <div class="nav">
        <button class="tab-btn active" onclick="switchTab('cases')">📦 Кейсы</button>
        <button class="tab-btn" onclick="switchTab('crash')">📈 Краш</button>
        <button class="tab-btn" onclick="switchTab('trade')">🔄 Трейд</button>
        <button class="tab-btn" onclick="switchTab('inv')">🎒 Инвентарь</button>
    </div>

    <!-- 1. КЕЙСЫ -->
    <div id="cases" class="section active card">
        <h4>📦 Тайный Кейс</h4>
        <p style="color:#8a8f9d; margin: 5px 0;">Цена открытия: 100 монет</p>
        <button class="btn" onclick="openCase()">Открыть за 100 🪙</button>
        <div id="case-result" style="margin-top: 15px; font-weight: bold;"></div>
    </div>

    <!-- 2. КРАШ ИГРА -->
    <div id="crash" class="section card">
        <h4>📈 Режим Crash</h4>
        <h1 id="crash-mult" style="font-size: 40px; color: #28a745; margin: 15px 0;">x1.00</h1>
        <button class="btn btn-orange" onclick="startCrash()">Сделать ставку (50 🪙)</button>
    </div>

    <!-- 3. ТРЕЙДИУМ / ПЕРЕДАЧА -->
    <div id="trade" class="section card">
        <h4>🔄 Передача монет/скинов</h4>
        <input id="trade-user" type="text" placeholder="ID игрока" style="width:100%; padding:10px; margin:10px 0; border-radius:6px; border:none;">
        <button class="btn" onclick="sendTrade()">Отправить подарок</button>
    </div>

    <!-- 4. ИНВЕНТАРЬ -->
    <div id="inv" class="section card">
        <h4>🎒 Мои Скины</h4>
        <div id="inv-list" style="margin-top:10px;">
            <p style="color:#8a8f9d;">Инвентарь пуст. Открой кейс!</p>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        let coins = 1000;
        let inventory = [];

        if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
            document.getElementById('user-name').innerText = '👤 ' + tg.initDataUnsafe.user.first_name;
        }

        function updateUI() {
            document.getElementById('coins-val').innerText = coins;
        }

        function switchTab(tabId) {
            document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }

        // Логика Кейсов
        const skins = [
            { name: "🔴 AWP | История о драконе", price: 5000 },
            { name: "🟣 AK-47 | Неоновый гонщик", price: 800 },
            { name: "🔵 M4A4 | Злобный даймё", price: 200 },
            { name: "⚪ USP-S | Проводник", price: 50 }
        ];

        function openCase() {
            if (coins < 100) { tg.showAlert("Не хватает монет!"); return; }
            coins -= 100;
            const drop = skins[Math.floor(Math.random() * skins.length)];
            inventory.push(drop);
            document.getElementById('case-result').innerText = "Выбили: " + drop.name;
            renderInventory();
            updateUI();
        }

        // Логика Краша
        function startCrash() {
            if (coins < 50) { tg.showAlert("Не хватает монет!"); return; }
            coins -= 50;
            updateUI();
            let mult = 1.0;
            const multEl = document.getElementById('crash-mult');
            const crashPoint = (Math.random() * 3 + 1).toFixed(2);
            
            let timer = setInterval(() => {
                mult += 0.05;
                multEl.innerText = 'x' + mult.toFixed(2);
                if (mult >= crashPoint) {
                    clearInterval(timer);
                    multEl.style.color = '#dc3545';
                    multEl.innerText = '💥 КРАШ на x' + crashPoint;
                    setTimeout(() => { multEl.style.color = '#28a745'; }, 2000);
                }
            }, 100);
        }

        function renderInventory() {
            const list = document.getElementById('inv-list');
            if (inventory.length === 0) return;
            list.innerHTML = "";
            inventory.forEach(item => {
                list.innerHTML += `<div class="item-card"><span class="item-name">${item.name}</span><span class="item-price">${item.price} 🪙</span></div>`;
            });
        }

        function sendTrade() {
            tg.showAlert("Запрос на перевод отправлен!");
        }
    </script>
</body>
</html>
"""

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
