import os
import logging
from datetime import datetime, timedelta
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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# База данных в памяти (для демо, в продакшене используйте реальную БД)
users_db = {}

PRAYER_NAMES_RU = {
    "Fajr": "🌅 Фаджр",
    "Sunrise": "☀️ Восход",
    "Dhuhr": "🕌 Зухр",
    "Asr": "⛅ Аср",
    "Maghrib": "🌇 Магриб",
    "Isha": "🌙 Иша"
}

# База данных для хранения
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
        [InlineKeyboardButton("📱 Открыть Азкары", web_app=WebAppInfo(url="https://blagodat.vercel.app"))],
        [InlineKeyboardButton("🕌 Времена намазов", callback_data="prayer_times")],
        [InlineKeyboardButton("📖 Хадис дня", callback_data="hadith_day")],
        [InlineKeyboardButton("🤲 Истигфар", callback_data="istighfar")],
        [InlineKeyboardButton("📍 Изменить город", callback_data="change_city")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    welcome_text = (
        "Ассаламу алейкум! 🌙\n\n"
        "Я бот «Благодатный дождь» — ваш помощник в поклонении.\n\n"
        "📌 *Мои функции:*\n"
        "• Времена намазов по вашему городу\n"
        "• Ежедневные хадисы\n"
        "• Напоминания о намазах\n"
        "• Истигфар и салаваты\n"
        "• Веб-азкары\n\n"
        "📍 *Сначала определим ваше местоположение:*"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=location_keyboard(),
        parse_mode='Markdown'
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
            'type': 'coords',
            'last_updated': datetime.now()
        }
        
        times = await get_prayer_times(lat, lon, city)
        
        if times:
            text = f"✅ *Местоположение определено!*\n\n"
            text += f"📍 *Город:* {city}\n\n"
            text += "🕌 *Времена намазов на сегодня:*\n\n"
            
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — *{times[prayer]}*\n"
            
            text += f"\n📅 *{datetime.now().strftime('%d.%m.%Y')}*\n\n"
            text += "Теперь вы будете получать уведомления о времени намазов! ⏰"
            
            await update.message.reply_text(
                text, 
                reply_markup=main_menu(), 
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"✅ *Местоположение определено!*\n\n📍 *Город:* {city}\n\n"
                "К сожалению, не удалось получить расписание намазов для вашего города. "
                "Попробуйте ввести город вручную.",
                reply_markup=main_menu(),
                parse_mode='Markdown'
            )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text == "🏙️ Ввести город вручную":
        await update.message.reply_text(
            "Напишите название вашего города (например: *Москва*, *Казань*, *Грозный*):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📍 Отправить местоположение", request_location=True)]], 
                resize_keyboard=True
            ),
            parse_mode='Markdown'
        )
        return
    
    if text == "📍 Отправить местоположение":
        await update.message.reply_text(
            "Нажмите кнопку ниже, чтобы отправить ваше местоположение:",
            reply_markup=location_keyboard()
        )
        return
    
    # Если пользователь просто отправил текст (название города)
    lat, lon, display_name = await get_coordinates_by_city(text)
    
    if lat and lon:
        city_name = display_name or text
        
        users_db[user_id] = {
            'city': city_name,
            'lat': lat,
            'lon': lon,
            'type': 'city',
            'last_updated': datetime.now()
        }
        
        times = await get_prayer_times(lat, lon, city_name)
        
        if times:
            message_text = f"✅ *Город определен!*\n\n📍 *Город:* {city_name}\n\n"
            message_text += "🕌 *Времена намазов на сегодня:*\n\n"
            
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    message_text += f"{PRAYER_NAMES_RU[prayer]} — *{times[prayer]}*\n"
            
            message_text += f"\n📅 *{datetime.now().strftime('%d.%m.%Y')}*\n\n"
            message_text += "Теперь вы будете получать уведомления о времени намазов! ⏰"
            
            await update.message.reply_text(
                message_text,
                reply_markup=main_menu(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"✅ *Город определен!*\n\n📍 *Город:* {city_name}\n\n"
                "К сожалению, не удалось получить расписание намазов для вашего города.\n\n"
                "Выберите действие из меню:",
                reply_markup=main_menu(),
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            "❌ Не удалось найти город. Проверьте название и попробуйте еще раз.\n"
            "Можно отправить местоположение:",
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
                "❌ Не удалось получить координаты. Пожалуйста, установите город заново.",
                reply_markup=main_menu()
            )
            return
        
        if times:
            text = f"🕌 *Времена намазов для {city}:*\n\n"
            prayers = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — *{times[prayer]}*\n"
            
            text += f"\n📅 *{datetime.now().strftime('%d.%m.%Y')}*\n\n"
            text += "⏰ *Ближайшие намазы:*\n"
            
            # Определяем ближайший намаз
            now = datetime.now()
            current_time = now.strftime("%H:%M")
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
                await query.edit_message_text(
                    text, 
                    reply_markup=main_menu(), 
                    parse_mode='Markdown'
                )
            except BadRequest:
                await query.message.reply_text(
                    text, 
                    reply_markup=main_menu(), 
                    parse_mode='Markdown'
                )
        else:
            await query.edit_message_text(
                "❌ Не удалось получить времена намазов. Попробуйте позже.",
                reply_markup=main_menu()
            )
    else:
        await query.edit_message_text(
            "❌ Сначала установите город!",
            reply_markup=main_menu()
        )

async def hadith_day_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    day_of_year = datetime.now().timetuple().tm_yday
    hadith_index = day_of_year % len(HADITHS)
    hadith = HADITHS[hadith_index]
    
    text = f"📖 *Хадис дня:*\n\n{hadith}\n\n"
    text += "Пусть Аллах сделает нас из тех, кто следует Сунне! 🤍"
    
    try:
        await query.edit_message_text(
            text, 
            reply_markup=main_menu(), 
            parse_mode='Markdown'
        )
    except BadRequest:
        await query.message.reply_text(
            text, 
            reply_markup=main_menu(), 
            parse_mode='Markdown'
        )

async def istighfar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    day_of_year = datetime.now().timetuple().tm_yday
    istighfar_index = day_of_year % len(ISTIGHFAR_VARIANTS)
    istighfar = ISTIGHFAR_VARIANTS[istighfar_index]
    
    text = f"🤲 *Истигфар на сегодня:*\n\n"
    text += f"*{istighfar}*\n\n"
    text += "📿 *Перевод:* \n«Прости меня, о Аллах, Великий, кроме Которого нет иного божества, "
    text += "Живого, Вечно Сущего, и я каюсь перед Тобой»\n\n"
    text += "*Произносите этот истигфар как можно чаще сегодня!*"
    
    try:
        await query.edit_message_text(
            text, 
            reply_markup=main_menu(), 
            parse_mode='Markdown'
        )
    except BadRequest:
        await query.message.reply_text(
            text, 
            reply_markup=main_menu(), 
            parse_mode='Markdown'
        )

async def change_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = "📍 *Изменить город*\n\n"
    text += "Вы можете:\n"
    text += "• Написать название города (например: *Москва*, *Казань*)\n"
    text += "• Или отправить местоположение\n\n"
    text += "Напишите название города:"
    
    try:
        await query.edit_message_text(
            text,
            reply_markup=location_keyboard(),
            parse_mode='Markdown'
        )
    except BadRequest:
        await query.message.reply_text(
            text,
            reply_markup=location_keyboard(),
            parse_mode='Markdown'
        )

# ============ ФУНКЦИИ УВЕДОМЛЕНИЙ ============

async def send_hadith_daily(context: ContextTypes.DEFAULT_TYPE):
    """Отправка ежедневного хадиса в 9:00"""
    now = datetime.now()
    if now.hour == 9 and now.minute == 0:
        day_of_year = now.timetuple().tm_yday
        hadith_index = day_of_year % len(HADITHS)
        hadith = HADITHS[hadith_index]
        
        for user_id in list(users_db.keys()):
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📖 *Хадис дня:*\n\n{hadith}\n\nДа примет Аллах наши благие дела! 🤍",
                    parse_mode='Markdown'
                )
                await asyncio.sleep(0.1)  # Задержка, чтобы не превысить лимиты
            except Exception as e:
                logger.error(f"Ошибка отправки хадиса пользователю {user_id}: {e}")
                # Удаляем неактивного пользователя
                if "chat not found" in str(e) or "blocked" in str(e):
                    users_db.pop(user_id, None)

async def send_prayer_notifications(context: ContextTypes.DEFAULT_TYPE):
    """Уведомления о времени намазов"""
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    for user_id, user_data in list(users_db.items()):
        try:
            # Проверяем, когда последний раз обновлялись данные
            last_updated = user_data.get('last_updated', datetime.min)
            if datetime.now() - last_updated > timedelta(hours=24):
                # Обновляем время намазов раз в день
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
            
            # Проверяем время намазов
            for prayer, time_str in times.items():
                if prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                    if time_str == current_time_str:
                        # Отправляем уведомление
                        notification_text = f"🕌 *Время намаза {PRAYER_NAMES_RU[prayer]}!*\n\n"
                        notification_text += f"📍 {user_data['city']}\n"
                        notification_text += f"⏰ {time_str}\n\n"
                        notification_text += "Вставайте на молитву! 🤲\n\n"
                        
                        if prayer == "Fajr":
                            notification_text += "🌅 *Не забудьте утренние азкары!*"
                        elif prayer == "Maghrib":
                            notification_text += "🌇 *Не забудьте вечерние азкары!*"
                        
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            parse_mode='Markdown',
                            reply_markup=main_menu()
                        )
                        await asyncio.sleep(0.1)
                        
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователю {user_id}: {e}")

async def send_istighfar_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Напоминание об истигфаре 3 раза в день"""
    now = datetime.now()
    reminder_times = [(7, 0), (13, 0), (20, 0)]  # 7:00, 13:00, 20:00
    
    if (now.hour, now.minute) in reminder_times:
        day_of_year = now.timetuple().tm_yday
        istighfar_index = day_of_year % len(ISTIGHFAR_VARIANTS)
        istighfar = ISTIGHFAR_VARIANTS[istighfar_index]
        
        for user_id in list(users_db.keys()):
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🤲 *Напоминание об истигфаре*\n\n"
                         f"Произнесите: *{istighfar}*\n\n"
                         f"Истигфар — это ключ к прощению и милости Аллаха!",
                    parse_mode='Markdown'
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка отправки истигфара пользователю {user_id}: {e}")

async def send_friday_salawat(context: ContextTypes.DEFAULT_TYPE):
    """Пятничные салаваты"""
    now = datetime.now()
    if now.weekday() == 4:  # Пятница
        if now.hour in [10, 12, 14, 16, 18] and now.minute == 0:
            for user_id in list(users_db.keys()):
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🤍 *Пятничный салават!*\n\n{SALAWAT}\n\n"
                             f"Отправляйте салават Пророку ﷺ как можно больше сегодня! "
                             f"Каждый салават — это свет на мосту Сират!",
                        parse_mode='Markdown',
                        reply_markup=main_menu()
                    )
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Ошибка отправки салавата пользователю {user_id}: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Ошибка: {context.error}')
    if update:
        logger.error(f'Update: {update}')

def main():
    if not TOKEN:
        logger.error("❌ Токен бота не найден! Убедитесь, что переменная TELEGRAM_BOT_TOKEN установлена.")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(prayer_times_handler, pattern="^prayer_times$"))
    app.add_handler(CallbackQueryHandler(hadith_day_handler, pattern="^hadith_day$"))
    app.add_handler(CallbackQueryHandler(istighfar_handler, pattern="^istighfar$"))
    app.add_handler(CallbackQueryHandler(change_city_handler, pattern="^change_city$"))
    
    # Настраиваем планировщик уведомлений
    job_queue = app.job_queue
    
    # Ежедневный хадис в 9:00
    job_queue.run_daily(
        send_hadith_daily,
        time=datetime.strptime("09:00", "%H:%M").time(),
        days=(0, 1, 2, 3, 4, 5, 6)
    )
    
    # Проверка намазов каждую минуту
    job_queue.run_repeating(send_prayer_notifications, interval=60, first=10)
    
    # Напоминание об истигфаре 3 раза в день
    for hour in [7, 13, 20]:
        job_queue.run_daily(
            send_istighfar_reminder,
            time=datetime.strptime(f"{hour:02d}:00", "%H:%M").time(),
            days=(0, 1, 2, 3, 4, 5, 6)
        )
    
    # Пятничные салаваты
    job_queue.run_repeating(send_friday_salawat, interval=3600, first=10)  Каждый час в пятницу
    
    app.add_error_handler(error_handler)
    
    logger.info("✅ Бот запускается...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()