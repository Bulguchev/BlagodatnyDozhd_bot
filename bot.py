from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import requests
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import os

TOKEN = os.getenv("TOKEN")
users = {}

AZKAR_URLS = {
    "Утренние": "https://azkar.ru/morning/",
    "Вечерние": "https://azkar.ru/evening/",
    "После намаза": "https://azkar.ru/after-prayer/",
    "Дуа из Корана": "https://azkar.ru/quran/",
    "Важные дуа": "https://azkar.ru/important/"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаляму алейкум! 🌙\n"
        "Я бот «Благодатный дождь».\n"
        "Напиши свой город (например: Tashkent)\n"
        "Напиши 'время', чтобы увидеть все намазы.\n"
        "Или нажми /azkar, чтобы открыть азкары."
    )

async def set_city_or_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.chat_id

    if text.lower() == "время":
        if user_id not in users:
            await update.message.reply_text("Сначала укажите свой город.")
            return
        city = users[user_id]
        times = get_prayer_times(city)
        if times:
            msg = "\n".join([f"{name}: {time}" for name, time in times.items()])
            await update.message.reply_text(f"🕌 Время намазов в {city}:\n{msg}")
        else:
            await update.message.reply_text("Не удалось получить время намазов для вашего города.")
    else:
        users[user_id] = text
        await update.message.reply_text(f"Город сохранён: {text}\nТеперь я буду присылать напоминания о намазе 🤲")

def get_prayer_times(city):
    try:
        url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
        response = requests.get(url)
        data = response.json()
        return data["data"]["timings"]
    except:
        return {}

def get_azkar(category):
    url = AZKAR_URLS.get(category)
    if not url:
        return "Азкар не найден"
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        div = soup.find("div", class_="entry-content")
        if not div:
            return "Азкар не найден"
        paragraphs = div.find_all("p")
        return "\n\n".join(p.get_text(strip=True) for p in paragraphs)[:4000]
    except:
        return "Ошибка при получении азкаров"

async def azkar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌅 Утренние", callback_data="Утренние")],
        [InlineKeyboardButton("🌙 Вечерние", callback_data="Вечерние")],
        [InlineKeyboardButton("🕌 После намаза", callback_data="После намаза")],
        [InlineKeyboardButton("📖 Дуа из Корана", callback_data="Дуа из Корана")],
        [InlineKeyboardButton("❗ Важные дуа", callback_data="Важные дуа")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите категорию азкаров:", reply_markup=reply_markup)

async def azkar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = get_azkar(query.data)
    await query.message.reply_text(text)

async def check_prayers(app):
    now = datetime.datetime.now().strftime("%H:%M")
    for user_id, city in users.items():
        times = get_prayer_times(city)
        for name, time in times.items():
            if time == now:
                await app.bot.send_message(chat_id=user_id, text=f"🕌 Время намаза: {name}\nПусть Аллах примет твою молитву")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_city_or_time))
app.add_handler(CommandHandler("azkar", azkar_command))
app.add_handler(CallbackQueryHandler(azkar_callback))

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: app.create_task(check_prayers(app)), "interval", minutes=1)
scheduler.start()

app.run_polling()
