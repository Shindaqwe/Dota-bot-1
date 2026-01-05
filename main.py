import os
import asyncio
import aiohttp
import random
import json
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import storage
from keep_alive import keep_alive
from collections import Counter

# ========== НАСТРОЙКА ДЛЯ RAILWAY ==========
# Railway требует специальной настройки вебхуков или long-polling
# Эта версия совместима с Railway

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")

# Критические проверки
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    logger.error("Добавьте BOT_TOKEN в Environment Variables на Railway")
    logger.error("Или создайте файл .env с BOT_TOKEN=ваш_токен")
    exit(1)

# Инициализация бота для Railway
# ВАЖНО: Используем long-polling, а не webhook для Railway
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

# Инициализация БД
try:
    storage.init_db()
    logger.info("✅ База данных инициализирована")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации БД: {e}")
    # Продолжаем без БД, если это возможно

# ========== КОНФИГУРАЦИЯ ==========
RANK_TIER_MMR = {
    11: 10, 12: 160, 13: 310, 14: 460, 15: 610,
    21: 760, 22: 910, 23: 1060, 24: 1210, 25: 1360,
    31: 1510, 32: 1660, 33: 1810, 34: 1960, 35: 2110,
    41: 2260, 42: 2410, 43: 2560, 44: 2710, 45: 2860,
    51: 3010, 52: 3160, 53: 3310, 54: 3460, 55: 3610,
    61: 3760, 62: 3910, 63: 4060, 64: 4210, 65: 4360,
    71: 4510, 72: 4660, 73: 4810, 74: 4960, 75: 5110,
    80: 6000
}

# ========== КЕШИ ==========
HEROES_CACHE = {}
ITEMS_CACHE = {}

# ========== СОСТОЯНИЯ FSM ==========
class ProfileStates(StatesGroup):
    waiting_steam_url = State()
    waiting_friend_url = State()

class QuizStates(StatesGroup):
    waiting_answer = State()

# ========== УТИЛИТЫ ==========
def steam64_to_account_id(steam64: int) -> int:
    return steam64 - 76561197960265728

async def extract_account_id_safe(steam_url: str):
    try:
        steam_url = steam_url.strip().rstrip("/")
        
        if "/profiles/" in steam_url:
            steam64 = int(steam_url.split("/")[-1])
            return steam64_to_account_id(steam64)
        
        elif "/id/" in steam_url:
            if not STEAM_API_KEY:
                return None
            vanity = steam_url.split("/")[-1]
            async with aiohttp.ClientSession() as session:
                url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key={STEAM_API_KEY}&vanityurl={vanity}"
                async with session.get(url, timeout=10) as r:
                    data = await r.json()
                    if data.get("response", {}).get("success") == 1:
                        steam64 = int(data["response"]["steamid"])
                        return steam64_to_account_id(steam64)
        
        elif steam_url.isdigit():
            num = int(steam_url)
            if num > 76561197960265728:
                return steam64_to_account_id(num)
            return num
        
        return None
    except Exception as e:
        logger.error(f"Ошибка извлечения account_id: {e}")
        return None

async def get_player_data(account_id: int):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.opendota.com/api/players/{account_id}",
                timeout=10
            ) as r:
                if r.status == 200:
                    return await r.json()
                return None
    except Exception as e:
        logger.error(f"Ошибка получения данных игрока: {e}")
        return None

async def get_recent_matches(account_id: int, limit=20):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.opendota.com/api/players/{account_id}/recentMatches",
                timeout=15
            ) as r:
                if r.status == 200:
                    matches = await r.json()
                    return matches[:limit] if isinstance(matches, list) else []
                return []
    except Exception as e:
        logger.error(f"Ошибка получения матчей: {e}")
        return []

async def get_heroes_data():
    global HEROES_CACHE
    if HEROES_CACHE:
        return HEROES_CACHE
    
    try:
        with open('hero_names.json', 'r', encoding='utf-8') as f:
            HEROES_CACHE = json.load(f)
            HEROES_CACHE = {int(k): v for k, v in HEROES_CACHE.items()}
            return HEROES_CACHE
    except:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.opendota.com/api/constants/heroes",
                    timeout=15
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        HEROES_CACHE = {int(k): v['localized_name'] for k, v in data.items()}
                        return HEROES_CACHE
        except:
            return {}

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    buttons = [
        "👤 Профиль", "📊 Анализ", "🎮 Викторина",
        "👥 Друзья", "🏆 Топ игроков", "ℹ️ Помощь"
    ]
    for btn in buttons:
        builder.button(text=btn)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(Command("start"))
async def start_command(message: types.Message):
    welcome_text = (
        "🎮 <b>Добро пожаловать в DotaStats Bot!</b>\n\n"
        "Отправьте ссылку на Steam профиль для привязки:\n"
        "• https://steamcommunity.com/profiles/76561198...\n"
        "• https://steamcommunity.com/id/ваш_ник\n\n"
        "Или используйте команду /bind"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command("bind"))
async def bind_command(message: types.Message, state: FSMContext):
    args = message.text.split()
    if len(args) > 1:
        steam_url = ' '.join(args[1:])
        await process_steam_url(message, steam_url)
    else:
        await message.answer("🔗 Отправьте ссылку на Steam профиль:")
        await state.set_state(ProfileStates.waiting_steam_url)

@dp.message(ProfileStates.waiting_steam_url)
async def process_steam_link(message: types.Message, state: FSMContext):
    await process_steam_url(message, message.text)
    await state.clear()

async def process_steam_url(message: types.Message, steam_url: str):
    try:
        account_id = await extract_account_id_safe(steam_url)
        if not account_id:
            await message.answer("❌ Не удалось распознать профиль.")
            return
        
        player_data = await get_player_data(account_id)
        if not player_data:
            await message.answer("❌ Не удалось получить данные.")
            return
        
        profile_name = player_data.get('profile', {}).get('personaname', 'Игрок')
        storage.bind_user(message.from_user.id, account_id)
        
        await message.answer(
            f"✅ Профиль привязан!\n"
            f"👤 Игрок: {profile_name}\n"
            f"🆔 Account ID: {account_id}",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка привязки: {e}")
        await message.answer("❌ Ошибка при привязке профиля.")

@dp.message(F.text == "👤 Профиль")
async def profile_command(message: types.Message):
    account_id = storage.get_account_id(message.from_user.id)
    if not account_id:
        await message.answer("❌ Профиль не привязан. Используйте /bind")
        return
    
    player_data = await get_player_data(account_id)
    if not player_data:
        await message.answer("❌ Не удалось получить данные профиля.")
        return
    
    profile = player_data.get('profile', {})
    profile_name = profile.get('personaname', 'Неизвестно')
    mmr = player_data.get('mmr_estimate', {}).get('estimate', 'Неизвестно')
    
    matches = await get_recent_matches(account_id, 5)
    matches_text = ""
    if matches:
        heroes = await get_heroes_data()
        for m in matches[:3]:
            hero_id = m.get('hero_id', 0)
            hero_name = heroes.get(hero_id, f"Герой {hero_id}")
            k, d, a = m.get('kills', 0), m.get('deaths', 0), m.get('assists', 0)
            win = ((m['player_slot'] < 128) == m.get('radiant_win', False))
            outcome = "✅" if win else "❌"
            matches_text += f"{outcome} {hero_name}: {k}/{d}/{a}\n"
    
    response = (
        f"👤 <b>{profile_name}</b>\n"
        f"🎯 MMR: {mmr}\n\n"
        f"<b>Последние игры:</b>\n{matches_text}"
    )
    await message.answer(response, parse_mode="HTML")

@dp.message(F.text == "📊 Анализ")
async def analyze_command(message: types.Message):
    account_id = storage.get_account_id(message.from_user.id)
    if not account_id:
        await message.answer("❌ Сначала привяжите профиль.")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.opendota.com/api/players/{account_id}/benchmarks",
                timeout=15
            ) as r:
                if r.status == 200:
                    bench = await r.json()
                    response = "📊 <b>Анализ производительности:</b>\n\n"
                    
                    metrics = {
                        'gold_per_min': '💰 GPM',
                        'xp_per_min': '📈 XPM',
                        'hero_damage_per_min': '💥 Урон',
                        'kills_per_min': '⚔️ Убийств'
                    }
                    
                    for key, label in metrics.items():
                        if key in bench and bench[key]:
                            percentile = bench[key][-1].get('percentile', 0)
                            value = bench[key][-1].get('value', 0)
                            response += f"{label}: {value:.1f} (лучше чем {percentile*100:.1f}% игроков)\n"
                    
                    await message.answer(response, parse_mode="HTML")
                else:
                    await message.answer("❌ Нет данных для анализа.")
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        await message.answer("❌ Ошибка при анализе.")

# ========== ВИКТОРИНА ==========
QUIZ_QUESTIONS = [
    {"q": "Какой герой имеет ультимейт 'Black Hole'?", "a": "Enigma", "o": ["Enigma", "Magnus", "Void", "Tide"]},
    {"q": "Какой предмет дает невидимость?", "a": "Shadow Blade", "o": ["BKB", "Manta", "Shadow Blade", "Blink"]},
    {"q": "Кто является боссом на реке?", "a": "Roshan", "o": ["Roshan", "Tormentor", "Ancient", "Courier"]},
]

@dp.message(F.text == "🎮 Викторина")
async def quiz_command(message: types.Message):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🎯 Начать", callback_data="quiz_start")
    keyboard.button(text="🏆 Лидеры", callback_data="quiz_leaderboard")
    
    await message.answer(
        "🎮 <b>Викторина по Dota 2</b>\n\n"
        "Проверьте свои знания!",
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(F.data == "quiz_start")
async def quiz_start_callback(callback: types.CallbackQuery):
    question = random.choice(QUIZ_QUESTIONS)
    keyboard = InlineKeyboardBuilder()
    
    for option in question['o']:
        is_correct = option == question['a']
        keyboard.button(text=option, callback_data=f"quiz_answer_{'correct' if is_correct else 'wrong'}")
    
    keyboard.adjust(2)
    await callback.message.edit_text(
        f"❓ {question['q']}",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(F.data.startswith("quiz_answer_"))
async def quiz_answer_callback(callback: types.CallbackQuery):
    answer_type = callback.data.split("_")[-1]
    
    if answer_type == "correct":
        storage.update_score(callback.from_user.id, 10)
        await callback.message.edit_text("✅ Правильно! +10 очков")
    else:
        await callback.message.edit_text("❌ Неправильно!")
    
    await callback.answer()

@dp.callback_query(F.data == "quiz_leaderboard")
async def quiz_leaderboard_callback(callback: types.CallbackQuery):
    leaders = storage.get_leaderboard(5)
    response = "🏆 <b>Топ игроков:</b>\n\n"
    
    for i, leader in enumerate(leaders, 1):
        response += f"{i}. ID {leader['telegram_id']}: {leader['score']} очков\n"
    
    await callback.message.edit_text(response, parse_mode="HTML")

# ========== ДРУГИЕ КОМАНДЫ ==========
@dp.message(F.text == "👥 Друзья")
async def friends_command(message: types.Message):
    friends = storage.get_friends(message.from_user.id)
    if not friends:
        await message.answer("У вас нет друзей. Добавьте командой:\n`/addfriend ссылка_на_стим`")
        return
    
    response = "👥 <b>Ваши друзья:</b>\n\n"
    for friend in friends:
        response += f"• {friend['friend_name']} (ID: {friend['friend_account_id']})\n"
    
    await message.answer(response, parse_mode="HTML")

@dp.message(Command("addfriend"))
async def addfriend_command(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: `/addfriend ссылка_на_стим`")
        return
    
    account_id = await extract_account_id_safe(args[1])
    if not account_id:
        await message.answer("❌ Неверная ссылка.")
        return
    
    player_data = await get_player_data(account_id)
    if not player_data:
        await message.answer("❌ Не удалось получить данные друга.")
        return
    
    name = player_data.get('profile', {}).get('personaname', 'Друг')
    storage.add_friend(message.from_user.id, account_id, name)
    await message.answer(f"✅ Друг {name} добавлен!")

@dp.message(F.text == "🏆 Топ игроков")
async def leaderboard_command(message: types.Message):
    leaders = storage.get_leaderboard(10)
    response = "🏆 <b>Топ игроков бота:</b>\n\n"
    
    for i, leader in enumerate(leaders, 1):
        response += f"{i}. ID {leader['telegram_id']}: {leader['score']} очков\n"
    
    await message.answer(response, parse_mode="HTML")

@dp.message(F.text == "ℹ️ Помощь")
async def help_command(message: types.Message):
    help_text = (
        "🆘 <b>Помощь:</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Начало работы\n"
        "/bind - Привязать Steam профиль\n"
        "/profile - Ваш профиль\n"
        "/analyze - Анализ статистики\n"
        "/addfriend - Добавить друга\n"
        "\n<b>Или используйте кнопки меню!</b>"
    )
    await message.answer(help_text, parse_mode="HTML")

@dp.message()
async def handle_steam_url(message: types.Message):
    """Обработка Steam ссылок напрямую"""
    text = message.text.strip()
    if "steamcommunity.com" in text:
        await process_steam_url(message, text)
    else:
        await message.answer("Используйте кнопки меню или отправьте ссылку на Steam профиль.")

# ========== ЗАПУСК БОТА ДЛЯ RAILWAY ==========
async def main():
    """Главная функция для Railway"""
    logger.info("🚀 Запуск бота на Railway...")
    
    # Запускаем keep-alive сервер
    keep_alive()
    logger.info("✅ Keep-alive сервер запущен")
    
    # Запускаем long-polling бота
    try:
        # На Railway нужно использовать long-polling
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook удален, используем long-polling")
        
        logger.info("🤖 Бот запущен и ожидает сообщений...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        raise

# ========== ТОЧКА ВХОДА ==========
if __name__ == "__main__":
    # Проверяем что мы на Railway (порт назначен)
    port = os.environ.get('PORT')
    if port:
        logger.info(f"🚂 Обнаружен Railway, порт: {port}")
    
    # Запускаем asyncio loop
    asyncio.run(main())