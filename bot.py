import os
import logging
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN not found in .env")
    exit(1)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

users_db = {}

PRAYER_NAMES_RU = {
    "Fajr": "🌅 Фаджр",
    "Sunrise": "☀️ Восход",
    "Dhuhr": "🕌 Зухр",
    "Asr": "⛅ Аср",
    "Maghrib": "🌇 Магриб",
    "Isha": "🌙 Иша"
}

HADITHS = [
    "Дела оцениваются по намерениям. (Бухари, Муслим)",
    "Лучшие из вас — лучшие по нраву. (Бухари)",
    "Аллах любит мягкость во всех делах. (Муслим)",
    "Не уверует никто из вас по-настоящему, пока не станет желать брату своему того же, чего желает себе. (Бухари, Муслим)",
    "Мусульманин — это тот, от языка и рук которого безопасны другие мусульмане. (Бухари, Муслим)",
]

ISTIGHFAR_VARIANTS = [
    "АстагфируЛлах аль-Азым аль-Лази ля иляха илля Хув аль-Хаййуль-Каййум ва атубу иляйх",
    "СубханаЛлахи ва бихамдихи, субханаЛлахиль-Азым",
    "Ля иляха илля Анта, субханака инни кунту миназ-залимин",
    "Раббигфирли ва туб алайя, иннака Антат-Таввабур-Рахим"
]

SALAWAT = "اللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ 🤍"

class UserStates(StatesGroup):
    waiting_for_city = State()

async def get_city_by_coordinates(lat, lon):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
            headers = {'User-Agent': 'MuslimPrayerBot/1.0'}
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    city = data.get('address', {}).get('city') or \
                           data.get('address', {}).get('town') or \
                           data.get('address', {}).get('village') or \
                           data.get('address', {}).get('county')
                    return city
    except Exception as e:
        logger.error(f"Ошибка определения города: {e}")
    return None

async def get_coordinates_by_city(city_name):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
            headers = {'User-Agent': 'MuslimPrayerBot/1.0'}
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        lat = float(data[0]['lat'])
                        lon = float(data[0]['lon'])
                        display_name = data[0]['display_name'].split(',')[0]
                        return lat, lon, display_name
    except Exception as e:
        logger.error(f"Ошибка получения координат: {e}")
    return None, None, None

async def get_prayer_times(lat, lon):
    try:
        async with aiohttp.ClientSession() as session:
            date = datetime.now().strftime('%d-%m-%Y')
            url = f"http://api.aladhan.com/v1/timings/{date}"
            params = {
                'latitude': lat,
                'longitude': lon,
                'method': 3,
                'school': 0,
                'timezonestring': 'auto'
            }
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["code"] == 200:
                        return data["data"]["timings"]
    except Exception as e:
        logger.error(f"Ошибка получения намазов: {e}")
    return None

def location_keyboard():
    keyboard = [
        [KeyboardButton(text="📍 Отправить местоположение", request_location=True)],
        [KeyboardButton(text="🏙️ Написать название города")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def main_menu():
    keyboard = [
        [InlineKeyboardButton(text="📱 Открыть Азкары", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))],
        [InlineKeyboardButton(text="🕌 Времена намазов", callback_data="prayer_times")],
        [InlineKeyboardButton(text="📖 Хадис дня", callback_data="hadith_day")],
        [InlineKeyboardButton(text="📍 Изменить город", callback_data="change_city")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(CommandStart())
async def start_command(message: Message):
    welcome_text = (
        "🌙 *Ассаламу алейкум!*\n\n"
        "Я бот «Благодатный дождь» — ваш помощник в поклонении.\n\n"
        "📍 *Установите ваш город:*\n"
        "• Отправьте местоположение\n"
        "• Или напишите название города"
    )
    await message.answer(welcome_text, reply_markup=location_keyboard(), parse_mode=ParseMode.MARKDOWN)

@router.message(F.location)
async def handle_location(message: Message):
    user_id = message.from_user.id
    location = message.location
    
    lat = location.latitude
    lon = location.longitude
    
    city = await get_city_by_coordinates(lat, lon)
    
    if not city:
        city = f"{lat:.4f}, {lon:.4f}"
    
    users_db[user_id] = {
        'city': city,
        'lat': lat,
        'lon': lon,
        'type': 'coords',
        'last_updated': datetime.now()
    }
    
    times = await get_prayer_times(lat, lon)
    
    text = f"✅ *Город установлен!*\n\n📍 *{city}*\n\n"
    
    if times:
        text += "🕌 *Времена намазов на сегодня:*\n\n"
        prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
        for prayer in prayers:
            if prayer in times:
                text += f"{PRAYER_NAMES_RU[prayer]} — *{times[prayer]}*\n"
        
        text += f"\n📅 *{datetime.now().strftime('%d.%m.%Y')}*\n\n"
        text += "⏰ Вы будете получать уведомления за 10 минут до намаза!"
    
    await message.answer(text, reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)
    await message.answer("Используйте меню ниже ⬇", reply_markup=ReplyKeyboardRemove())

@router.message(F.text == "🏙️ Написать название города")
async def ask_city(message: Message, state: FSMContext):
    await message.answer(
        "✍️ *Напишите название вашего города:*\n\nНапример: Москва, Казань, Назрань",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN
    )
    await state.set_state(UserStates.waiting_for_city)

@router.message(UserStates.waiting_for_city)
async def handle_city_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    city_name = message.text.strip()
    
    lat, lon, display_name = await get_coordinates_by_city(city_name)
    
    if lat and lon:
        city_display = display_name or city_name
        
        users_db[user_id] = {
            'city': city_display,
            'lat': lat,
            'lon': lon,
            'type': 'city',
            'last_updated': datetime.now()
        }
        
        times = await get_prayer_times(lat, lon)
        
        text = f"✅ *Город установлен!*\n\n📍 *{city_display}*\n\n"
        
        if times:
            text += "🕌 *Времена намазов на сегодня:*\n\n"
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — *{times[prayer]}*\n"
            
            text += f"\n📅 *{datetime.now().strftime('%d.%m.%Y')}*\n\n"
            text += "⏰ Вы будете получать уведомления за 10 минут до намаза!"
        
        await message.answer(text, reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer(
            "❌ *Не удалось найти город*\n\nПроверьте название и попробуйте еще раз:",
            reply_markup=location_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    await state.clear()

@router.callback_query(F.data == "prayer_times")
async def prayer_times_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id in users_db:
        user_data = users_db[user_id]
        times = await get_prayer_times(user_data['lat'], user_data['lon'])
        
        if times:
            text = f"🕌 *Времена намазов для {user_data['city']}:*\n\n"
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — *{times[prayer]}*\n"
            
            text += f"\n📅 *{datetime.now().strftime('%d.%m.%Y')}*\n\n"
            
            now = datetime.now()
            upcoming_prayers = []
            
            for prayer, time_str in times.items():
                if prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                    prayer_time = datetime.strptime(time_str, "%H:%M")
                    if prayer_time.time() > now.time():
                        upcoming_prayers.append((prayer, time_str))
            
            upcoming_prayers.sort(key=lambda x: x[1])
            
            if upcoming_prayers:
                text += "⏰ *Ближайшие намазы:*\n"
                for i, (prayer, time_str) in enumerate(upcoming_prayers[:2]):
                    text += f"• {PRAYER_NAMES_RU[prayer]} — {time_str}\n"
            
            await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)
        else:
            await callback.message.edit_text("❌ Не удалось получить времена намазов", reply_markup=main_menu())
    else:
        await callback.message.edit_text("❌ Сначала установите город!", reply_markup=main_menu())
    
    await callback.answer()

@router.callback_query(F.data == "hadith_day")
async def hadith_day_handler(callback: CallbackQuery):
    hadith = HADITHS[datetime.now().timetuple().tm_yday % len(HADITHS)]
    text = f"📖 *Хадис дня:*\n\n{hadith}\n\nПусть Аллах сделает нас из тех, кто следует Сунне! 🤍"
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@router.callback_query(F.data == "change_city")
async def change_city_handler(callback: CallbackQuery):
    text = "📍 *Изменить город*\n\nВы можете:\n• Отправить местоположение\n• Или написать название города"
    await callback.message.edit_text(text, reply_markup=location_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

async def send_prayer_notifications():
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    time_10min = (now + timedelta(minutes=10)).strftime("%H:%M")
    
    for user_id, user_data in list(users_db.items()):
        try:
            times = await get_prayer_times(user_data['lat'], user_data['lon'])
            if not times:
                continue
            
            for prayer, time_str in times.items():
                if prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                    if time_str == time_10min:
                        notification_text = f"⏰ *Через 10 минут {PRAYER_NAMES_RU[prayer]}!*\n\n"
                        notification_text += f"📍 {user_data['city']}\n"
                        notification_text += f"🕰 Время намаза: {time_str}\n\n"
                        notification_text += "Подготовьтесь к молитве! 🤲"
                        
                        await bot.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        await asyncio.sleep(0.1)
                    
                    elif time_str == current_time_str:
                        notification_text = f"🕌 *Время намаза {PRAYER_NAMES_RU[prayer]}!*\n\n"
                        notification_text += f"📍 {user_data['city']}\n"
                        notification_text += f"🕰 {time_str}\n\n"
                        notification_text += "Вставайте на молитву! 🤲"
                        
                        if prayer == "Fajr":
                            notification_text += "\n\n🌅 *Не забудьте утренние азкары!*"
                        elif prayer == "Maghrib":
                            notification_text += "\n\n🌇 *Не забудьте вечерние азкары!*"
                        
                        await bot.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=main_menu()
                        )
                        await asyncio.sleep(0.1)
                        
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователю {user_id}: {e}")

async def send_istighfar_reminder():
    now = datetime.now()
    reminder_times = [(7, 0), (13, 0), (20, 0)]
    
    if (now.hour, now.minute) in reminder_times:
        istighfar = ISTIGHFAR_VARIANTS[now.timetuple().tm_yday % len(ISTIGHFAR_VARIANTS)]
        
        for user_id in list(users_db.keys()):
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"🤲 *Напоминание об истигфаре*\n\n{istighfar}\n\n"
                         f"Истигфар — это ключ к прощению и милости Аллаха!",
                    parse_mode=ParseMode.MARKDOWN
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка отправки истигфара пользователю {user_id}: {e}")

async def send_friday_salawat():
    now = datetime.now()
    if now.weekday() == 4:
        if now.hour in range(10, 19) and now.minute == 0:
            for user_id in list(users_db.keys()):
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"🤍 *Пятничный салават!*\n\n{SALAWAT}\n\n"
                             f"Отправляйте салават Пророку ﷺ как можно больше сегодня! "
                             f"Каждый салават — это свет на мосту Сират!",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=main_menu()
                    )
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Ошибка отправки салавата пользователю {user_id}: {e}")

async def setup_scheduler():
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    scheduler.add_job(send_prayer_notifications, 'interval', minutes=1)
    scheduler.add_job(send_istighfar_reminder, 'interval', minutes=1)
    scheduler.add_job(send_friday_salawat, 'interval', minutes=1)
    
    scheduler.start()

async def main():
    logger.info("✅ Бот запускается...")
    await setup_scheduler()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())