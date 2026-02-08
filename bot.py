import os
import logging
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, Location
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
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

async def get_prayer_times(lat, lon, city_name=None):
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
        [KeyboardButton(text="🏙️ Ввести город вручную")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def main_menu():
    keyboard = [
        [InlineKeyboardButton(text="📱 Открыть Азкары", web_app=WebAppInfo(url="https://blagodat.vercel.app"))],
        [InlineKeyboardButton(text="🕌 Времена намазов", callback_data="prayer_times")],
        [InlineKeyboardButton(text="📖 Хадис дня", callback_data="hadith_day")],
        [InlineKeyboardButton(text="🤲 Истигфар", callback_data="istighfar")],
        [InlineKeyboardButton(text="📍 Изменить город", callback_data="change_city")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(CommandStart())
async def start_command(message: Message):
    welcome_text = (
        "Ассаламу алейкум! 🌙\n\n"
        "Я бот «Благодатный дождь» — ваш помощник в поклонении.\n\n"
        "📌 <b>Мои функции:</b>\n"
        "• Времена намазов по вашему городу\n"
        "• Ежедневные хадисы\n"
        "• Напоминания о намазах\n"
        "• Истигфар и салаваты\n"
        "• Веб-азкары\n\n"
        "<b>📍 Сначала определим ваше местоположение:</b>"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=location_keyboard(),
        parse_mode=ParseMode.HTML
    )

@router.message(F.location)
async def handle_location(message: Message):
    user_id = message.from_user.id
    location = message.location
    
    if location:
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
        
        times = await get_prayer_times(lat, lon, city)
        
        if times:
            text = f"✅ <b>Местоположение определено!</b>\n\n"
            text += f"📍 <b>Город:</b> {city}\n\n"
            text += "🕌 <b>Времена намазов на сегодня:</b>\n\n"
            
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — <b>{times[prayer]}</b>\n"
            
            text += f"\n📅 <b>{datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
            text += "Теперь вы будете получать уведомления о времени намазов! ⏰"
            
            await message.answer(
                text, 
                reply_markup=main_menu(), 
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(
                f"✅ <b>Местоположение определено!</b>\n\n📍 <b>Город:</b> {city}\n\n"
                "К сожалению, не удалось получить расписание намазов.",
                reply_markup=main_menu(),
                parse_mode=ParseMode.HTML
            )

@router.message(F.text == "🏙️ Ввести город вручную")
async def ask_city(message: Message, state: FSMContext):
    await message.answer(
        "Напишите название вашего города:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📍 Отправить местоположение", request_location=True)]], 
            resize_keyboard=True
        ),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(UserStates.waiting_for_city)

@router.message(UserStates.waiting_for_city)
async def handle_city_input(message: Message, state: FSMContext):
    city_name = message.text.strip()
    user_id = message.from_user.id
    
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
        
        times = await get_prayer_times(lat, lon, city_display)
        
        if times:
            message_text = f"✅ <b>Город определен!</b>\n\n📍 <b>Город:</b> {city_display}\n\n"
            message_text += "🕌 <b>Времена намазов на сегодня:</b>\n\n"
            
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    message_text += f"{PRAYER_NAMES_RU[prayer]} — <b>{times[prayer]}</b>\n"
            
            message_text += f"\n📅 <b>{datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
            message_text += "Теперь вы будете получать уведомления! ⏰"
            
            await message.answer(
                message_text,
                reply_markup=main_menu(),
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(
                f"✅ <b>Город определен!</b>\n\n📍 <b>Город:</b> {city_display}\n\n"
                "К сожалению, не удалось получить расписание намазов.",
                reply_markup=main_menu(),
                parse_mode=ParseMode.HTML
            )
    else:
        await message.answer(
            "❌ Не удалось найти город. Попробуйте еще раз.",
            reply_markup=location_keyboard()
        )
    
    await state.clear()

@router.message(F.text == "📍 Отправить местоположение")
async def request_location(message: Message):
    await message.answer(
        "Нажмите кнопку ниже, чтобы отправить ваше местоположение:",
        reply_markup=location_keyboard()
    )

@router.callback_query(F.data == "prayer_times")
async def prayer_times_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id in users_db:
        user_data = users_db[user_id]
        city = user_data['city']
        
        if user_data['type'] in ['coords', 'city'] and user_data['lat'] and user_data['lon']:
            times = await get_prayer_times(user_data['lat'], user_data['lon'], city)
        else:
            await callback.message.edit_text(
                "❌ Не удалось получить координаты.",
                reply_markup=main_menu()
            )
            return
        
        if times:
            text = f"🕌 <b>Времена намазов для {city}:</b>\n\n"
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — <b>{times[prayer]}</b>\n"
            
            text += f"\n📅 <b>{datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
            text += "⏰ <b>Ближайшие намазы:</b>\n"
            
            now = datetime.now()
            upcoming_prayers = []
            
            for prayer, time_str in times.items():
                if prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                    prayer_time = datetime.strptime(time_str, "%H:%M")
                    if prayer_time.time() > now.time():
                        upcoming_prayers.append((prayer, time_str))
            
            upcoming_prayers.sort(key=lambda x: x[1])
            
            if upcoming_prayers:
                next_prayer, next_time = upcoming_prayers[0]
                text += f"• {PRAYER_NAMES_RU[next_prayer]} — {next_time}\n"
                if len(upcoming_prayers) > 1:
                    text += f"• {PRAYER_NAMES_RU[upcoming_prayers[1][0]]} — {upcoming_prayers[1][1]}"
            else:
                text += "• Завтрашний Фаджр — первым"
            
            try:
                await callback.message.edit_text(
                    text, 
                    reply_markup=main_menu(), 
                    parse_mode=ParseMode.HTML
                )
            except:
                await callback.message.answer(
                    text, 
                    reply_markup=main_menu(), 
                    parse_mode=ParseMode.HTML
                )
        else:
            await callback.message.edit_text(
                "❌ Не удалось получить времена намазов.",
                reply_markup=main_menu()
            )
    else:
        await callback.message.edit_text(
            "❌ Сначала установите город!",
            reply_markup=main_menu()
        )
    
    await callback.answer()

@router.callback_query(F.data == "hadith_day")
async def hadith_day_handler(callback: CallbackQuery):
    day_of_year = datetime.now().timetuple().tm_yday
    hadith_index = day_of_year % len(HADITHS)
    hadith = HADITHS[hadith_index]
    
    text = f"📖 <b>Хадис дня:</b>\n\n{hadith}\n\n"
    text += "Пусть Аллах сделает нас из тех, кто следует Сунне! 🤍"
    
    try:
        await callback.message.edit_text(
            text, 
            reply_markup=main_menu(), 
            parse_mode=ParseMode.HTML
        )
    except:
        await callback.message.answer(
            text, 
            reply_markup=main_menu(), 
            parse_mode=ParseMode.HTML
        )
    
    await callback.answer()

@router.callback_query(F.data == "istighfar")
async def istighfar_handler(callback: CallbackQuery):
    day_of_year = datetime.now().timetuple().tm_yday
    istighfar_index = day_of_year % len(ISTIGHFAR_VARIANTS)
    istighfar = ISTIGHFAR_VARIANTS[istighfar_index]
    
    text = f"🤲 <b>Истигфар на сегодня:</b>\n\n"
    text += f"<b>{istighfar}</b>\n\n"
    text += "📿 <b>Перевод:</b> \n«Прости меня, о Аллах, Великий, кроме Которого нет иного божества, "
    text += "Живого, Вечно Сущего, и я каюсь перед Тобой»\n\n"
    text += "<b>Произносите этот истигфар как можно чаще сегодня!</b>"
    
    try:
        await callback.message.edit_text(
            text, 
            reply_markup=main_menu(), 
            parse_mode=ParseMode.HTML
        )
    except:
        await callback.message.answer(
            text, 
            reply_markup=main_menu(), 
            parse_mode=ParseMode.HTML
        )
    
    await callback.answer()

@router.callback_query(F.data == "change_city")
async def change_city_handler(callback: CallbackQuery):
    text = "📍 <b>Изменить город</b>\n\n"
    text += "Вы можете:\n"
    text += "• Написать название города\n"
    text += "• Или отправить местоположение\n\n"
    text += "Напишите название города:"
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=location_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except:
        await callback.message.answer(
            text,
            reply_markup=location_keyboard(),
            parse_mode=ParseMode.HTML
        )
    
    await callback.answer()

async def send_hadith_daily():
    now = datetime.now()
    if now.hour == 9 and now.minute == 0:
        day_of_year = now.timetuple().tm_yday
        hadith_index = day_of_year % len(HADITHS)
        hadith = HADITHS[hadith_index]
        
        for user_id in list(users_db.keys()):
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"📖 <b>Хадис дня:</b>\n\n{hadith}\n\nДа примет Аллах наши благие дела! 🤍",
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка отправки хадиса пользователю {user_id}: {e}")
                if "chat not found" in str(e) or "blocked" in str(e):
                    users_db.pop(user_id, None)

async def send_prayer_notifications():
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    for user_id, user_data in list(users_db.items()):
        try:
            last_updated = user_data.get('last_updated', datetime.min)
            if datetime.now() - last_updated > timedelta(hours=24):
                times = await get_prayer_times(user_data['lat'], user_data['lon'], user_data['city'])
                if times:
                    user_data['prayer_times_cache'] = times
                    user_data['last_updated'] = datetime.now()
                else:
                    continue
            else:
                times = user_data.get('prayer_times_cache')
                if not times:
                    times = await get_prayer_times(user_data['lat'], user_data['lon'], user_data['city'])
                    if times:
                        user_data['prayer_times_cache'] = times
            
            if not times:
                continue
            
            for prayer, time_str in times.items():
                if prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                    if time_str == current_time_str:
                        notification_text = f"🕌 <b>Время намаза {PRAYER_NAMES_RU[prayer]}!</b>\n\n"
                        notification_text += f"📍 {user_data['city']}\n"
                        notification_text += f"⏰ {time_str}\n\n"
                        notification_text += "Вставайте на молитву! 🤲\n\n"
                        
                        if prayer == "Fajr":
                            notification_text += "🌅 <b>Не забудьте утренние азкары!</b>"
                        elif prayer == "Maghrib":
                            notification_text += "🌇 <b>Не забудьте вечерние азкары!</b>"
                        
                        await bot.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=main_menu()
                        )
                        await asyncio.sleep(0.1)
                        
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователю {user_id}: {e}")

async def send_istighfar_reminder():
    now = datetime.now()
    reminder_times = [(7, 0), (13, 0), (20, 0)]
    
    if (now.hour, now.minute) in reminder_times:
        day_of_year = now.timetuple().tm_yday
        istighfar_index = day_of_year % len(ISTIGHFAR_VARIANTS)
        istighfar = ISTIGHFAR_VARIANTS[istighfar_index]
        
        for user_id in list(users_db.keys()):
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"🤲 <b>Напоминание об истигфаре</b>\n\n"
                         f"Произнесите: <b>{istighfar}</b>\n\n"
                         f"Истигфар — это ключ к прощению и милости Аллаха!",
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка отправки истигфара пользователю {user_id}: {e}")

async def send_friday_salawat():
    now = datetime.now()
    if now.weekday() == 4:
        if now.hour in [10, 12, 14, 16, 18] and now.minute == 0:
            for user_id in list(users_db.keys()):
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"🤍 <b>Пятничный салават!</b>\n\n{SALAWAT}\n\n"
                             f"Отправляйте салават Пророку ﷺ как можно больше сегодня!",
                        parse_mode=ParseMode.HTML,
                        reply_markup=main_menu()
                    )
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Ошибка отправки салавата пользователю {user_id}: {e}")

async def setup_scheduler():
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    scheduler.add_job(send_hadith_daily, 'cron', hour=9, minute=0)
    scheduler.add_job(send_prayer_notifications, 'interval', minutes=1)
    
    for hour in [7, 13, 20]:
        scheduler.add_job(send_istighfar_reminder, 'cron', hour=hour, minute=0)
    
    scheduler.add_job(send_friday_salawat, 'cron', day_of_week='fri', hour='10-18', minute=0)
    
    scheduler.start()

async def main():
    logger.info("✅ Бот запускается...")
    await setup_scheduler()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())