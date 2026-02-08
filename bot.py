import os
import datetime
import json
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = os.getenv("TOKEN")

users = {}

PRAYER_NAMES_RU = {
    "Fajr": "🌅 Фаджр (Рассвет)",
    "Sunrise": "☀️ Восход",
    "Dhuhr": "🕌 Зухр",
    "Asr": "🌤️ Аср",
    "Maghrib": "🌆 Магриб",
    "Isha": "🌙 Иша",
    "Imsak": "🕰️ Имсак",
    "Midnight": "🌃 Полночь"
}

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

MORNING_TEXT = "🌅 *Утренние азкары*\n\nНе забудьте прочитать:\n• Аятуль-Курси\n• Последние 2 аята суры Аль-Бакара\n• Суры Аль-Ихлас, Аль-Фаляк, Ан-Нас"
EVENING_TEXT = "🌇 *Вечерние азкары*\n\nНе забудьте прочитать:\n• Аятуль-Курси\n• Последние 2 аята суры Аль-Бакара\n• Суры Аль-Ихлас, Аль-Фаляк, Ан-Нас"
ISTIGHFAR_TEXT = "🕋 *АстагфируЛлах аль-Азым*"
SALAWAT_TEXT = "🕌 *Аллахумма салли аля Мухаммад*"

def get_prayer_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        timings = data["data"]["timings"]
        date_info = data["data"]["date"]["readable"]
        return timings, date_info
    except:
        return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [KeyboardButton("📖 Открыть Азкары", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))],
        [KeyboardButton("📍 Отправить геолокацию", request_location=True)],
        [KeyboardButton("🕌 Время намазов")]
    ]
    
    welcome_text = """
🕌 *Ас-саляму алейкум ва рахматуЛлахи ва баракятуху!*

*Добро пожаловать в бота "Благодатный дождь"* 🌧️

Я помогу вам:
• 📅 Узнать точное время намазов
• 📖 Читать ежедневные азкары
• 🌅 Получать напоминания о молитвах
• 🕌 Следить за временем рассвета (Фаджр)

*Для начала работы:*
1️⃣ Нажмите кнопку ниже для открытия сборника азкаров
2️⃣ Отправьте геолокацию или название города
3️⃣ Получайте ежедневные уведомления о времени намазов

*Да воздаст вам Аллах благом!* 🤲
"""
    
    await update.message.reply_text(
        text=welcome_text,
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True),
        parse_mode='Markdown'
    )

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        
        try:
            url = f"https://nominatim.openstreetmap.org/reverse"
            params = {"lat": lat, "lon": lon, "format": "json", "accept-language": "ru"}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            city = data.get("address", {}).get("city") or data.get("address", {}).get("town") or "Ташкент"
        except:
            city = "Ташкент"
    else:
        city = update.message.text.strip()
    
    users[update.message.chat_id] = city
    
    timings, date_info = get_prayer_times(city)
    
    if timings:
        response_text = f"""
✅ *Город сохранён: {city}*
📅 {date_info}

*Времена намазов на сегодня:*

🌅 *Фаджр (Рассвет):* {timings['Fajr']}
☀️ *Восход:* {timings['Sunrise']}
🕌 *Зухр:* {timings['Dhuhr']}
🌤️ *Аср:* {timings['Asr']}
🌆 *Магриб:* {timings['Maghrib']}
🌙 *Иша:* {timings['Isha']}
🕰️ *Имсак:* {timings['Imsak']}
🌃 *Полночь:* {timings['Midnight']}

*Напоминания:*
• 🕰️ За 10 минут до каждого намаза
• 🌅 Утренние азкары после Фаджра
• 🌇 Вечерние азкары после Магриба
"""
    else:
        response_text = f"""
✅ *Город сохранён: {city}*

⚠️ *Не удалось получить время намазов*
Проверьте название города или попробуйте позже.

Вы можете получить время намазов вручную, нажав кнопку ниже.
"""
    
    inline_kb = [
        [InlineKeyboardButton("🔄 Обновить время намазов", callback_data="update_times")],
        [InlineKeyboardButton("📖 Открыть Азкары", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))],
        [InlineKeyboardButton("📍 Изменить город", callback_data="change_city")]
    ]
    
    await update.message.reply_text(
        text=response_text,
        reply_markup=InlineKeyboardMarkup(inline_kb),
        parse_mode='Markdown'
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    city = users.get(query.message.chat_id)
    
    if query.data == "update_times" or query.data == "times":
        if not city:
            await query.edit_message_text(
                "📍 *Сначала укажите город*\n\nОтправьте геолокацию или название города.",
                parse_mode='Markdown'
            )
            return
            
        timings, date_info = get_prayer_times(city)
        
        if timings:
            text = f"""
🕌 *Времена намазов*
📍 Город: {city}
📅 {date_info}

*Основные намазы:*
🌅 *Фаджр (Рассвет):* {timings['Fajr']}
🕌 *Зухр:* {timings['Dhuhr']}
🌤️ *Аср:* {timings['Asr']}
🌆 *Магриб:* {timings['Maghrib']}
🌙 *Иша:* {timings['Isha']}

*Дополнительно:*
☀️ *Восход:* {timings['Sunrise']}
🕰️ *Имсак:* {timings['Imsak']}
🌃 *Полночь:* {timings['Midnight']}

*Следующий намаз:*
{get_next_prayer(timings)}
"""
        else:
            text = f"""
⚠️ *Не удалось получить время намазов*

Город: {city}
Попробуйте обновить позже или проверьте название города.
"""
        
        inline_kb = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="update_times")],
            [InlineKeyboardButton("📖 Открыть Азкары", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))],
            [InlineKeyboardButton("📍 Изменить город", callback_data="change_city")]
        ]
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_kb),
            parse_mode='Markdown'
        )
    
    elif query.data == "change_city":
        kb = [
            [KeyboardButton("📍 Отправить геолокацию", request_location=True)],
            [KeyboardButton("🏙️ Ввести город вручную")]
        ]
        
        await query.edit_message_text(
            "📍 *Укажите новый город*\n\nОтправьте геолокацию или напишите название города:",
            parse_mode='Markdown'
        )
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Выберите способ:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
        )

def get_next_prayer(timings):
    """Определяет следующий намаз"""
    now = datetime.datetime.now().strftime("%H:%M")
    prayer_times = [
        ("Fajr", timings["Fajr"], "🌅 Фаджр (Рассвет)"),
        ("Dhuhr", timings["Dhuhr"], "🕌 Зухр"),
        ("Asr", timings["Asr"], "🌤️ Аср"),
        ("Maghrib", timings["Maghrib"], "🌆 Магриб"),
        ("Isha", timings["Isha"], "🌙 Иша"),
    ]
    
    for prayer_name, prayer_time, display_name in prayer_times:
        if now < prayer_time:
            time_until = calculate_time_until(now, prayer_time)
            return f"{display_name} в {prayer_time}\n⏳ Осталось: {time_until}"
    
    return "🌅 Следующий намаз - Фаджр (завтра)"

def calculate_time_until(now_str, prayer_str):
    """Вычисляет время до намаза"""
    now = datetime.datetime.strptime(now_str, "%H:%M")
    prayer = datetime.datetime.strptime(prayer_str, "%H:%M")
    
    if prayer < now:
        prayer = prayer.replace(day=prayer.day + 1)
    
    diff = prayer - now
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"

async def send_notifications(app):
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M")
    
    for user_id, city in list(users.items()):
        try:
            timings, _ = get_prayer_times(city)
            if not timings:
                continue
                
            for prayer_name in PRAYER_NAMES_RU:
                if prayer_name in timings and timings[prayer_name] == time_str:
                    emoji = "🌅" if prayer_name == "Fajr" else "🕌" if prayer_name == "Dhuhr" else "🌤️" if prayer_name == "Asr" else "🌆" if prayer_name == "Maghrib" else "🌙"
                    await app.bot.send_message(
                        user_id,
                        f"{emoji} *Время намаза: {PRAYER_NAMES_RU[prayer_name]}*\n\nНе забудьте совершить молитву вовремя! 🤲",
                        parse_mode='Markdown'
                    )
                    
            for prayer_name in PRAYERS:
                prayer_time = datetime.datetime.strptime(timings[prayer_name], "%H:%M")
                reminder_time = (prayer_time - datetime.timedelta(minutes=10)).strftime("%H:%M")
                
                if reminder_time == time_str:
                    await app.bot.send_message(
                        user_id,
                        f"⏰ *Напоминание:* До намаза {PRAYER_NAMES_RU[prayer_name]} осталось 10 минут!\n\nПодготовьтесь к молитве.",
                        parse_mode='Markdown'
                    )
            if timings["Fajr"] == time_str:
                await app.bot.send_message(
                    user_id,
                    MORNING_TEXT,
                    parse_mode='Markdown'
                )
            
            if timings["Maghrib"] == time_str:
                await app.bot.send_message(
                    user_id,
                    EVENING_TEXT,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")

async def run_scheduler(app):
    while True:
        await send_notifications(app)
        await asyncio.sleep(60)

async def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT | filters.LOCATION, set_city))
    application.add_handler(CallbackQueryHandler(buttons))
    
    asyncio.create_task(run_scheduler(application))
    
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())