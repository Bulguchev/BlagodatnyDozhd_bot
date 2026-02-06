from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import requests
import datetime
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = "8298951678:AAGHWFexDQXoNCLyWOcR7_DL1XkZFRA_B-E"

users = {}

# Старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаляму алейкум! 🌙\n"
        "Я бот «Благодатный дождь».\n"
        "Напиши свой город (например: Tashkent)"
    )

# Получаем город
async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    user_id = update.message.chat_id
    users[user_id] = city
    await update.message.reply_text(
        f"Город сохранён: {city}\n"
        "Теперь я буду присылать напоминания о намазе 🤲"
    )

# Получаем времена намаза
def get_prayer_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
    response = requests.get(url)
    data = response.json()
    return data["data"]["timings"]

# Проверяем время каждую минуту
async def check_prayers(context):
    now = datetime.datetime.now().strftime("%H:%M")
    for user_id, city in users.items():
        times = get_prayer_times(city)
        for name, time in times.items():
            if time == now:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🕌 Время намаза: {name}\nПусть Аллах примет твою молитву"
                )

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, set_city))

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: app.create_task(check_prayers(None)), "interval", minutes=1)
scheduler.start()

app.run_polling()