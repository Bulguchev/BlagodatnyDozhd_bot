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
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Russia&method=2"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["code"] == 200:
                        return data["data"]["timings"]
    except:
        pass
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
    
    users_db[user_id] = city
    
    times = await get_prayer_times(city)
    
    if times:
        text = f"✅ Город сохранён: {city}\n\n"
        text += "🕌 *Времена намазов:*\n\n"
        
        prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        for prayer in prayers:
            if prayer in times:
                text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
        
        await update.message.reply_text(text, reply_markup=main_menu(), parse_mode='Markdown')
    else:
        await update.message.reply_text(
            f"✅ Город {city} сохранён!\n\nВыберите действие:",
            reply_markup=main_menu()
        )

async def prayer_times_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id in users_db:
        city = users_db[user_id]
        times = await get_prayer_times(city)
        if times:
            text = f"🕌 *Времена намазов для {city}:*\n\n"
            prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
            for prayer in prayers:
                if prayer in times:
                    text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
            
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

async def hadith_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    hadith = HADITHS[datetime.now().day % len(HADITHS)]
    await query.edit_message_text(
        f"📖 *Хадис дня:*\n\n{hadith}",
        reply_markup=main_menu(),
        parse_mode='Markdown'
    )

async def change_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📍 Напишите новый город:"
    )

async def check_prayer_times(context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.now().strftime("%H:%M")
    
    for user_id, city in list(users_db.items()):
        try:
            times = await get_prayer_times(city)
            if not times:
                continue
            
            for prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                if prayer in times and times[prayer] == current_time:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"🕌 *Время намаза {PRAYER_NAMES_RU[prayer]}!*\n\nВставайте на молитву! 🤲",
                        parse_mode='Markdown'
                    )
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")

def main():
    if not TOKEN:
        logger.error("TOKEN не установлен!")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    app.job_queue.run_repeating(check_prayer_times, interval=60, first=10)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_city))
    app.add_handler(CallbackQueryHandler(prayer_times_handler, pattern="^prayer_times$"))
    app.add_handler(CallbackQueryHandler(hadith_handler, pattern="^hadith$"))
    app.add_handler(CallbackQueryHandler(change_city_handler, pattern="^change_city$"))
    
    logger.info("Бот запускается...")
    app.run_polling()

if __name__ == "__main__":
    main()