import os
import logging
from datetime import datetime
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import BadRequest

import aiohttp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")

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

SALAWAT = "اللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ 🤍"

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
                'method': 3,  # Метод для России и СНГ
                'school': 0,   # Шафиитский мазхаб
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
        [KeyboardButton("📍 Отправить местоположение", request_location=True)],
        [KeyboardButton("🏙️ Ввести город вручную")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📱 Открыть Азкары", web_app=WebAppInfo(url="https://blagodatny-dozhd-j76zeu4g3-blgchevvs-projects.vercel.app"))],
        [InlineKeyboardButton("🕌 Времена намазов", callback_data="prayer_times")],
        [InlineKeyboardButton("📍 Изменить город", callback_data="change_city")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаламу алейкум! 🌙\n\n"
        "Я бот «Благодатный дождь»\n\n"
        "Выберите способ определения местоположения:",
        reply_markup=location_keyboard()
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    location = update.message.location
    
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
            'type': 'coords'
        }
        
        times = await get_prayer_times(lat, lon, city)
        
        if times:
            text = f"✅ *Местоположение определено*\n\n"
            text += f"📍 *Город:* {city}\n\n"
            text += "🕌 *Времена намазов:*\n\n"
            
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
            
            text += f"\n📅 {datetime.now().strftime('%d.%m.%Y')}"
            
            await update.message.reply_text(text, reply_markup=main_menu(), parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"✅ *Местоположение определено*\n\n📍 *Город:* {city}\n\nВыберите действие:",
                reply_markup=main_menu(),
                parse_mode='Markdown'
            )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text == "🏙️ Ввести город вручную":
        await update.message.reply_text(
            "Напишите название вашего города:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📍 Отправить местоположение", request_location=True)]], resize_keyboard=True)
        )
        return
    
    if text == "📍 Отправить местоположение":
        await update.message.reply_text(
            "Нажмите кнопку ниже, чтобы отправить ваше местоположение:",
            reply_markup=location_keyboard()
        )
        return
    
    lat, lon, display_name = await get_coordinates_by_city(text)
    
    if lat and lon:
        city_name = display_name or text
        
        users_db[user_id] = {
            'city': city_name,
            'lat': lat,
            'lon': lon,
            'type': 'city'
        }
        
        times = await get_prayer_times(lat, lon, city_name)
        
        if times:
            message_text = f"✅ *Город определен:* {city_name}\n\n"
            message_text += "🕌 *Времена намазов:*\n\n"
            
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    message_text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
            
            message_text += f"\n📅 {datetime.now().strftime('%d.%m.%Y')}"
            
            await update.message.reply_text(
                message_text,
                reply_markup=main_menu(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"✅ *Город определен:* {city_name}\n\nВыберите действие:",
                reply_markup=main_menu(),
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            "Не удалось найти город. Проверьте название и попробуйте еще раз:",
            reply_markup=location_keyboard()
        )

async def prayer_times_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id in users_db:
        user_data = users_db[user_id]
        city = user_data['city']
        
        if user_data['type'] in ['coords', 'city'] and user_data['lat'] and user_data['lon']:
            times = await get_prayer_times(user_data['lat'], user_data['lon'], city)
        else:
            await query.edit_message_text(
                "Не удалось получить координаты. Пожалуйста, установите город заново.",
                reply_markup=main_menu()
            )
            return
        
        if times:
            text = f"🕌 *Времена намазов для {city}:*\n\n"
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
            
            text += f"\n📅 {datetime.now().strftime('%d.%m.%Y')}"
            try:
                await query.edit_message_text(text, reply_markup=main_menu(), parse_mode='Markdown')
            except BadRequest:
                await query.message.reply_text(text, reply_markup=main_menu(), parse_mode='Markdown')
        else:
            await query.edit_message_text(
                "Не удалось получить времена намазов",
                reply_markup=main_menu()
            )
    else:
        await query.edit_message_text(
            "Сначала установите город!",
            reply_markup=main_menu()
        )

async def change_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📍 Напишите новый город:",
        reply_markup=location_keyboard()
    )

async def send_hadith_daily(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if now.hour == 9 and now.minute == 0:
        hadith = HADITHS[now.day % len(HADITHS)]
        for user_id in users_db:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📖 *Хадис дня:*\n\n{hadith}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка отправки хадиса: {e}")

async def send_prayer_notifications(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    for user_id, user_data in list(users_db.items()):
        try:
            if user_data['type'] in ['coords', 'city'] and user_data['lat'] and user_data['lon']:
                times = await get_prayer_times(user_data['lat'], user_data['lon'], user_data['city'])
            else:
                continue
            
            if not times:
                continue
            
            main_prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in main_prayers:
                if prayer in times and times[prayer] == current_time:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🕌 *Время намаза {PRAYER_NAMES_RU[prayer]}!*\n\nВставайте на молитву! 🤲",
                        parse_mode='Markdown'
                    )
                    
                    if prayer == "Fajr":
                        await asyncio.sleep(2)
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="🌅 *Не забудьте прочитать утренние азкары!*\n\nНажмите кнопку ниже 👇",
                            reply_markup=main_menu(),
                            parse_mode='Markdown'
                        )
                    elif prayer == "Maghrib":
                        await asyncio.sleep(2)
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="🌇 *Не забудьте прочитать вечерние азкары!*\n\nНажмите кнопку ниже 👇",
                            reply_markup=main_menu(),
                            parse_mode='Markdown'
                        )
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")

async def send_friday_salawat(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if now.weekday() == 4 and now.hour in [10, 12, 14, 16, 18] and now.minute == 0:
        for user_id in users_db:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🤍 *Пятничный салават!*\n\n{SALAWAT}\n\nОтправляйте салават Пророку ﷺ как можно больше сегодня!",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка отправки салавата: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning(f'Update {update} caused error {context.error}')

def main():
    if not TOKEN:
        logger.error("TOKEN не установлен!")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    app.job_queue.run_repeating(send_hadith_daily, interval=60)
    app.job_queue.run_repeating(send_prayer_notifications, interval=60)
    app.job_queue.run_repeating(send_friday_salawat, interval=60)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(prayer_times_handler, pattern="^prayer_times$"))
    app.add_handler(CallbackQueryHandler(change_city_handler, pattern="^change_city$"))
    
    app.add_error_handler(error_handler)
    
    logger.info("Бот запускается...")
    app.run_polling()

if __name__ == "__main__":
    main()