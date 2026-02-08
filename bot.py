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
    "Asr": "Аср",
    "Maghrib": "Магриб",
    "Isha": "Иша"
}

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

MORNING_TEXT = "🌅 Не забудь прочитать утренние азкары"
EVENING_TEXT = "🌇 Не забудь прочитать вечерние азкары"
ISTIGHFAR_TEXT = "أستغفر الله العظيم"
SALAWAT_TEXT = "اللهم صل على محمد وعلى آل محمد"

AZKAR_URL = "https://blagodat-app.vercel.app"

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Город", callback_data="city")],
        [InlineKeyboardButton("📖 Открыть Азкары", web_app=WebAppInfo(url=https://azkar-app-omega.onrender.com))],
        [InlineKeyboardButton("🕌 Времена намазов", callback_data="times")]
    ])

def city_menu():
    kb = [
        [KeyboardButton("📍 Отправить геолокацию", request_location=True)],
        [KeyboardButton("⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_prayer_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
    data = requests.get(url).json()
    return data["data"]["timings"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаляму алейкум 🌙\nЯ бот «Благодатный дождь»",
        reply_markup=main_menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "city":
        await query.message.reply_text(
            "Отправь геолокацию или напиши город:",
            reply_markup=city_menu()
        )

    if query.data == "times":
        city = users.get(query.message.chat_id)
        if not city:
            await query.message.reply_text("Сначала укажи город")
            return

        times = get_prayer_times(city)
        text = "🕌 Времена намазов:\n\n"
        for k in PRAYERS:
            text += f"{PRAYER_NAMES_RU[k]} — {times[k]}\n"
        await query.message.reply_text(text, reply_markup=main_menu())

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text("Главное меню", reply_markup=main_menu())
        return

    if update.message.location:
        await update.message.reply_text("Напиши название города текстом")
        return

    city = update.message.text.strip()
    users[update.message.chat_id] = city
    await update.message.reply_text(
        f"Город сохранён: {city}",
        reply_markup=main_menu()
    )

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
            await app.bot.send_message(user_id, MORNING_TEXT, reply_markup=main_menu())

        if times["Maghrib"] == time_str:
            await app.bot.send_message(user_id, EVENING_TEXT, reply_markup=main_menu())

        if now.minute % 90 == 0:
            await app.bot.send_message(user_id, ISTIGHFAR_TEXT)

        if weekday == 4 and times["Fajr"] <= time_str <= times["Isha"]:
            await app.bot.send_message(user_id, SALAWAT_TEXT)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT | filters.LOCATION, set_city))

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: app.create_task(scheduler_job(app)), "interval", minutes=1)
scheduler.start()

app.run_polling()