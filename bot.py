import os
import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = os.getenv("TOKEN")

users = {}

PRAYER_NAMES_RU = {
    "Fajr": "Фаджр",
    "Dhuhr": "Зухр",
    "Asр": "Аср",
    "Asr": "Аср",
    "Maghrib": "Магриб",
    "Isha": "Иша"
}

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

MORNING_TEXT = "🌅 Не забудь прочитать утренние азкары"
EVENING_TEXT = "🌇 Не забудь прочитать вечерние азкары"
ISTIGHFAR_TEXT = "أستغفر الله العظيم"
SALAWAT_TEXT = "اللهم صل على محمد وعلى آل محمد"

def get_prayer_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
    data = requests.get(url).json()
    return data["data"]["timings"]

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Открыть Азкары", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))],
        [InlineKeyboardButton("🕌 Времена намазов", callback_data="times")]
    ])
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📖 Открыть Азкары", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))]
    ]
    
    await update.message.reply_text(
        text="Открыть азкары:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [KeyboardButton("Отправить геолокацию", request_location=True)]
    ]
    await update.message.reply_text(
        "Ассаляму алейкум 🌙\nОтправь геолокацию или напиши город:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        await update.message.reply_text("Напиши название города текстом")
        return

    city = update.message.text.strip()
    users[update.message.chat_id] = city
    await update.message.reply_text(f"Город сохранён: {city}", reply_markup=menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = users.get(query.message.chat_id)

    if query.data == "times":
        times = get_prayer_times(city)
        text = "🕌 Времена намазов:\n\n"
        for k in PRAYERS:
            text += f"{PRAYER_NAMES_RU[k]} — {times[k]}\n"
        await query.message.reply_text(text, reply_markup=menu())

async def scheduler_job(app):
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M")
    weekday = now.weekday()

    for user_id, city in users.items():
        times = get_prayer_times(city)

        for k in PRAYERS:
            if times[k] == time_str:
                await app.bot.send_message(user_id, f"🕌 Время намаза: {PRAYER_NAMES_RU[k]}")

        if times["Fajr"] == time_str:
            await app.bot.send_message(user_id, MORNING_TEXT, reply_markup=menu())

        if times["Maghrib"] == time_str:
            await app.bot.send_message(user_id, EVENING_TEXT, reply_markup=menu())

        if now.minute % 90 == 0:
            await app.bot.send_message(user_id, ISTIGHFAR_TEXT)

        if weekday == 4 and times["Fajr"] <= time_str <= times["Isha"]:
            await app.bot.send_message(user_id, SALAWAT_TEXT)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT | filters.LOCATION, set_city))
app.add_handler(CallbackQueryHandler(buttons))

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: app.create_task(scheduler_job(app)), "interval", minutes=1)
scheduler.start()

app.run_polling()