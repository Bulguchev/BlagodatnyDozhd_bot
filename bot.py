import os
import datetime
import asyncio
import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = os.getenv("TOKEN")
USERS_FILE = "users.json"

def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()
bot_instance = None

PRAYER_NAMES = {
    "Fajr": {"emoji": "🌅", "name": "Фаджр (Рассвет)"},
    "Sunrise": {"emoji": "☀️", "name": "Восход"},
    "Dhuhr": {"emoji": "🕌", "name": "Зухр"},
    "Asr": {"emoji": "🌤️", "name": "Аср"},
    "Maghrib": {"emoji": "🌇", "name": "Магриб (Закат)"},
    "Isha": {"emoji": "🌙", "name": "Иша"}
}

def get_prayer_times(city):
    try:
        url = "http://api.aladhan.com/v1/timingsByCity"
        params = {"city": city, "country": "Russia", "method": 3, "school": 0}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data["code"] == 200:
            return data["data"]["timings"], data["data"]["date"]["readable"]
    except:
        pass
    return None, None

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🕌 Время намазов"), KeyboardButton("📖 Открыть Азкары")],
            [KeyboardButton("📍 Изменить город")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def location_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📍 Отправить геолокацию", request_location=True)],
            [KeyboardButton("🏙️ Написать название города")],
            [KeyboardButton("⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    welcome_text = f"""
🕌 *Ассаляму алейкум, {user.first_name}!* 🤲

✨ *Добро пожаловать в бота «Благодатный дождь»!* 🌧️

Я буду напоминать вам о времени намазов точно вовремя.

*Выберите действие:*
"""
    await update.message.reply_text(text=welcome_text, reply_markup=main_menu_keyboard(), parse_mode='Markdown')

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)
    text = update.message.text

    if user_id in users and users[user_id].get("state") == "waiting_city":
        await handle_city_input(update, context)
        return

    if text == "🕌 Время намазов":
        if user_id not in users or "city" not in users[user_id]:
            await ask_for_city(update, context)
        else:
            await show_prayer_times(update, context, user_id)

    elif text == "📖 Открыть Азкары":
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✨ Открыть сборник азкаров", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))]])
        await update.message.reply_text("📖 *Нажмите кнопку ниже, чтобы открыть сборник азкаров:*", reply_markup=inline_kb, parse_mode='Markdown')

    elif text == "📍 Изменить город":
        await ask_for_city(update, context)

async def ask_for_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)
    if user_id not in users:
        users[user_id] = {}
    users[user_id]["state"] = "waiting_location"
    save_users(users)
    await update.message.reply_text("📍 *Укажите ваше местоположение:*", reply_markup=location_menu_keyboard(), parse_mode='Markdown')

async def handle_location_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)
    text = update.message.text

    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {"lat": lat, "lon": lon, "format": "json", "accept-language": "ru"}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            city = data.get("address", {}).get("city") or data.get("address", {}).get("town") or data.get("address", {}).get("village")
            if not city:
                city = "Москва"
        except:
            city = "Москва"
        users[user_id]["city"] = city
        users[user_id]["state"] = "main_menu"
        save_users(users)
        await confirm_city_set(update, context, city)

    elif text == "🏙️ Написать название города":
        users[user_id]["state"] = "waiting_city"
        save_users(users)
        await update.message.reply_text("✍️ *Напишите название города:*", parse_mode='Markdown')

    elif text == "⬅️ Назад":
        users[user_id]["state"] = "main_menu"
        save_users(users)
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())

async def handle_city_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.chat_id)
    city = update.message.text.strip()
    if city:
        users[user_id]["city"] = city
        users[user_id]["state"] = "main_menu"
        save_users(users)
        await confirm_city_set(update, context, city)

async def confirm_city_set(update: Update, context: ContextTypes.DEFAULT_TYPE, city):
    timings, date_info = get_prayer_times(city)
    
    if timings:
        response_text = f"""
✅ *Город сохранен: {city}*
📅 {date_info}

*Точное время намазов:*
"""
        for key, info in PRAYER_NAMES.items():
            if key in timings:
                response_text += f"\n{info['emoji']} *{info['name']}:* `{timings[key]}`"
    else:
        response_text = f"✅ *Город сохранен: {city}*"

    await update.message.reply_text(text=response_text, parse_mode='Markdown')
    await update.message.reply_text("Выберите действие:", reply_markup=main_menu_keyboard())

async def show_prayer_times(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    city = users[user_id]["city"]
    timings, date_info = get_prayer_times(city)
    
    if not timings:
        await update.message.reply_text("⚠️ *Не удалось загрузить расписание.*", parse_mode='Markdown', reply_markup=main_menu_keyboard())
        return
    
    text = f"""
🕌 *Время намазов*
📍 *Город:* {city}
📅 {date_info}

"""
    for key, info in PRAYER_NAMES.items():
        if key in timings:
            text += f"\n{info['emoji']} *{info['name']}:* `{timings[key]}`"
    
    await update.message.reply_text(text=text, parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

async def send_notifications():
    global bot_instance
    if not bot_instance:
        bot_instance = Bot(token=TOKEN)
    
    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M")
    weekday = now.weekday()
    
    for user_id_str, user_data in list(users.items()):
        try:
            if "city" not in user_data:
                continue
                
            city = user_data["city"]
            timings, _ = get_prayer_times(city)
            if not timings:
                continue
            
            for prayer_key in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                if prayer_key in timings:
                    prayer_time = datetime.datetime.strptime(timings[prayer_key], "%H:%M")
                    reminder_time = (prayer_time - datetime.timedelta(minutes=10)).strftime("%H:%M")
                    if current_time == reminder_time:
                        prayer_info = PRAYER_NAMES[prayer_key]
                        await bot_instance.send_message(
                            user_id_str,
                            f"⏰ *Напоминаю:* До намаза {prayer_info['name']} осталось 10 минут!\n\n*Точное время:* `{timings[prayer_key]}`",
                            parse_mode='Markdown'
                        )
            
            for prayer_key in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
                if timings[prayer_key] == current_time:
                    prayer_info = PRAYER_NAMES[prayer_key]
                    await bot_instance.send_message(
                        user_id_str,
                        f"{prayer_info['emoji']} *Точное время намаза {prayer_info['name']}!*\n\n*Время:* `{timings[prayer_key]}`",
                        parse_mode='Markdown'
                    )
            
            if timings["Fajr"] == current_time:
                inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("📖 Открыть азкары", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))]])
                await bot_instance.send_message(
                    user_id_str,
                    "🌅 *Напоминаю об утренних азкарах!*",
                    reply_markup=inline_kb,
                    parse_mode='Markdown'
                )
            
            if timings["Maghrib"] == current_time:
                inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("📖 Открыть азкары", web_app=WebAppInfo(url="https://azkar-app-omega.vercel.app"))]])
                await bot_instance.send_message(
                    user_id_str,
                    "🌇 *Напоминаю о вечерних азкарах!*",
                    reply_markup=inline_kb,
                    parse_mode='Markdown'
                )
            
            current_hour = now.hour
            if 8 <= current_hour <= 22 and now.minute == 0:
                await bot_instance.send_message(
                    user_id_str,
                    "🕋 *АстагфируЛлах аль-Азым аль-лязи ля иляха илля Хуваль-Хаййуль-Кайюм ва атубу иляйхи*",
                    parse_mode='Markdown'
                )
            
            if weekday == 4:
                fajr_time = datetime.datetime.strptime(timings["Fajr"], "%H:%M")
                isha_time = datetime.datetime.strptime(timings["Isha"], "%H:%M")
                current_dt = datetime.datetime.combine(now.date(), now.time())
                
                if fajr_time <= current_dt <= isha_time:
                    await bot_instance.send_message(
                        user_id_str,
                        "🕌 *Аллахумма салли аля Мухаммадин ва аля али Мухаммад*\n\nНапоминаю чаще читать салават Пророку ﷺ.",
                        parse_mode='Markdown'
                    )
                        
        except Exception as e:
            print(f"Ошибка уведомления: {e}")

async def notification_scheduler():
    while True:
        await send_notifications()
        await asyncio.sleep(30)

async def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location_input))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    asyncio.create_task(notification_scheduler())
    
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())