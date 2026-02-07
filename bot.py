from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import requests
import datetime
import os
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = os.getenv("TOKEN")

# ---------------- ДАННЫЕ ----------------

users = {}          # user_id -> city
current_index = {}  # user_id -> index

PRAYER_NAMES_RU = {
    "Fajr": "Фаджр",
    "Dhuhr": "Зухр",
    "Asr": "Аср",
    "Maghrib": "Магриб",
    "Isha": "Иша"
}

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

MORNING_AZKAR = [
    {
        "title": "Утренний зикр 1",
        "arabic": "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ",
        "translit": "Asbahna wa asbahal-mulku lillah",
        "ru": "Мы встретили утро, и власть принадлежит Аллаху"
    },
    {
        "title": "Утренний зикр 2",
        "arabic": "اللّهـمَّ بِكَ أَصْـبَحْنا",
        "translit": "Allahumma bika asbahna",
        "ru": "О Аллах, с Тобой мы встретили утро"
    }
]

EVENING_AZKAR = [
    {
        "title": "Вечерний зикр 1",
        "arabic": "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ",
        "translit": "Amsayna wa amsal-mulku lillah",
        "ru": "Мы встретили вечер, и власть принадлежит Аллаху"
    }
]

HADITHS = [
    "Дела оцениваются по намерениям. (Бухари, Муслим)",
    "Лучшие из вас — лучшие по нраву. (Бухари)",
    "Аллах любит мягкость во всех делах. (Муслим)"
]

SALAWAT_TEXT = "اللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ 🤍"

# ---------------- API ----------------

def get_prayer_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"
    data = requests.get(url).json()
    return data["data"]["timings"]

# ---------------- ВСПОМОГАТЕЛЬНОЕ ----------------

def build_azkar_message(azkar_list, index):
    item = azkar_list[index]
    return (
        f"📿 {item['title']}\n\n"
        f"{item['arabic']}\n\n"
        f"{item['translit']}\n\n"
        f"{item['ru']}\n\n"
        f"{index+1}/{len(azkar_list)}"
    )

def azkar_keyboard(category):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️", callback_data=f"{category}_prev"),
            InlineKeyboardButton("➡️", callback_data=f"{category}_next")
        ],
        [
            InlineKeyboardButton("🏠 Меню", callback_data="menu")
        ]
    ])

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 Утренние азкары", callback_data="morning")],
        [InlineKeyboardButton("🌇 Вечерние азкары", callback_data="evening")],
        [InlineKeyboardButton("📖 Хадис дня", callback_data="hadith")],
        [InlineKeyboardButton("🕌 Времена намазов", callback_data="times")]
    ])

# ---------------- КОМАНДЫ ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаляму алейкум 🌙\n"
        "Я бот «Благодатный дождь».\n\n"
        "Напиши свой город (например: Tashkent)"
    )

async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    user_id = update.message.chat_id
    users[user_id] = city
    current_index[user_id] = 0

    await update.message.reply_text(
        f"Город сохранён: {city}\n\nВыбери раздел:",
        reply_markup=main_menu()
    )

# ---------------- КНОПКИ ----------------

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.message.chat_id

    if user_id not in current_index:
        current_index[user_id] = 0

    idx = current_index[user_id]
    city = users.get(user_id)

    if query.data == "menu":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu())

    elif query.data == "morning":
        text = build_azkar_message(MORNING_AZKAR, idx)
        await query.edit_message_text(text, reply_markup=azkar_keyboard("morning"))

    elif query.data == "evening":
        text = build_azkar_message(EVENING_AZKAR, idx)
        await query.edit_message_text(text, reply_markup=azkar_keyboard("evening"))

    elif query.data == "hadith":
        hadith = HADITHS[datetime.datetime.now().day % len(HADITHS)]
        await query.edit_message_text(f"📖 Хадис дня:\n\n{hadith}", reply_markup=main_menu())

    elif query.data == "times":
        times = get_prayer_times(city)
        text = "🕌 Времена намазов:\n\n"
        for key in PRAYERS:
            text += f"{PRAYER_NAMES_RU[key]} — {times[key]}\n"
        await query.edit_message_text(text, reply_markup=main_menu())

    elif query.data.endswith("_next"):
        current_index[user_id] = (idx + 1) % len(MORNING_AZKAR)
        await query.edit_message_text(
            build_azkar_message(MORNING_AZKAR, current_index[user_id]),
            reply_markup=azkar_keyboard("morning")
        )

    elif query.data.endswith("_prev"):
        current_index[user_id] = (idx - 1) % len(MORNING_AZKAR)
        await query.edit_message_text(
            build_azkar_message(MORNING_AZKAR, current_index[user_id]),
            reply_markup=azkar_keyboard("morning")
        )

# ---------------- ПЛАНИРОВЩИК ----------------

async def scheduler_job(app):
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M")
    weekday = now.weekday()  # 4 = пятница

    for user_id, city in users.items():
        times = get_prayer_times(city)

        # Все 5 намазов
        for key in PRAYERS:
            if times[key] == time_str:
                ru_name = PRAYER_NAMES_RU[key]
                await app.bot.send_message(
                    chat_id=user_id,
                    text=f"🕌 Время намаза: {ru_name}\nПусть Аллах примет твою молитву 🤲"
                )

        # Фаджр → утренние
        if times["Fajr"] == time_str:
            text = build_azkar_message(MORNING_AZKAR, 0)
            await app.bot.send_message(chat_id=user_id, text="🌅 Утренние азкары:\n\n" + text)

        # Магриб → вечерние
        if times["Maghrib"] == time_str:
            text = build_azkar_message(EVENING_AZKAR, 0)
            await app.bot.send_message(chat_id=user_id, text="🌇 Вечерние азкары:\n\n" + text)

        # Хадис дня
        if time_str == "09:00":
            hadith = HADITHS[now.day % len(HADITHS)]
            await app.bot.send_message(chat_id=user_id, text="📖 Хадис дня:\n\n" + hadith)

        # Пятничный салават
        if weekday == 4 and time_str in ["10:00", "12:00", "14:00", "16:00", "18:00"]:
            await app.bot.send_message(chat_id=user_id, text="🤍 Пятничный салават:\n" + SALAWAT_TEXT * 10)

# ---------------- ЗАПУСК ----------------

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_city))
app.add_handler(CallbackQueryHandler(buttons))

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: app.create_task(scheduler_job(app)), "interval", minutes=1)
scheduler.start()

app.run_polling()