# -*- coding: utf-8 -*-
"""
Beruniy Taxi 1221 — Telegram bot
Mijoz uchun: buyurtma berish (telefon, manzil/lokatsiya, izoh)
Admin guruh uchun: buyurtmani qabul qilish / bekor qilish
"""

import logging
import sqlite3
from contextlib import closing

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ============== SOZLAMALAR ==============
import os
BOT_TOKEN = os.environ.get("8544782058:AAEfzIJqJ9GL-OyU-tQgVYt8jD1D5dIGr9k")
ADMIN_GROUP_ID = int(os.environ.get("ADMIN_GROUP_ID"))
ADMIN_GROUP_ID = -1001234567890        # Admin guruh ID (manfiy son, pastda qanday topish yozilgan)
DB_PATH = "beruniy_taxi.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Conversation bosqichlari
PHONE, LOCATION, COMMENT = range(3)

COMMENT_NO_COMMENT = "Izohsiz"


# ============== DATABASE ==============
def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT NOT NULL
            )
            """
        )
        conn.commit()


def get_saved_phone(user_id: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.execute("SELECT phone FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None


def save_phone(user_id: int, phone: str):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id, phone) VALUES (?, ?)",
            (user_id, phone),
        )
        conn.commit()


# ============== YORDAMCHI FUNKSIYALAR ==============
def comment_keyboard():
    return ReplyKeyboardMarkup(
        [[COMMENT_NO_COMMENT]], resize_keyboard=True, one_time_keyboard=True
    )


def location_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ============== HANDLERLAR ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    saved_phone = get_saved_phone(user_id)

    if saved_phone:
        context.user_data["phone"] = saved_phone
        await update.message.reply_text(
            "Assalomu alaykum! Beruniy Taxi 1221 botiga xush kelibsiz.\n\n"
            "Qayerga taksi kerak? Lokatsiya yuboring yoki manzilni matn ko'rinishida yozing.",
            reply_markup=location_keyboard(),
        )
        return LOCATION
    else:
        await update.message.reply_text(
            "Assalomu alaykum! Beruniy Taxi 1221 botiga xush kelibsiz.\n\n"
            "Avval telefon raqamingizni yuboring (keyingi buyurtmalarda so'ralmaydi).",
            reply_markup=phone_keyboard(),
        )
        return PHONE


async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()

    user_id = update.effective_user.id
    save_phone(user_id, phone)
    context.user_data["phone"] = phone

    await update.message.reply_text(
        "Rahmat! Endi qayerga taksi kerak?\n"
        "Lokatsiya yuboring yoki manzilni matn ko'rinishida yozing.",
        reply_markup=location_keyboard(),
    )
    return LOCATION


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        loc = update.message.location
        context.user_data["location_text"] = f"{loc.latitude}, {loc.longitude}"
        context.user_data["location_obj"] = (loc.latitude, loc.longitude)
    else:
        context.user_data["location_text"] = update.message.text.strip()
        context.user_data["location_obj"] = None

    await update.message.reply_text(
        "Izoh qoldirmoqchimisiz? (masalan: Yetkazib berish, Cobalt-Gentra, Ustki bagaj, Bagaj...)\n"
        "Agar izoh kerak bo'lmasa, pastdagi tugmani bosing.",
        reply_markup=comment_keyboard(),
    )
    return COMMENT


async def comment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_comment = update.message.text.strip()
    user = update.effective_user
    phone = context.user_data.get("phone", "Noma'lum")
    location_text = context.user_data.get("location_text", "Noma'lum")
    location_obj = context.user_data.get("location_obj")

    await update.message.reply_text(
        "Buyurtmangiz qabul qilindi va operatorga yuborildi. Tez orada javob beramiz!",
        reply_markup=ReplyKeyboardRemove(),
    )

    # Admin guruhga xabar
    name = user.full_name
    username = f"@{user.username}" if user.username else "—"

    text = (
        "🆕 <b>Yangi buyurtma</b>\n\n"
        f"👤 Mijoz: {name} ({username})\n"
        f"📞 Telefon: <code>{phone}</code>\n"
        f"📍 Manzil: {location_text}"
    )

    # "Izohsiz" tugmasi bosilgan bo'lsa — izoh qatori umuman qo'shilmaydi.
    # Aks holda mijoz yozgan erkin matn qo'shiladi.
    if raw_comment != COMMENT_NO_COMMENT:
        text += f"\n💬 Izoh: {raw_comment}"

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Qabul qilindi", callback_data=f"accept:{user.id}"),
                InlineKeyboardButton("❌ Bekor qilindi", callback_data=f"cancel:{user.id}"),
            ]
        ]
    )

    sent_msg = await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )

    # Agar lokatsiya bo'lsa, alohida pin yuboramiz
    if location_obj:
        await context.bot.send_location(
            chat_id=ADMIN_GROUP_ID,
            latitude=location_obj[0],
            longitude=location_obj[1],
            reply_to_message_id=sent_msg.message_id,
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Buyurtma bekor qilindi.", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


# ============== ADMIN TUGMALARI (callback) ==============
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id_str = query.data.split(":")
    user_id = int(user_id_str)

    original_text = query.message.text or query.message.caption or ""

    if action == "accept":
        new_text = original_text + "\n\n✅ <b>Qabul qilindi</b>"
        client_text = "Buyurtmangiz qabul qilindi! Haydovchi tez orada sizga aloqaga chiqadi"
    else:
        new_text = original_text + "\n\n❌ <b>Bekor qilindi</b>"
        client_text = "Afsuski biz sizni tushunmadik, iltimos operator qo'ng'irog'ini kuting…1221"

    # Guruhdagi xabarni yangilash — tugmalarsiz, faqat matn
    try:
        await query.edit_message_text(
            text=new_text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning(f"Edit message error: {e}")

    # Mijozga xabar yuborish
    try:
        await context.bot.send_message(chat_id=user_id, text=client_text)
    except Exception as e:
        logger.warning(f"Mijozga xabar yuborib bo'lmadi: {e}")


# ============== GURUH ID NI TOPISH UCHUN YORDAMCHI ==============
async def show_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guruhda /chatid deb yozsangiz, guruh ID sini ko'rsatadi."""
    await update.message.reply_text(f"Chat ID: `{update.effective_chat.id}`", parse_mode=ParseMode.MARKDOWN)


# ============== MAIN ==============
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHONE: [
                MessageHandler(filters.CONTACT, phone_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler),
            ],
            LOCATION: [
                MessageHandler(filters.LOCATION, location_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, location_handler),
            ],
            COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, comment_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(accept|cancel):"))
    app.add_handler(CommandHandler("chatid", show_chat_id))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
