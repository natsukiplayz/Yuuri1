#!/usr/bin/env python3
"""Anti-spam captcha system used to gate non-premium users who
hammer economy commands (kill/rob/daily)."""

import time
import secrets
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.helpers import get_user, is_premium as _is_premium  # re-exported alias used by economy.py

CAPTCHA_HOST = "https://yuuri_captcha.oneapp.dev/"
SPAM_THRESHOLD = 4
SPAM_WINDOW = 10
CAPTCHA_TIMEOUT = 300
CAPTCHA_COOLDOWN = 600

spam_tracker: dict = {}
pending_captcha: dict = {}
captcha_cleared: dict = {}


def _token() -> str:
    return secrets.token_hex(8)


def _captcha_url(token: str) -> str:
    return f"{CAPTCHA_HOST}?token={token}"


def _already_verified(user_id: int) -> bool:
    ts = captcha_cleared.get(user_id)
    return bool(ts and time.time() - ts < CAPTCHA_COOLDOWN)


def _record_cmd(user_id: int) -> int:
    now = time.time()
    hits = [t for t in spam_tracker.get(user_id, []) if now - t < SPAM_WINDOW]
    hits.append(now)
    spam_tracker[user_id] = hits
    return len(hits)


async def _dm_captcha(bot, user_id: int, chat_id: int, cmd: str):
    tok = _token()
    pending_captcha[user_id] = {
        "token": tok, "expires": time.time() + CAPTCHA_TIMEOUT,
        "pending_cmd": cmd, "pending_chat": chat_id,
    }
    url = _captcha_url(tok)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔒 ᴠᴇʀɪꜰʏ ɪ'ᴍ ʜᴜᴍᴀɴ", url=url)]])
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "⚠️ <b>ʜᴜᴍᴀɴ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ʀᴇqᴜɪʀᴇᴅ</b>\n\n"
                "ʏᴏᴜ'ᴠᴇ ʙᴇᴇɴ ꜰʟᴀɢɢᴇᴅ ꜰᴏʀ ꜰᴀsᴛ ᴄᴏᴍᴍᴀɴᴅ ᴜsᴀɢᴇ.\n"
                "ᴄᴏᴍᴘʟᴇᴛᴇ ᴛʜᴇ ᴄᴀᴘᴛᴄʜᴀ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ ᴘʟᴀʏɪɴɢ.\n\n"
                "<i>ᴇxᴘɪʀᴇs ɪɴ 5 ᴍɪɴᴜᴛᴇs.</i>"
            ),
            parse_mode=ParseMode.HTML, reply_markup=kb
        )
    except Exception:
        await bot.send_message(
            chat_id=chat_id,
            text=f"🔒 <a href='tg://user?id={user_id}'>ʜᴇʏ!</a> ᴘʟᴇᴀsᴇ ᴏᴘᴇɴ ᴍʏ DM ꜰɪʀsᴛ ᴛᴏ ᴄᴏᴍᴘʟᴇᴛᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ.",
            parse_mode=ParseMode.HTML
        )


async def handle_captcha_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered via /start captcha_TOKEN deep link after the person taps
    Confirm on the captcha web page."""
    user = update.effective_user
    args = context.args
    if not args or not args[0].startswith("captcha_"):
        return

    tok = args[0][len("captcha_"):]
    data = pending_captcha.get(user.id)

    if not data:
        return await update.message.reply_text("❌ ɴᴏ ᴘᴇɴᴅɪɴɢ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ꜰᴏᴜɴᴅ.")
    if time.time() > data["expires"]:
        pending_captcha.pop(user.id, None)
        return await update.message.reply_text("⏰ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ᴇxᴘɪʀᴇᴅ. ᴛʀʏ ʏᴏᴜʀ ᴄᴏᴍᴍᴀɴᴅ ᴀɢᴀɪɴ.")
    if data["token"] != tok:
        return await update.message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ᴛᴏᴋᴇɴ.")

    pending_captcha.pop(user.id, None)
    captcha_cleared[user.id] = time.time()
    spam_tracker.pop(user.id, None)

    await update.message.reply_text(
        "✅ <b>ᴠᴇʀɪꜰɪᴇᴅ!</b> ʏᴏᴜ'ʀᴇ ɢᴏᴏᴅ ᴛᴏ ɢᴏ.\n"
        "ʜᴇᴀᴅ ʙᴀᴄᴋ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ ᴀɴᴅ ᴜsᴇ ʏᴏᴜʀ ᴄᴏᴍᴍᴀɴᴅ ᴀɢᴀɪɴ. 🎮",
        parse_mode=ParseMode.HTML
    )


def spam_guard(cmd_name: str):
    """Decorator: @spam_guard("kill") on any economy command."""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            chat = update.effective_chat
            user_data = get_user(user)

            if _is_premium(user_data, context):
                return await func(update, context)

            if user.id in pending_captcha:
                info = pending_captcha[user.id]
                if time.time() < info["expires"]:
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔒 ᴠᴇʀɪꜰʏ ɴᴏᴡ", url=_captcha_url(info["token"]))]])
                    return await update.message.reply_text(
                        "🛑 ᴄᴏᴍᴘʟᴇᴛᴇ ʏᴏᴜʀ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ꜰɪʀsᴛ!", reply_markup=kb
                    )
                else:
                    pending_captcha.pop(user.id, None)

            if _already_verified(user.id):
                return await func(update, context)

            uses = _record_cmd(user.id)
            if uses >= SPAM_THRESHOLD:
                await update.message.reply_text(
                    "⚡ <b>sᴘᴀᴍ ᴅᴇᴛᴇᴄᴛᴇᴅ!</b>\nᴄʜᴇᴄᴋ ʏᴏᴜʀ DM ᴛᴏ ᴠᴇʀɪꜰʏ ʏᴏᴜ'ʀᴇ ʜᴜᴍᴀɴ. 👀",
                    parse_mode=ParseMode.HTML
                )
                await _dm_captcha(context.bot, user.id, chat.id, cmd_name)
                return

            return await func(update, context)

        wrapper.__name__ = func.__name__
        return wrapper
    return decorator
