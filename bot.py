import os
import json
import asyncio
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

import aiohttp

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
    except:
        return None
    
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
        
        for prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
            if prayer in times:
                text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
        
        text += f"\n📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
        text += "Вы будете получать уведомления о намазах!"
        
        await update.message.reply_text(text, reply_markup=main_menu(), parse_mode='Markdown')
        
        context.job_queue.run_repeating(
            check_prayer_time,
            interval=60,
            first=5,
            name=str(user_id),
            chat_id=user_id,
            data={'city': city}
        )
    else:
        await update.message.reply_text(
            f"Город {city} сохранён!\n\nВыберите действие:",
            reply_markup=main_menu()
        )

async def check_prayer_time(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.chat_id
    city = job.data['city']
    
    if user_id not in users_db:
        return
    
    current_time = datetime.now().strftime("%H:%M")
    
    times = await get_prayer_times(city)
    if not times:
        return
    
    for prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
        if prayer in times and times[prayer] == current_time:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🕌 *Время намаза {PRAYER_NAMES_RU[prayer]}!*\n\nВставайте на молитву! 🤲",
                parse_mode='Markdown'
            )
            
            if prayer == "Fajr":
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🌅 *Не забудьте прочитать утренние азкары!*\n\nНажмите кнопку ниже 👇",
                    reply_markup=main_menu(),
                    parse_mode='Markdown'
                )
            elif prayer == "Maghrib":
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🌇 *Не забудьте прочитать вечерние азкары!*\n\nНажмите кнопку ниже 👇",
                    reply_markup=main_menu(),
                    parse_mode='Markdown'
                )

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
                for prayer in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                    if prayer in times:
                        text += f"{PRAYER_NAMES_RU[prayer]} — {times[prayer]}\n"
                
                text += f"\n📅 {datetime.now().strftime('%d.%m.%Y')}"
                await query.edit_message_text(text, reply_markup=main_menu(), parse_mode='Markdown')
            else:
                await query.edit_message_text(
                    f"Не удалось получить времена намазов для {city}",
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

async def send_hadith_daily(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if now.hour == 9 and now.minute == 0:
        hadith = HADITHS[now.day % len(HADITHS)]
        for user_id in users_db:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📖 *Хадис дня:*\n\n{hadith}",
                parse_mode='Markdown'
            )

async def send_friday_salawat(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    if now.weekday() == 4 and now.hour in [10, 12, 14, 16, 18] and now.minute == 0:
        salawat = "اللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ 🤍"
        for user_id in users_db:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🤍 *Пятничный салават!*\n\n{salawat}",
                parse_mode='Markdown'
            )

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.job_queue.run_repeating(send_hadith_daily, interval=3600)
    application.job_queue.run_repeating(send_friday_salawat, interval=3600)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_city))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()