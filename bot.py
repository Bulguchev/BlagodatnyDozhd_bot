from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import requests
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import os

TOKEN = os.getenv("TOKEN")

users = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаляму алейкум! 🌙\n"
        "Я бот «Благодатный дождь».\n"
        "Напиши свой город (например: Tashkent)"
    )

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    user_id = update.message.chat_id
    users[user_id] = city
    await update.message.reply_text(
        f"Город сохранён: {city}\n"
        "Теперь я буду присылать напоминания о намазе 🤲"
    )

def get_prayer_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
    response = requests.get(url)
    data = response.json()
    return data["data"]["timings"]

async def check_prayers(app):
    now = datetime.datetime.now().strftime("%H:%M")
    for user_id, city in users.items():
        times = get_prayer_times(city)
        for name, time in times.items():
            if time == now:
                await app.bot.send_message(
                    chat_id=user_id,
                    text=f"🕌 Время намаза: {name}\nПусть Аллах примет твою молитву"
                )

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, set_city))

scheduler = BackgroundScheduler()

async def scheduled_job():
    await check_prayers(app)

scheduler.add_job(lambda: app.create_task(scheduled_job()), "interval", minutes=1)
scheduler.start()

app.run_polling()
