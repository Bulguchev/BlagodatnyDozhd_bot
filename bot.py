from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
import requests, datetime, os, re
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = os.getenv("TOKEN")
users = {}

AZKAR_URLS = {
    "Утренние": "https://azkar.ru/morning/",
    "Вечерние": "https://azkar.ru/evening/",
    "После намаза": "https://azkar.ru/after-prayer/",
    "Дуа из Корана": "https://azkar.ru/quran/",
    "Важные дуа": "https://azkar.ru/important/"
}

PRAYER_NAMES = {
    "Fajr": "Фаджр (Утренний намаз)",
    "Dhuhr": "Зухр (Полуденный намаз)",
    "Asr": "Аср (После полудня)",
    "Maghrib": "Магриб (Вечерний намаз)",
    "Isha": "Иша (Ночной намаз)"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаляму алейкум! 🌙\nЯ бот «Благодатный дождь».\n"
        "Напиши свой город (например: Tashkent)\nНапиши 'время', чтобы увидеть все намазы.\nИли нажми /azkar, чтобы открыть азкары."
    )

async def set_city_or_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.chat.id
    if text.lower() == "время":
        if user_id not in users:
            await update.message.reply_text("Сначала укажите свой город.")
            return
        city = users[user_id]
        times = get_prayer_times(city)
        if times:
            msg = "\n".join([f"{PRAYER_NAMES.get(k, k)}: {v}" for k,v in times.items()])
            await update.message.reply_text(f"🕌 Время намазов в {city}:\n{msg}")
        else:
            await update.message.reply_text("Не удалось получить время намазов.")
    else:
        users[user_id] = text
        await update.message.reply_text(f"Город сохранён: {text}\nТеперь я буду присылать напоминания о намазе 🤲")

def get_prayer_times(city):
    try:
        url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
        r = requests.get(url)
        data = r.json()
        return data["data"]["timings"]
    except:
        return {}

def get_azkar(category):
    url = AZKAR_URLS.get(category)
    if not url:
        return "Азкар не найден"
    try:
        r = requests.get(url)
        paragraphs = re.findall(r'<p>(.*?)</p>', r.text, re.DOTALL)
        paragraphs = [re.sub(r'<.*?>', '', p).strip() for p in paragraphs if p.strip()]
        return "\n\n".join(paragraphs) if paragraphs else "Азкар не найден"
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
    await update.message.reply_text("Выберите категорию азкаров:", reply_markup=InlineKeyboardMarkup(keyboard))

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
                await app.bot.send_message(chat_id=user_id, text=f"🕌 Время намаза: {PRAYER_NAMES.get(name, name)}\nПусть Аллах примет твою молитву")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_city_or_time))
app.add_handler(CommandHandler("azkar", azkar_command))
app.add_handler(CallbackQueryHandler(azkar_callback))

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: app.create_task(check_prayers(app)), "interval", minutes=1)
scheduler.start()
app.run_polling()