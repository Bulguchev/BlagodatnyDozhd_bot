from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
import requests, datetime, os
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = os.getenv("TOKEN")
users = {}
azkar_pages = {}
hadis_index = 0

PRAYER_NAMES = {
    "Fajr": "🌅 Фаджр (Утренний намаз)",
    "Dhuhr": "🕌 Зухр (Полуденный намаз)",
    "Asr": "🕋 Аср (После полудня)",
    "Maghrib": "🌇 Магриб (Вечерний намаз)",
    "Isha": "🌙 Иша (Ночной намаз)"
}

AZKAR_TEXTS = {
    "Утренние": [
        "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ\nAsbahna wa asbaha al-mulku lillah\nМы вступили в утро, и вся власть принадлежит Аллаху\n" + "―"*30,
        "اللَّهُمَّ بِكَ أَصْبَحْنَا وَبِكَ أَمْسَيْنَا\nAllahumma bika asbahna wa bika amsayna\nО Аллах! С Тобой мы вступили в утро и вечер\n" + "―"*30
    ],
    "Вечерние": [
        "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ\nAmsayna wa amsa al-mulku lillah\nМы вступили в вечер, и вся власть принадлежит Аллаху\n" + "―"*30,
        "اللَّهُمَّ بِكَ أَمْسَيْنَا وَبِكَ أَصْبَحْنَا\nAllahumma bika amsayna wa bika asbahna\nО Аллах! С Тобой мы вступили в вечер и утро\n" + "―"*30
    ],
    "После намаза": [
        "سُبْحَانَ اللَّهِ وَالْحَمْدُ لِلَّهِ\nSubhanallah wa alhamdulillah\nПречист Аллах, хвала Аллаху\n" + "―"*30
    ],
    "Дуа из Корана": [
        "رَبَّنَا لَا تُؤَاخِذْنَا إِن نَسِينَا أَوْ أَخْطَأْنَا\nRabbana la tu-akhidhna in nasina aw akhta\nГосподь наш! Не наказывай нас, если мы забыли или ошиблись\n" + "―"*30
    ],
    "Важные дуа": [
        "اللَّهُمَّ اهْدِنَا فِيْمَا أَخْتُلِفَ فِيهِ\nAllahumma ihdina fima akhtulifa fih\nО Аллах! Направь нас в том, в чем мы расходились\n" + "―"*30
    ]
}

HADIS = [
    "Хадис 1: Кто говорит «Субханаллах» сто раз, тому прощаются грехи.",
    "Хадис 2: Кто читает утренние и вечерние азкары, того оберегает Аллах.",
    "Хадис 3: Кто приветствует салаватом Пророка ﷺ, получает вознаграждение."
]

SALAWAT = "اللهم صل على محمد\nAllahumma salli ala Muhammad"

def get_azkar_pages(category):
    texts = AZKAR_TEXTS.get(category, ["Азкар не найден"])
    return [t for t in texts]

def build_keyboard(category, page, total):
    keyboard = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"{category}|{page-1}"))
    if page < total-1:
        nav.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"{category}|{page+1}"))
    if nav:
        keyboard.append(nav)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

async def azkar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("☀️ Утренние", callback_data="Утренние|0")],
        [InlineKeyboardButton("🌇 Вечерние", callback_data="Вечерние|0")],
        [InlineKeyboardButton("🕌 После намаза", callback_data="После намаза|0")],
        [InlineKeyboardButton("📖 Дуа из Корана", callback_data="Дуа из Корана|0")],
        [InlineKeyboardButton("❗ Важные дуа", callback_data="Важные дуа|0")]
    ]
    await update.message.reply_text("Выберите категорию азкаров:", reply_markup=InlineKeyboardMarkup(keyboard))

async def azkar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category, page_str = query.data.split("|")
    page = int(page_str)
    key = f"{query.message.chat.id}_{category}"
    if key not in azkar_pages:
        azkar_pages[key] = get_azkar_pages(category)
    pages = azkar_pages[key]
    text = f"{category} ({page+1}/{len(pages)})\n\n{pages[page]}"
    reply_markup = build_keyboard(category, page, len(pages))
    await query.message.edit_text(text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаляму алейкум! 🌙\n"
        "Я бот «Благодатный дождь».\n"
        "Напишите свой город (например: Tashkent)\n"
        "Напишите 'время', чтобы увидеть намазы.\n"
        "Или нажмите /azkar, чтобы открыть азкары."
    )

async def set_city_or_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.message.chat.id
    if text.lower() == "время":
        if uid not in users:
            await update.message.reply_text("Сначала укажите город.")
            return
        city = users[uid]
        times = get_prayer_times(city)
        if times:
            msg = "\n".join([f"{PRAYER_NAMES.get(k,k)}: {v}" for k,v in times.items()])
            await update.message.reply_text(f"🕌 Время намазов в {city}:\n{msg}")
        else:
            await update.message.reply_text("Не удалось получить намазы.")
    else:
        users[uid] = text
        await update.message.reply_text(f"Город сохранён: {text}")

def get_prayer_times(city):
    try:
        url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
        r = requests.get(url)
        return r.json()["data"]["timings"]
    except:
        return {}

async def check_prayers(app):
    now = datetime.datetime.now().strftime("%H:%M")
    for uid, city in users.items():
        times = get_prayer_times(city)
        if not times:
            continue
        if now == times.get("Fajr"):
            await app.bot.send_message(chat_id=uid, text="🌅 Время Фаджр! Не забудьте прочитать утренние азкары.")
        if now == times.get("Maghrib"):
            await app.bot.send_message(chat_id=uid, text="🌇 Время Магриб! Не забудьте прочитать вечерние азкары.")

async def daily_hadis(app):
    global hadis_index
    for uid in users.keys():
        await app.bot.send_message(chat_id=uid, text=f"📜 Хадис на сегодня:\n{HADIS[hadis_index]}")
    hadis_index = (hadis_index + 1) % len(HADIS)

async def friday_salawat(app):
    now = datetime.datetime.now()
    if now.weekday() != 4:
        return
    for uid in users.keys():
        await app.bot.send_message(chat_id=uid, text=f"🌹 Салават на Пророка ﷺ:\n{SALAWAT}")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_city_or_time))
app.add_handler(CommandHandler("azkar", azkar_command))
app.add_handler(CallbackQueryHandler(azkar_callback))

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: app.create_task(check_prayers(app)), "interval", minutes=1)
scheduler.add_job(lambda: app.create_task(daily_hadis(app)), "cron", hour=9, minute=0)
for hour in range(8, 18):
    scheduler.add_job(lambda h=hour: app.create_task(friday_salawat(app)), "cron", day_of_week="fri", hour=hour, minute=0)
scheduler.start()

app.run_polling()