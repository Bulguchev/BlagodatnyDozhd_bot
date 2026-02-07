import os
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

import aiohttp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")

users_db = {}
prayer_cache = {}

PRAYER_NAMES_RU = {
    "Fajr": "🌅 Фаджр",
    "Dhuhr": "☀️ Зухр",
    "Asr": "⛅ Аср",
    "Maghrib": "🌇 Магриб",
    "Isha": "🌙 Иша"
}

HADITHS = [
    "Дела оцениваются по намерениям. (Бухари, Муслим)",
    "Лучшие из вас — лучшие по нраву. (Бухари)",
    "Аллах любит мягкость во всех делах. (Муслим)",
]

MINI_APP_URL = "https://blagodat.vercel.app"

async def get_prayer_times(city):
    today = datetime.now().strftime('%Y-%m-%d')
    cache_key = f"{city}_{today}"
    
    if cache_key in prayer_cache:
        return prayer_cache[cache_key]
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Russia&method=2"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["code"] == 200:
                        timings = data["data"]["timings"]
                        prayer_cache[cache_key] = timings
                        return timings
    except Exception as e:
        logger.error(f"Ошибка получения намазов: {e}")
    
    return None

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📱 Открыть Азкары", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("🕌 Времена намазов", callback_data="prayer_times")],
        [InlineKeyboardButton("📖 Хадис дня", callback_data="hadith")],
        [InlineKeyboardButton("📍 Изменить город", callback_data="change_city")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаламу алейкум! 🌙\n\n"
        "Я бот «Благодатный дождь»\n\n"
        "Напишите название вашего города:"
    )

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    city = update.message.text.strip()
    
    users_db[user_id] = {"city": city}
    
    times = await get_prayer_times(city)
    
    if times:
        text = f"✅ Город сохранён: {city}\n\n"
        text += "🕌 *Времена намазов на сегодня:*\n\n"
        
        prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        for prayer in prayers:
            if prayer in times:
                text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
        
        text += f"\n📅 {datetime.now().strftime('%d.%m.%Y')}"
        
        await update.message.reply_text(text, reply_markup=main_menu(), parse_mode='Markdown')
    else:
        await update.message.reply_text(
            f"Город {city} сохранён!\n\nВыберите действие:",
            reply_markup=main_menu()
        )

async def check_prayer_time(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.chat_id
    
    if user_id not in users_db:
        return
    
    city = users_db[user_id].get("city")
    if not city:
        return
    
    current_time = datetime.now().strftime("%H:%M")
    times = await get_prayer_times(city)
    
    if not times:
        return
    
    prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    for prayer in prayers:
        if prayer in times and times[prayer] == current_time:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🕌 *Время намаза {PRAYER_NAMES_RU[prayer]}!*\n\nВставайте на молитву! 🤲",
                    parse_mode='Markdown'
                )
                
                if prayer == "Fajr":
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="🌅 *Не забудьте утренние азкары!*",
                        parse_mode='Markdown'
                    )
                elif prayer == "Maghrib":
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="🌇 *Не забудьте вечерние азкары!*",
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "prayer_times":
        if user_id in users_db and "city" in users_db[user_id]:
            city = users_db[user_id]["city"]
            times = await get_prayer_times(city)
            if times:
                text = f"🕌 *Времена намазов для {city}:*\n\n"
                prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
                for prayer in prayers:
                    if prayer in times:
                        text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
                
                text += f"\n📅 {datetime.now().strftime('%d.%m.%Y')}"
                await query.edit_message_text(text, reply_markup=main_menu(), parse_mode='Markdown')
            else:
                await query.edit_message_text(
                    f"Не удалось получить времена намазов",
                    reply_markup=main_menu()
                )
        else:
            await query.edit_message_text(
                "Сначала установите город!",
                reply_markup=main_menu()
            )
    
    elif query.data == "hadith":
        hadith = HADITHS[datetime.now().day % len(HADITHS)]
        await query.edit_message_text(
            f"📖 *Хадис дня:*\n\n{hadith}",
            reply_markup=main_menu(),
            parse_mode='Markdown'
        )
    
    elif query.data == "change_city":
        await query.edit_message_text(
            "📍 Напишите новый город:",
            reply_markup=main_menu()
        )

async def setup_jobs(application):
    for user_id in users_db:
        if "city" in users_db[user_id]:
            application.job_queue.run_repeating(
                check_prayer_time,
                interval=60,
                first=10,
                name=str(user_id),
                chat_id=user_id
            )

def main():
    if not TOKEN:
        logger.error("TOKEN не установлен!")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_city))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Бот запускается...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()