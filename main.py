from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import BadRequest, Forbidden
import json
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import logging
import re

load_dotenv()

SUBSCRIBERS_FILE = "subscribers.json"
PENDING_FILE = "pending_accounts.json"
ACCOUNTS_FILE = "accounts.json"
SKINS_FILE = "skins.json"
CONFIG_FILE = "config.json"
VISITS_FILE = "visits.json"
ERROR_LOG = "errors.log"

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

logging.basicConfig(filename=ERROR_LOG, level=logging.ERROR, format='%(asctime)s %(message)s')

def load_json(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_visits():
    raw = load_json(VISITS_FILE)
    return {date: set(users) for date, users in raw.items()}

def save_visits(visits):
    serializable = {date: list(users) for date, users in visits.items()}
    save_json(VISITS_FILE, serializable)

def log_visit(user_id):
    visits = load_visits()
    today = datetime.now().strftime("%Y-%m-%d")
    visits.setdefault(today, set()).add(user_id)
    save_visits(visits)

config = load_json(CONFIG_FILE)
if not config:
    config = {
        "newyear": False,
        "skin_balance": 0.0,
        "discount_accounts": 0,
        "discount_skins": 0,
        "discount_usernames": 0,
        "menu_media": {}
    }
    save_json(CONFIG_FILE, config)

RUB_RATE = 74

subscribers = set(load_json(SUBSCRIBERS_FILE))
pending_accounts = load_json(PENDING_FILE)
accounts_for_sale = load_json(ACCOUNTS_FILE)
skins_catalog = load_json(SKINS_FILE)

user_languages = {}
user_states = {}
user_drafts = {}

USERNAME_ITEMS = [
    ("@pepecollectors", 200),
    ("@DateHappy", 15),
    ("@noggano444", 15),
    ("@mokrivskiylox", 50),
]

TEXTS = {
    "add_account": {"ru": "📥 Опубликовать аккаунт", "en": "📥 Post account"},
    "add_skin": {"ru": "🔫 Добавить скин", "en": "🔫 Add skin"},
    "enter_skin_title": {"ru": "✍️ Введите название скина:", "en": "✍️ Enter skin title:"},
    "enter_skin_photo": {"ru": "📷 Отправьте фото скина:", "en": "📷 Send skin photo:"},
    "enter_skin_desc": {"ru": "📘 Отправьте описание скина:", "en": "📘 Send skin description:"},
    "enter_skin_price": {"ru": "💰 Введите цену в USDT:", "en": "💰 Enter price in USDT:"},
    "skin_added": {"ru": "✅ Скин добавлен в каталог!", "en": "✅ Skin added to catalog!"},
    "skins_empty": {"ru": "🔫 Пока скинов на продажу нет.", "en": "🔫 No skins for sale yet."},
    "skins": {"ru": "🔫 Скины CS2/Dota 2", "en": "🔫 CS2/Dota 2 Skins"},
    "enter_title": {"ru": "✍️ Введите название аккаунта:", "en": "✍️ Enter account title:"},
    "enter_photo": {"ru": "📷 Отправьте до 10 фотографий аккаунта:", "en": "📷 Send up to 10 photos:"},
    "enter_desc": {"ru": "📘 Отправьте описание аккаунта:", "en": "📘 Send account description:"},
    "enter_price": {"ru": "💰 Введите цену в USDT:", "en": "💰 Enter price in USDT:"},
    "sent_for_review": {"ru": "⏳ Отправлено на модерацию. Ожидайте уведомления.", "en": "⏳ Sent for moderation. Please wait."},
    "choose_language": {"ru": "🌐 Выберите язык / Choose language:", "en": "🌐 Choose language / Выберите язык:"},
    "greeting": {"ru": "🏪 Добро пожаловать в маркетплейс!\n\nВыберите категорию ниже:", "en": "🏪 Welcome to the marketplace!\n\nChoose a category below:"},
    "back": {"ru": "🔙 Назад", "en": "🔙 Back"},
    "contact_seller": {"ru": "👨‍💻 Связаться", "en": "👨‍💻 Contact"},
    "usernames": {"ru": "💎 Юзернеймы", "en": "💎 Usernames"},
    "wardrobe": {"ru": "💼 Заказ скинов", "en": "💼 Order skins"},
    "tg_username": {"ru": "👱 Доступные юзернеймы", "en": "👱 Available usernames"},
}

if config["newyear"]:
    TEXTS["greeting"]["ru"] = "🎄 С Новым годом! Добро пожаловать в маркетплейс! 🎄"
    TEXTS["greeting"]["en"] = "🎄 Happy New Year! Welcome to the marketplace! 🎄"

def apply_discount(price_usdt, discount):
    return round(price_usdt * (1 - discount / 100), 2) if discount else price_usdt

def format_price(price_usdt, lang, category="accounts"):
    discount = config.get(f"discount_{category}", 0)
    price = apply_discount(price_usdt, discount)
    return f"{int(price * RUB_RATE)} RUB" if lang == "ru" else f"{price} USDT"

def language_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]])

def main_menu(lang):
    keyboard = []
    for acc_id, acc in accounts_for_sale.items():
        title = acc["title"] if isinstance(acc["title"], str) else acc["title"].get(lang, list(acc["title"].values())[0])
        keyboard.append([InlineKeyboardButton(f"📦 {title}", callback_data=f"show_{acc_id}")])
    if skins_catalog:
        keyboard.append([InlineKeyboardButton(TEXTS["skins"][lang], callback_data="skins_catalog")])
    keyboard.append([InlineKeyboardButton(TEXTS["usernames"][lang], callback_data="usernames")])
    keyboard.append([InlineKeyboardButton(TEXTS["wardrobe"][lang], callback_data="wardrobe")])
    keyboard.append([InlineKeyboardButton(TEXTS["add_account"][lang], callback_data="add_account")])
    return InlineKeyboardMarkup(keyboard)

def skins_menu(lang):
    if not skins_catalog:
        return None
    keyboard = []
    for skin_id, skin in skins_catalog.items():
        title = skin["title"] if isinstance(skin["title"], str) else skin["title"].get(lang, list(skin["title"].values())[0])
        keyboard.append([InlineKeyboardButton(f"🔫 {title}", callback_data=f"skin_{skin_id}")])
    keyboard.append([InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def tg_username(lang):
    keyboard = []
    for uname, base_price in USERNAME_ITEMS:
        label = f"💎 {uname}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"uname_{uname[1:]}")])
    keyboard.append([InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def csdota_wardrobe(lang):
    keyboard = [
        [InlineKeyboardButton("🎯 Counter-Strike 2", callback_data="order_cs2")],
        [InlineKeyboardButton("🦸 Dota 2", callback_data="order_dota2")],
        [InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def account_buttons(lang, author_link=None):
    keyboard = [[InlineKeyboardButton(TEXTS["contact_seller"][lang], url=author_link or "https://t.me/balenciaga_telegram")]]
    keyboard.append([InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_visit(user_id)
    if user_id not in subscribers:
        subscribers.add(user_id)
        save_json(SUBSCRIBERS_FILE, list(subscribers))
    if user_id not in user_languages:
        await update.message.reply_text(TEXTS["choose_language"]["ru"], reply_markup=language_keyboard())
    else:
        lang = user_languages[user_id]
        await update.message.reply_text(TEXTS["greeting"][lang], reply_markup=main_menu(lang))

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_languages.get(update.effective_user.id, "ru")
    text = {"ru": "🏪 *Цифровой Маркетплейс*\n\nЗдесь вы можете безопасно покупать и продавать игровые аккаунты, уникальные юзернеймы и скины.",
            "en": "🏪 *Digital Marketplace*\n\nHere you can safely buy and sell game accounts, unique usernames, and skins."}
    await update.message.reply_text(text[lang], parse_mode="Markdown")

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Ваш Telegram ID: `{update.effective_user.id}`", parse_mode="Markdown")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("🔄 Бот перезапускается...")
    await asyncio.sleep(1)
    os._exit(0)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: /broadcast <текст>")
        return
    text = " ".join(context.args)
    sent = 0
    failed = 0
    for uid in list(subscribers):
        try:
            await context.bot.send_message(uid, text)
            sent += 1
        except Forbidden:
            subscribers.discard(uid)
            failed += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)
    if failed > 0:
        save_json(SUBSCRIBERS_FILE, list(subscribers))
    await update.message.reply_text(f"Рассылка завершена. Отправлено: {sent}, Заблокировали: {failed}")

async def moderation_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    data = query.data
    if data.startswith("approve_"):
        acc_id = data.split("_")[1]
        acc = pending_accounts.pop(acc_id, None)
        if acc:
            accounts_for_sale[acc_id] = {
                "title": acc["title"],
                "photos": acc["photos"],
                "description": acc["description"],
                "price_usdt": acc["price_usdt"],
                "author": f"https://t.me/{acc['username']}" if acc.get("username") else None
            }
            save_json(ACCOUNTS_FILE, accounts_for_sale)
            save_json(PENDING_FILE, pending_accounts)
            await context.bot.send_message(acc["user_id"], "✅ Аккаунт опубликован!")
            await query.message.delete()
    elif data.startswith("reject_"):
        acc_id = data.split("_")[1]
        context.user_data["reject_id"] = acc_id
        await query.message.reply_text("🚫 Причина отказа:")

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    data = query.data if query.data else None
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("Доступ запрещён.")
        return

    if data == "toggle_ny":
        config["newyear"] = not config["newyear"]
        save_json(CONFIG_FILE, config)
        await query.answer("Новогоднее оформление " + ("включено" if config["newyear"] else "выключено"))

    if data == "set_balance":
        context.user_data["set_balance"] = True
        await query.message.reply_text("Введите новый баланс в USDT:")
        return

    if data == "visits":
        visits = load_visits()
        report = "Отчёт посещаемости:\n"
        for date in sorted(visits.keys(), reverse=True)[:30]:
            report += f"{date}: {len(visits[date])} уникальных\n"
        await query.message.reply_text(report or "Нет данных")
        return

    if data == "errors":
        if os.path.exists(ERROR_LOG):
            with open(ERROR_LOG, "r", encoding="utf-8") as f:
                log_content = f.read()[-2000:]
            await query.message.reply_text(f"Последние ошибки:\n{log_content}" or "Нет ошибок")
        else:
            await query.message.reply_text("Лог пуст")
        return

    if data == "discounts":
        context.user_data["set_discount"] = True
        await query.message.reply_text("Введите скидку для аккаунтов скинов юзернеймов через пробел (в %):")
        return

    if data == "add_skin":
        user_states[query.from_user.id] = "skin_title"
        user_drafts[query.from_user.id] = {"photos": []}
        await query.message.reply_text(TEXTS["enter_skin_title"]["ru"])
        return

    kb = [
        [InlineKeyboardButton(f"Новогоднее: {'ВКЛ' if config['newyear'] else 'ВЫКЛ'}", callback_data="toggle_ny")],
        [InlineKeyboardButton(f"Баланс скинов: {config['skin_balance']} USDT", callback_data="set_balance")],
        [InlineKeyboardButton("Отчёт посещаемости", callback_data="visits")],
        [InlineKeyboardButton("Логи ошибок", callback_data="errors")],
        [InlineKeyboardButton(f"Скидки: Акк {config['discount_accounts']}%, Скины {config['discount_skins']}%, Юз {config['discount_usernames']}%", callback_data="discounts")],
        [InlineKeyboardButton(TEXTS["add_skin"]["ru"], callback_data="add_skin")],
        [InlineKeyboardButton(TEXTS["back"]["ru"], callback_data="back")]
    ]
    current_time = datetime.now().strftime("%H:%M:%S")
    text = f"🔧 Админ-панель\nОбновлено: {current_time}"
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    except BadRequest as e:
        if "not modified" in str(e).lower():
            await query.answer("Панель уже актуальна")
        else:
            logging.error(f"Admin panel error: {e}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    kb = [
        [InlineKeyboardButton(f"Новогоднее: {'ВКЛ' if config['newyear'] else 'ВЫКЛ'}", callback_data="toggle_ny")],
        [InlineKeyboardButton(f"Баланс скинов: {config['skin_balance']} USDT", callback_data="set_balance")],
        [InlineKeyboardButton("Отчёт посещаемости", callback_data="visits")],
        [InlineKeyboardButton("Логи ошибок", callback_data="errors")],
        [InlineKeyboardButton(f"Скидки: Акк {config['discount_accounts']}%, Скины {config['discount_skins']}%, Юз {config['discount_usernames']}%", callback_data="discounts")],
        [InlineKeyboardButton(TEXTS["add_skin"]["ru"], callback_data="add_skin")],
        [InlineKeyboardButton(TEXTS["back"]["ru"], callback_data="back")]
    ]
    current_time = datetime.now().strftime("%H:%M:%S")
    text = f"🔧 Админ-панель\nОбновлено: {current_time}"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    lang = user_languages.get(user_id, "ru")

    if data.startswith("lang_"):
        user_languages[user_id] = data[5:]
        await query.edit_message_text(TEXTS["greeting"][data[5:]], reply_markup=main_menu(data[5:]))
        return

    if data == "add_account":
        user_states[user_id] = "title"
        user_drafts[user_id] = {"photos": []}
        await query.message.reply_text(TEXTS["enter_title"][lang])
        return

    if data == "skins_catalog":
        menu = skins_menu(lang)
        if menu is None:
            await query.edit_message_text(TEXTS["skins_empty"][lang])
        else:
            await query.edit_message_text(TEXTS["skins"][lang], reply_markup=menu)
        return

    if data.startswith("skin_"):
        skin_id = data[5:]
        skin = skins_catalog.get(skin_id)
        if not skin:
            return
        photos = skin["photos"]
        price_str = format_price(skin.get("price_usdt", 0), lang, "skins")
        desc = skin["description"].get(lang, skin["description"]) if isinstance(skin["description"], dict) else skin["description"]
        desc_with_price = f"{desc}\n\n💰 Цена: {price_str}"
        author = skin.get("author")
        try:
            await query.message.delete()
        except:
            pass
        if len(photos) == 1:
            await context.bot.send_photo(query.message.chat_id, photos[0], caption=desc_with_price, reply_markup=account_buttons(lang, author))
        else:
            media = [InputMediaPhoto(p, caption=desc_with_price if i == 0 else "") for i, p in enumerate(photos)]
            await context.bot.send_media_group(query.message.chat_id, media)
            await context.bot.send_message(query.message.chat_id, "📍 Кнопки:", reply_markup=account_buttons(lang, author))
        return

    if data == "back":
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(query.message.chat_id, TEXTS["greeting"][lang], reply_markup=main_menu(lang))
        return

    if data.startswith("show_"):
        acc_id = data[5:]
        acc = accounts_for_sale.get(acc_id)
        if not acc:
            return
        photos = acc["photos"]
        price_str = format_price(acc.get("price_usdt", 0), lang)
        desc = acc["description"].get(lang, acc["description"]) if isinstance(acc["description"], dict) else acc["description"]
        desc_with_price = f"{desc}\n\n💰 Цена: {price_str}"
        author = acc.get("author")
        try:
            await query.message.delete()
        except:
            pass
        if len(photos) == 1:
            await context.bot.send_photo(query.message.chat_id, photos[0], caption=desc_with_price, reply_markup=account_buttons(lang, author))
        else:
            media = [InputMediaPhoto(p, caption=desc_with_price if i == 0 else "") for i, p in enumerate(photos)]
            await context.bot.send_media_group(query.message.chat_id, media)
            await context.bot.send_message(query.message.chat_id, "📍 Кнопки:", reply_markup=account_buttons(lang, author))
        return

    if data.startswith("uname_"):
        uname = data[6:]
        item = next((i for i in USERNAME_ITEMS if i[0][1:] == uname), None)
        if item:
            price_str = format_price(item[1], lang, "usernames")
            text = f"💎 {item[0]}\n\n💰 Цена: {price_str}\nСсылка: https://t.me/{uname}"
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(query.message.chat_id, text, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Купить", url="https://t.me/balenciaga_telegram")],
                [InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")]
            ]))
        return

    if data in ("order_cs2", "order_dota2"):
        game = "CS2" if data == "order_cs2" else "Dota 2"
        user_states[user_id] = "skin_link"
        user_drafts[user_id] = {"game": game}
        await query.message.reply_text(f"Отправьте ссылку на предмет в Steam ({game}):")
        return

    if data == "usernames":
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(query.message.chat_id, "💎 Юзернеймы:", reply_markup=tg_username(lang))
        return

    if data == "wardrobe":
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(query.message.chat_id, TEXTS["wardrobe"][lang], reply_markup=csdota_wardrobe(lang))
        return

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    if state not in ("photo", "skin_photo"):
        return
    if not update.message.photo:
        await update.message.reply_text("⚠️ Отправьте фото.")
        return
    photos = user_drafts[user_id]["photos"]
    photos.append(update.message.photo[-1].file_id)
    if state == "skin_photo":
        user_states[user_id] = "skin_desc"
        await update.message.reply_text(TEXTS["enter_skin_desc"][user_languages.get(user_id, "ru")])
    else:
        if len(photos) >= 10:
            user_states[user_id] = "desc"
            await update.message.reply_text(TEXTS["enter_desc"][user_languages.get(user_id, "ru")])
        else:
            await update.message.reply_text(f"Получено {len(photos)}/10. Отправьте ещё или текст для продолжения.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_languages.get(user_id, "ru")
    state = user_states.get(user_id)
    text = update.message.text.strip() if update.message.text else ""

    if "reject_id" in context.user_data:
        acc_id = context.user_data.pop("reject_id")
        acc = pending_accounts.pop(acc_id, None)
        if acc:
            save_json(PENDING_FILE, pending_accounts)
            await context.bot.send_message(acc["user_id"], f"❌ Отказ.\nПричина: {text}")
        await update.message.reply_text("Отказ отправлен.")
        return

    if "set_balance" in context.user_data:
        context.user_data.pop("set_balance")
        try:
            new_balance = float(text)
            config["skin_balance"] = new_balance
            save_json(CONFIG_FILE, config)
            await update.message.reply_text(f"Баланс обновлён: {new_balance} USDT")
            await admin_panel_handler(update, context)
        except:
            await update.message.reply_text("Неверное значение.")
        return

    if "set_discount" in context.user_data:
        context.user_data.pop("set_discount")
        parts = text.split()
        if len(parts) == 3:
            try:
                config["discount_accounts"] = int(parts[0])
                config["discount_skins"] = int(parts[1])
                config["discount_usernames"] = int(parts[2])
                save_json(CONFIG_FILE, config)
                await update.message.reply_text("Скидки обновлены.")
                await admin_panel_handler(update, context)
            except:
                await update.message.reply_text("Неверный формат.")
        else:
            await update.message.reply_text("Введите 3 числа через пробел.")
        return

    if state == "skin_title":
        user_drafts[user_id]["title"] = text
        user_states[user_id] = "skin_photo"
        await update.message.reply_text(TEXTS["enter_skin_photo"][lang])
    elif state == "skin_photo":
        if update.message.photo:
            return
        user_states[user_id] = "skin_desc"
        await update.message.reply_text(TEXTS["enter_skin_desc"][lang])
    elif state == "skin_desc":
        user_drafts[user_id]["desc_raw"] = text
        user_states[user_id] = "skin_price"
        await update.message.reply_text(TEXTS["enter_skin_price"][lang])
    elif state == "skin_price":
        try:
            price_usdt = float(text)
            if price_usdt <= 0:
                raise ValueError
            draft = user_drafts[user_id]
            if len(draft["photos"]) == 0:
                await update.message.reply_text("Добавьте хотя бы одно фото.")
                return
            desc_ru = draft["desc_raw"]
            desc_en = draft["desc_raw"]
            skin_id = str(max([int(k) for k in skins_catalog.keys() if k.isdigit()] + [0]) + 1)
            skins_catalog[skin_id] = {
                "title": draft["title"],
                "photos": draft["photos"],
                "description": {"ru": desc_ru, "en": desc_en},
                "price_usdt": price_usdt
            }
            save_json(SKINS_FILE, skins_catalog)
            user_states.pop(user_id, None)
            user_drafts.pop(user_id, None)
            await update.message.reply_text(TEXTS["skin_added"][lang])
        except ValueError:
            await update.message.reply_text("Введите корректную цену > 0.")
        return

    if state == "title":
        if not text:
            await update.message.reply_text("Введите название.")
            return
        user_drafts[user_id]["title"] = text
        user_states[user_id] = "photo"
        await update.message.reply_text(TEXTS["enter_photo"][lang])
    elif state == "photo":
        if update.message.photo:
            return
        user_states[user_id] = "desc"
        await update.message.reply_text(TEXTS["enter_desc"][lang])
    elif state == "desc":
        if not text:
            await update.message.reply_text("Введите описание.")
            return
        user_drafts[user_id]["desc_raw"] = text
        user_states[user_id] = "price"
        await update.message.reply_text(TEXTS["enter_price"][lang])
    elif state == "price":
        try:
            price_usdt = float(text)
            if price_usdt <= 0:
                raise ValueError
            draft = user_drafts[user_id]
            if len(draft["photos"]) == 0:
                await update.message.reply_text("Добавьте хотя бы одно фото.")
                return
            desc_ru = draft['desc_raw']
            desc_en = draft['desc_raw']
            acc_id = str(max([int(k) for k in list(accounts_for_sale.keys()) + list(pending_accounts.keys()) if k.isdigit()] + [0]) + 1)
            pending_accounts[acc_id] = {
                "title": draft["title"],
                "photos": draft["photos"],
                "description": {"ru": desc_ru, "en": desc_en},
                "price_usdt": price_usdt,
                "user_id": user_id,
                "username": update.effective_user.username
            }
            save_json(PENDING_FILE, pending_accounts)
            user_states.pop(user_id, None)
            user_drafts.pop(user_id, None)
            await update.message.reply_text(TEXTS["sent_for_review"][lang])
            price_info = f"Цена: {price_usdt} USDT"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{acc_id}"), InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{acc_id}")]])
            await context.bot.send_photo(ADMIN_ID, draft["photos"][0], caption=f"Новый аккаунт на модерацию:\n{draft['title']}\n{price_info}", reply_markup=kb)
        except ValueError:
            await update.message.reply_text("Введите корректную цену > 0.")
    elif state == "skin_link":
        if not re.match(r"^https?://steamcommunity\.com/market/listings/", text):
            await update.message.reply_text("Отправьте корректную ссылку Steam Market.")
            return
        user_drafts[user_id]["link"] = text
        user_states[user_id] = "skin_quantity"
        await update.message.reply_text("Укажите количество:")
    elif state == "skin_quantity":
        try:
            qty = int(text)
            if qty <= 0:
                raise ValueError
            link = user_drafts[user_id]["link"]
            game = user_drafts[user_id]["game"]
            admin_text = f"🆕 Заказ скина\nИгра: {game}\nСсылка: {link}\nКоличество: {qty}\nБаланс: {config['skin_balance']} USDT\nОт: @{update.effective_user.username or 'NoUsername'} (ID: {user_id})"
            await context.bot.send_message(ADMIN_ID, admin_text)
            await update.message.reply_text("Заказ отправлен. Ожидайте.")
            user_states.pop(user_id, None)
            user_drafts.pop(user_id, None)
        except ValueError:
            await update.message.reply_text("Введите положительное число.")

if __name__ == "__main__":
    if not TOKEN:
        print("Ошибка: BOT_TOKEN не задан!")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("restart", restart_command))

    app.add_handler(CallbackQueryHandler(moderation_buttons, pattern="^(approve_|reject_)"))
    app.add_handler(CallbackQueryHandler(admin_panel_handler, pattern="^(toggle_ny|set_balance|visits|errors|discounts|add_skin)$"))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Бот запущен")
    app.run_polling()