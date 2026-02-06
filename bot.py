import os
import datetime
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler

# ===== 1. Токен бота =====
TOKEN = os.getenv("TOKEN")  # В Render или Heroku создать переменную окружения TOKEN

# ===== 2. Словарь пользователей =====
users = {}  # {user_id: city}

# ===== 3. Команды бота =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ассаляму алейкум! 🌙\n"
        "Я бот «Благодатный дождь».\n"
        "Напиши свой город (например: Tashkent) для напоминаний о намазе.\n"
        "Или используй команду /azkar, чтобы открыть азкары."
    )

async def set_city_or_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Если пользователь пишет город, сохраняем его для напоминаний.
       Если пишет время, показываем совпадения с намазами."""
    text = update.message.text
    user_id = update.message.chat_id

    if ":" in text:  # пользователь ввел время, например 12:30
        if user_id not in users:
            await update.message.reply_text("Сначала укажите свой город для напоминаний о намазах.")
            return
        city = users[user_id]
        try:
            times = get_prayer_times(city)
            matching = {name: t for name, t in times.items() if t.startswith(text)}
            if matching:
                msg = "\n".join([f"{name}: {t}" for name, t in matching.items()])
            else:
                msg = "Нет совпадений с этим временем."
            await update.message.reply_text(f"В городе {city} совпадения:\n{msg}")
        except:
            await update.message.reply_text("Ошибка получения времени намаза.")
    else:  # пользователь пишет город
        city = text
        users[user_id] = city
        await update.message.reply_text(
            f"Город сохранён: {city}\nТеперь я буду присылать напоминания о намазе 🤲"
        )

# ===== 4. Получение времени намазов с time-namaz.ru =====
def get_prayer_times(city):
    """Парсинг времени намазов с сайта time-namaz.ru"""
    try:
        city_url = city.lower().replace(" ", "-")
        url = f"https://www.time-namaz.ru/{city_url}/"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")  # На сайте таблица с namaz times
        times = {}
        if table:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) == 2:
                    name = cols[0].get_text(strip=True)
                    time = cols[1].get_text(strip=True)
                    times[name] = time
        return times
    except Exception as e:
        print(f"Ошибка при получении намазов для {city}: {e}")
        return {}

async def check_prayers(app):
    now = datetime.datetime.now().strftime("%H:%M")
    for user_id, city in users.items():
        try:
            times = get_prayer_times(city)
            for name, time in times.items():
                if time == now:
                    await app.bot.send_message(
                        chat_id=user_id,
                        text=f"🕌 Время намаза: {name}\nПусть Аллах примет твою молитву"
                    )
        except Exception as e:
            print(f"Ошибка при проверке намаза для {user_id}: {e}")

# ===== 5. Парсер азкаров с azkar.ru =====
def get_azkar(category):
    urls = {
        "morning": "https://azkar.ru/morning/",
        "evening": "https://azkar.ru/evening/",
        "after_prayer": "https://azkar.ru/after-prayer/",
        "quran": "https://azkar.ru/quran/",
        "important": "https://azkar.ru/important/"
    }
    url = urls.get(category)
    if not url:
        return "Ошибка: неизвестная категория"
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        div = soup.find("div", class_="entry-content")
        if not div:
            return "Азкар не найдено :("
        paragraphs = div.find_all("p")
        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs)
        return text[:4000]
    except Exception as e:
        return f"Ошибка при получении азкаров: {e}"

# ===== 6. Web App кнопки =====
async def azkar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Открыть Азкар", web_app=WebAppInfo(url="https://твоя_ссылка_на_index.html"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Нажмите, чтобы открыть мини-приложение с азкарами:", reply_markup=reply_markup)

# ===== 7. Обработка данных из Web App =====
async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.web_app_data.data  # категория
    azkar_text = get_azkar(data)
    await update.message.reply_text(azkar_text)

# ===== 8. Настройка приложения Telegram =====
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_city_or_time))
app.add_handler(CommandHandler("azkar", azkar_menu))
app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_handler))

# ===== 9. Планировщик напоминаний =====
scheduler = BackgroundScheduler()
async def scheduled_job():
    await check_prayers(app)
scheduler.add_job(lambda: app.create_task(scheduled_job()), "interval", minutes=1)
scheduler.start()

# ===== 10. Запуск бота =====
app.run_polling()
