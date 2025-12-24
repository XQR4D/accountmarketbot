from telegram import (  # type: ignore
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    PhotoSize,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)
from telegram.ext import (  # type: ignore
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    Application,
)
from telegram.error import Forbidden  # type: ignore
import json
import os
import asyncio
import re
import urllib.parse
import urllib.request
from dotenv import load_dotenv  # Импорт для работы с .env

# Загружаем переменные из .env
load_dotenv()

SUBSCRIBERS_FILE = "subscribers.json"
PENDING_FILE = "pending_accounts.json"
ACCOUNTS_FILE = "accounts.json"
SKINS_FILE = "skins.json"

# Получаем настройки из окружения
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

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

def remove_subscriber(user_id):
    if user_id in subscribers:
        subscribers.discard(user_id)
        save_json(SUBSCRIBERS_FILE, list(subscribers))

def contains_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text or ""))

def translate_ru_to_en_sync(text: str) -> str:
    try:
        query = urllib.parse.quote_plus(text)
        url = f"https://api.mymemory.translated.net/get?q={query}&langpair=ru|en"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = data.get("responseData", {}).get("translatedText")
            return translated or text
    except Exception:
        return text

async def translate_ru_to_en(text: str) -> str:
    if not text or not contains_cyrillic(text):
        return text
    return await asyncio.to_thread(translate_ru_to_en_sync, text)

subscribers = set(load_json(SUBSCRIBERS_FILE))
pending_accounts = load_json(PENDING_FILE)
accounts_for_sale = load_json(ACCOUNTS_FILE)
skins_catalog = load_json(SKINS_FILE)

user_languages = {}
user_states = {}
user_drafts = {}

TEXTS = {
    "add_account": {"ru": "📥 Опубликовать аккаунт", "en": "📥 Post account"},
    "add_skin": {"ru": "🔫 Добавить скин (Adm)", "en": "🔫 Add skin (Adm)"},
    "enter_title": {"ru": "✍️ Введите название аккаунта:", "en": "✍️ Enter account title:"},
    "enter_photo": {
        "ru": "📷 Отправьте до 10 фотографий аккаунта:",
        "en": "📷 Send up to 10 photos:",
    },
    "enter_desc": {"ru": "📘 Отправьте описание аккаунта:", "en": "📘 Send account description:"},
    "sent_for_review": {
        "ru": "⏳ Отправлено на модерацию. Ожидайте уведомления.",
        "en": "⏳ Sent for moderation. Please wait.",
    },
    "rejected_reason": {"ru": "🚫 Укажите причину отказа:", "en": "🚫 Specify rejection reason:"},
    "choose_language": {"ru": "🌐 Выберите язык / Choose language:", "en": "🌐 Choose language / Выберите язык:"},
    "greeting": {
        "ru": "🏪 Добро пожаловать в маркетплейс!\n\nВыберите категорию ниже:",
        "en": "🏪 Welcome to the marketplace!\n\nChoose a category below:",
    },
    "back": {"ru": "🔙 Назад", "en": "🔙 Back"},
    "settings": {"ru": "🛠 Настройки", "en": "🛠 Settings"},
    "report_bug": {"ru": "🆘 Тех. поддержка", "en": "🆘 Support"},
    "contact_seller": {"ru": "👨‍💻 Связаться", "en": "👨‍💻 Contact"},
    "support_dev": {"ru": "💳 Поддержать проект", "en": "💳 Support project"},
    "choose_account": {"ru": "📁 Доступные аккаунты:", "en": "📁 Available accounts:"},
    "settings_menu": {"ru": "🛠 Настройки и помощь:", "en": "🛠 Settings & Help:"},
    "username_menu": {"ru": "💎 Эксклюзивные юзернеймы:", "en": "💎 Exclusive usernames:"},
    "buy_username": {"ru": "🛍 Купить юзернейм", "en": "🛍 Buy a username"},
    "usernames": {"ru": "💎 Юзернеймы", "en": "💎 Usernames"},
    "skins": {"ru": "🔫 Скины CS/Dota", "en": "🔫 CS/Dota Skins"},
    "skins_available": {"ru": "🔫 Витрина скинов:", "en": "🔫 Skin showcase:"},
    "cs_dota_wardrobe": {"ru": "🎮 Поиск предметов в Steam:", "en": "🎮 Search items in Steam:"},
    "wardrobebuy": {"ru": "🛒 Заказать покупку", "en": "🛒 Order purchase"},
    "wardrobe": {"ru": "💼 Заказ скинов", "en": "💼 Order skins"},
    "funpay": {"ru": "⭐️ Отзывы FunPay", "en": "⭐️ FunPay Reviews"},
}

async def set_bot_commands(app: Application):
    user_commands = [
        BotCommand("start", "Главное меню / Main Menu"),
        BotCommand("info", "О боте / About"),
        BotCommand("id", "Мой ID / My ID"),
    ]
    admin_commands = user_commands + [
        BotCommand("broadcast", "Рассылка / Broadcast"),
        BotCommand("restart", "Перезагрузка / Restart"),
    ]
    await app.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    if ADMIN_ID:
        await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))

def language_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ])

def main_menu(lang):
    keyboard = []
    # Секция аккаунтов
    for acc_id, acc in accounts_for_sale.items():
        title = acc["title"][lang] if isinstance(acc.get("title"), dict) else acc.get("title", "")
        keyboard.append([InlineKeyboardButton(f"📦 {title}", callback_data=f"show_{acc_id}")])
    
    # Секция категорий
    keyboard.append([
        InlineKeyboardButton(TEXTS["skins"][lang], callback_data="skins"),
        InlineKeyboardButton(TEXTS["usernames"][lang], callback_data="usernames")
    ])
    keyboard.append([InlineKeyboardButton(TEXTS["wardrobe"][lang], callback_data="wardrobe")])
    
    # Секция действий
    keyboard.append([
        InlineKeyboardButton(TEXTS["add_account"][lang], callback_data="add_account"),
        InlineKeyboardButton(TEXTS["add_skin"][lang], callback_data="add_skin")
    ])
    
    # Настройки
    keyboard.append([InlineKeyboardButton(TEXTS["settings"][lang], callback_data="settings")])
    return InlineKeyboardMarkup(keyboard)

def settings_menu(lang):
    link = "https://t.me/vs_xrd"
    funpay = "https://funpay.com/users/4624991/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(TEXTS["report_bug"][lang], url=link),
         InlineKeyboardButton(TEXTS["funpay"][lang], url=funpay)],
        [InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")]
    ])

def account_buttons(lang, author_link=None):
    keyboard = []
    contact_url = author_link if author_link else "https://t.me/vs_xrd"
    keyboard.append([InlineKeyboardButton(TEXTS["contact_seller"][lang], url=contact_url)])
    keyboard.append([InlineKeyboardButton(TEXTS["support_dev"][lang], callback_data="support_dev_info")])
    keyboard.append([InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in subscribers:
        subscribers.add(user_id)
        save_json(SUBSCRIBERS_FILE, list(subscribers))
    if user_id not in user_languages:
        await update.message.reply_text(TEXTS["choose_language"]["ru"], reply_markup=language_keyboard())
    else:
        lang = user_languages[user_id]
        await update.message.reply_text(TEXTS["greeting"][lang], reply_markup=main_menu(lang))

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_languages.get(user_id, "ru")
    text = {
        "ru": "🏪 *Цифровой Маркетплейс*\n\nЗдесь вы можете безопасно покупать и продавать игровые аккаунты, уникальные юзернеймы и скины.",
        "en": "🏪 *Digital Marketplace*\n\nHere you can safely buy and sell game accounts, unique usernames, and skins."
    }
    await update.message.reply_text(text[lang], parse_mode="Markdown")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    await update.message.reply_text("🔄 Команда получена. Бот перезагрузится в течение пары секунд...")
    
    await asyncio.sleep(1)
    
    os._exit(0)

def tg_username(lang):
    username_items = [
        ("💎 @pepecollectors — 8$", "pepecollectors"),
        ("💎 @DateHappy — 8$", "DateHappy"),
        ("💎 @seIIer_accounts — 3$", "seIIer_accounts"),
        ("💎 @messengervolt — 39$", "messengervolt"),
        ("💎 @voltmessenger — 39$", "voltmessenger"),
        ("💎 @vs_xrd — 8$", "vs_xrd"),
    ]
    keyboard = [[InlineKeyboardButton(label, url=f"https://t.me/{uname}")] for label, uname in username_items]
    keyboard.append([InlineKeyboardButton(TEXTS["buy_username"][lang], url="https://t.me/vs_xrd")])
    keyboard.append([InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def skins_menu(lang):
    keyboard = []
    for skin_id, skin in skins_catalog.items():
        title = skin["title"][lang] if isinstance(skin.get("title"), dict) else skin.get("title", "")
        keyboard.append([InlineKeyboardButton(f"🔫 {title}", callback_data=f"skin_{skin_id}")])
    if not keyboard:
        keyboard.append([InlineKeyboardButton("📭 Пока пусто", callback_data="back")])
    keyboard.append([InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def skin_buttons(lang, author_link=None):
    return account_buttons(lang, author_link)

def csdota_wardrobe(lang):
    wardrobe_items = [("🎮 Counter-Strike 2", "730"), ("🎮 Dota 2", "570")]
    keyboard = [
        [InlineKeyboardButton(label, url=f"https://steamcommunity.com/market/search?appid={appid}")]
        for label, appid in wardrobe_items
    ]
    keyboard.append([InlineKeyboardButton(TEXTS["wardrobebuy"][lang], url="https://t.me/vs_xrd")])
    keyboard.append([InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data
    lang = user_languages.get(user_id, "ru")

    if data.startswith("lang_"):
        lang = data.split("_")[1]
        user_languages[user_id] = lang
        await query.edit_message_text(TEXTS["greeting"][lang], reply_markup=main_menu(lang))
        return

    if data == "add_account":
        user_states[user_id] = "title"
        user_drafts[user_id] = {}
        await query.message.reply_text(TEXTS["enter_title"][lang])
        return

    if data == "add_skin":
        if user_id != ADMIN_ID:
            await query.answer("Доступ только для администратора.", show_alert=True)
            return
        user_states[user_id] = "skin_title"
        user_drafts[user_id] = {}
        await query.message.reply_text("✍️ Введите название скина:")
        return

    if data == "back":
        try: await query.message.delete()
        except: pass
        last_album = context.user_data.pop("last_album", [])
        for mid in last_album:
            try: await context.bot.delete_message(chat_id=query.message.chat_id, message_id=mid)
            except: pass
        await context.bot.send_message(chat_id=query.message.chat_id, text=TEXTS["greeting"][lang], reply_markup=main_menu(lang))
        return

    if data.startswith("show_") or data.startswith("skin_"):
        is_skin = data.startswith("skin_")
        item_id = data[5:] if not is_skin else data.split("_", 1)[1]
        catalog = accounts_for_sale if not is_skin else skins_catalog
        item = catalog.get(item_id)
        
        if not item:
            await query.edit_message_text("❌ Информация недоступна.")
            return
        
        try: await query.message.delete()
        except: pass

        photos = item.get("photos", [])
        desc = item.get("description", "")
        description_text = desc.get(lang, str(desc)) if isinstance(desc, dict) else str(desc)
        author_link = item.get("author")

        if len(photos) == 1:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photos[0],
                caption=description_text,
                reply_markup=account_buttons(lang, author_link)
            )
        else:
            media_group = [InputMediaPhoto(media=p, caption=description_text if i == 0 else "") for i, p in enumerate(photos)]
            sent_media = await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group)
            sent_menu = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📍 Используйте кнопки ниже для связи:",
                reply_markup=account_buttons(lang, author_link)
            )
            context.user_data["last_album"] = [m.message_id for m in sent_media] + [sent_menu.message_id]
        return

    if data == "settings":
        await query.edit_message_text(TEXTS["settings_menu"][lang], reply_markup=settings_menu(lang))
        return
    if data == "usernames":
        await query.edit_message_text(TEXTS["username_menu"][lang], reply_markup=tg_username(lang))
        return
    if data == "skins":
        await query.edit_message_text(TEXTS["skins_available"][lang], reply_markup=skins_menu(lang))
        return
    if data == "wardrobe":
        await query.edit_message_text(TEXTS["cs_dota_wardrobe"][lang], reply_markup=csdota_wardrobe(lang))
        return

async def moderation_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("approve_"):
        acc_id = data.split("_")[1]
        acc = pending_accounts.pop(acc_id, None)
        if acc:
            accounts_for_sale[acc_id] = {
                "title": {"ru": acc.get("title", ""), "en": acc.get("title_en", acc.get("title", ""))},
                "photos": acc["photos"],
                "description": {"ru": acc.get("description", ""), "en": acc.get("description_en", acc.get("description", ""))},
                "author": f"https://t.me/{acc['username']}" if acc["username"] else None
            }
            save_json(PENDING_FILE, pending_accounts); save_json(ACCOUNTS_FILE, accounts_for_sale)
            await context.bot.send_message(chat_id=acc["user_id"], text="✅ Ваш аккаунт опубликован!")
            try: await query.message.delete()
            except: pass
        return
    if data.startswith("reject_"):
        acc_id = data.split("_")[1]
        if acc_id in pending_accounts:
            context.user_data["rejecting"] = acc_id
            await query.message.reply_text("🚫 Укажите причину отказа:")
    return

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_languages.get(user_id, "ru")
    state = user_states.get(user_id)
    if state not in ("photo", "skin_photo"): return
    key = "photos" if state == "photo" else "skin_photos"
    photo_list = user_drafts.setdefault(user_id, {}).setdefault(key, [])
    if update.message.photo:
        photo_list.append(update.message.photo[-1].file_id)
    if len(photo_list) >= 10:
        user_states[user_id] = "desc" if state == "photo" else "skin_desc"
        await update.message.reply_text(TEXTS["enter_desc"][lang] if state == "photo" else "📘 Отправьте описание:")
    else:
        await update.message.reply_text(f"📸 Получено {len(photo_list)}/10. Отправьте ещё или любое слово для завершения.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_languages.get(user_id, "ru")
    state = user_states.get(user_id)
    text = update.message.text.strip() if update.message.text else ""

    if "rejecting" in context.user_data:
        acc_id = context.user_data.pop("rejecting")
        acc = pending_accounts.pop(acc_id, None)
        if acc:
            save_json(PENDING_FILE, pending_accounts)
            await context.bot.send_message(chat_id=acc["user_id"], text=f"❌ Отказ по '{acc['title']}'.\nПричина: {text}")
            for msg_id in context.user_data.pop(f"admin_msg_ids_{acc_id}", []):
                try: await context.bot.delete_message(chat_id=ADMIN_ID, message_id=msg_id)
                except: pass
            await update.message.reply_text("📨 Отказ отправлен.")
        return

    if state == "title":
        user_drafts[user_id]["title"] = text
        user_states[user_id] = "photo"; await update.message.reply_text(TEXTS["enter_photo"][lang])
    elif state == "photo":
        if not user_drafts[user_id].get("photos"):
            await update.message.reply_text("⚠️ Нужно фото.")
            return
        user_states[user_id] = "desc"; await update.message.reply_text(TEXTS["enter_desc"][lang])
    elif state == "desc":
        draft = user_drafts[user_id]
        acc_id = str(max([int(i) for i in list(accounts_for_sale.keys()) + list(pending_accounts.keys()) if i.isdigit()] + [0]) + 1)
        pending_accounts[acc_id] = {
            "title": draft["title"], "title_en": await translate_ru_to_en(draft["title"]),
            "photos": draft["photos"], "description": text, "description_en": await translate_ru_to_en(text),
            "user_id": user_id, "username": update.effective_user.username
        }
        save_json(PENDING_FILE, pending_accounts)
        user_states.pop(user_id); user_drafts.pop(user_id)
        await update.message.reply_text(TEXTS["sent_for_review"][lang])
        
        # Админ-панель
        author = f"@{update.effective_user.username}" if update.effective_user.username else f"ID: {user_id}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Да", callback_data=f"approve_{acc_id}"), InlineKeyboardButton("❌ Нет", callback_data=f"reject_{acc_id}")]])
        caption = f"🆕 Модерация:\n📌 {draft['title']}\n💬 {text}\n👤 {author}"
        msg = await context.bot.send_photo(chat_id=ADMIN_ID, photo=draft["photos"][0], caption=caption, reply_markup=kb)
        context.user_data[f"admin_msg_ids_{acc_id}"] = [msg.message_id]

    elif state == "skin_title":
        user_drafts[user_id]["skin_title"] = text; user_states[user_id] = "skin_photo"
        await update.message.reply_text("📷 Отправьте фото скина:")
    elif state == "skin_photo":
        user_states[user_id] = "skin_desc"; await update.message.reply_text("📘 Описание скина:")
    elif state == "skin_desc":
        draft = user_drafts[user_id]
        skin_id = str(max([int(i) for i in list(skins_catalog.keys()) if i.isdigit()] + [0]) + 1)
        skins_catalog[skin_id] = {
            "title": {"ru": draft["skin_title"], "en": await translate_ru_to_en(draft["skin_title"])},
            "description": {"ru": text, "en": await translate_ru_to_en(text)},
            "photos": draft.get("skin_photos", []),
            "author": f"https://t.me/{update.effective_user.username}" if update.effective_user.username else None,
        }
        save_json(SKINS_FILE, skins_catalog)
        user_states.pop(user_id); user_drafts.pop(user_id)
        await update.message.reply_text("✅ Скин добавлен.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    text = " ".join(context.args)
    for uid in list(subscribers):
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            await asyncio.sleep(0.05)
        except Forbidden: remove_subscriber(uid)
        except: pass
    await update.message.reply_text("✅ Рассылка завершена.")

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 Ваш Telegram ID: `{update.effective_user.id}`", parse_mode="Markdown")

async def support_dev_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = user_languages.get(query.from_user.id, "ru")
    addr = "TGcAAaqLdYQFAFDVPkbAYSTvwo7WP9y2DF"
    text = f"💎 *Поддержка проекта*\n\nUSDT (TRC20):\n`{addr}`\n\n_Нажмите на адрес, чтобы скопировать_"
    await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(TEXTS["back"][lang], callback_data="back")]]))

if __name__ == "__main__":
    # Проверка на наличие токена
    if not TOKEN:
        print("Ошибка: Переменная окружения BOT_TOKEN не установлена!")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CallbackQueryHandler(support_dev_handler, pattern="^support_dev_info$"))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(moderation_buttons, pattern="^(approve_|reject_)"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    app.job_queue.run_once(lambda _: set_bot_commands(app), 2)
    print("Бот запущен с использованием ENV...")
    app.run_polling()