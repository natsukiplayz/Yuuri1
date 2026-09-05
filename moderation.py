#!/usr/bin/env python3
"""Group moderation: ban, kick, mute, tmute, warn, promote, demote,
pin/unpin, purge, plus the auto security guard (links / bad words)."""

import re
from telegram import Update, ChatPermissions
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from bot.config import OWNER_ID, users_collection, allowed_collection, admins_db

# --- Bad word / link filters ---
LINK_PATTERN = r"(https?://\S+|www\.\S+|t\.me/\S+)"
BAD_WORDS = [
    "fuck", "fucking", "fuk", "shitt", "bitch", "btch", "asshole", "dick", "pussy",
    "cunt", "slut", "whore", "bastard", "motherfucker", "nigga", "nigger",
    "bc", "mc", "bsdk", "bhenchod", "behenchod", "madarchod", "maderchod",
    "chutiya", "chut", "gaand", "gand", "gandu", "lund", "lodu", "lauda",
    "raandi", "randi", "bhosadi", "bhosadike", "bhosdike", "saala", "sala",
    "harami", "kamina", "kamine", "muth", "muthal", "bakchod", "bakchodi", "lowda"
]


def is_allowed(user_id):
    if user_id == OWNER_ID:
        return True
    found = allowed_collection.find_one({"user_id": user_id})
    return bool(found)


def get_security_data(user_id):
    user = users_collection.find_one({"id": user_id})
    return user.get("warns", 0) if user else 0


def increment_warns(user_id):
    users_collection.update_one({"id": user_id}, {"$inc": {"warns": 1}}, upsert=True)
    return get_security_data(user_id)


def reset_warns(user_id):
    users_collection.update_one({"id": user_id}, {"$set": {"warns": 0}})


async def security_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    user_id = user.id
    chat_id = update.effective_chat.id
    text = update.message.text or update.message.caption or ""

    if is_allowed(user_id):
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return
    except Exception:
        pass

    violation = False
    reason = ""

    if re.search(LINK_PATTERN, text):
        violation = True
        reason = "🔗 Uɴᴀᴜᴛʜᴏʀɪᴢᴇᴅ Lɪɴᴋ"

    if not violation:
        for word in BAD_WORDS:
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, text, re.IGNORECASE):
                violation = True
                reason = "🔞 Iɴᴀᴘᴘʀᴏᴘʀɪᴀᴛᴇ Cᴏɴᴛᴇɴᴛ"
                break

    if violation:
        try:
            await update.message.delete()
            warn_count = increment_warns(user_id)

            if warn_count >= 3:
                await context.bot.ban_chat_member(chat_id, user_id)
                reset_warns(user_id)
                report = (
                    f"🚫 <b>sᴇᴄᴜʀɪᴛʏ ᴀᴄᴛɪᴏɴ</b>\n\n"
                    f"👤 ɴᴀᴍᴇ: {user.first_name}\n"
                    f"🆔 ɪᴅ: <code>{user_id}</code>\n"
                    f"⚖️ ᴀᴄᴛɪᴏɴ: ʙᴀɴɴᴇᴅ 🔨\n"
                    f"🌀 ʀᴇᴀsᴏɴ: {reason} (ʀᴇᴀᴄʜᴇᴅ 3 ᴡᴀʀɴs)"
                )
                await context.bot.send_message(chat_id=chat_id, text=report, parse_mode='HTML')
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ {user.first_name}, {reason} ɪs ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ!\n"
                         f"ᴀᴄᴛɪᴏɴ: ᴍᴇssᴀɢᴇ ᴅᴇʟᴇᴛᴇᴅ 🗑️\nᴡᴀʀɴɪɴɢs: <code>{warn_count}/3</code>",
                    parse_mode='HTML'
                )
        except Exception as e:
            import logging
            logging.error(f"Sᴇᴄᴜʀɪᴛʏ Eʀʀᴏʀ: {e}")


async def allow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/allow <id> - Whitelist a user from security checks (owner or admins)."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    is_permitted = False
    if user_id == OWNER_ID:
        is_permitted = True
    else:
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                is_permitted = True
        except Exception:
            pass

    if not is_permitted:
        return await update.message.reply_text("❌ Oɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")

    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target_id = int(context.args[0])
        except ValueError:
            return await update.message.reply_text("❌ Gɪᴠᴇ ᴀ ᴠᴀʟɪᴅ Usᴇʀ ID.")

    if not target_id:
        return await update.message.reply_text("❌ Rᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴀ Usᴇʀ ID.")

    allowed_collection.update_one({"user_id": target_id}, {"$set": {"allowed": True}}, upsert=True)
    await update.message.reply_text(f"✅ Usᴇʀ `{target_id}` ɪs ɴᴏᴡ ᴀʟʟᴏᴡᴇᴅ ᴛᴏ ʙʏᴘᴀss sᴇᴄᴜʀɪᴛʏ.", parse_mode='Markdown')


# ================= RESOLVER / ADMIN HELPERS =================

async def resolve_user_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply > @mention (DB then Telegram) > raw ID."""
    msg = update.message
    args = context.args
    chat_id = update.effective_chat.id

    if msg.reply_to_message:
        return msg.reply_to_message.from_user.id, msg.reply_to_message.from_user.first_name

    if args:
        target = args[0]
        if target.isdigit():
            return int(target), "User"

        username = target.replace("@", "").lower()
        cached = users_collection.find_one({"username": username})
        if cached:
            return cached["id"], cached["name"]

        try:
            member = await context.bot.get_chat_member(chat_id, target)
            return member.user.id, member.user.first_name
        except Exception:
            pass

    return None, None


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    if user_id == OWNER_ID:
        return True
    chat_id = update.effective_chat.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]


async def is_user_allowed(chat, user_id):
    """Owner, group creator, or admin with promote rights."""
    if user_id == OWNER_ID:
        return True
    try:
        member = await chat.get_member(user_id)
        if member.status == 'creator':
            return True
        return member.status == 'administrator' and getattr(member, 'can_promote_members', False)
    except Exception:
        return False


# ================= BAN / KICK / UNBAN =================

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if chat.type == "private":
        return await message.reply_text("❌ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Cᴀɴ Bᴇ Uꜱᴇᴅ Oɴʟʏ Iɴ Gʀᴏᴜᴘ Cʜᴀᴛꜱ.")

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>/ban @username or reply</code>", parse_mode='HTML')

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        return await message.reply_text("🧐 Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ Bᴀɴ Oᴛʜᴇʀꜱ.")

    if target_id == OWNER_ID:
        return await message.reply_text("👑 I Wᴏɴ'ᴛ Bᴀɴ Mʏ Oᴡɴᴇʀ.")

    try:
        target_member = await chat.get_member(target_id)
        if target_member.status == 'creator':
            return await message.reply_text("👑 Tʜᴀᴛ'ꜱ Tʜᴇ Gʀᴏᴜᴘ Cʀᴇᴀᴛᴏʀ. I Cᴀɴ'ᴛ Tᴏᴜᴄʜ Tʜᴇᴍ.")
        if target_member.status == 'administrator':
            return await message.reply_text("⚠️ I Cᴀɴ'ᴛ Bᴀɴ Aᴅᴍɪɴꜱ. Dᴇᴍᴏᴛᴇ Tʜᴇᴍ Fɪʀꜱᴛ!")
        if target_member.status == 'kicked':
            return await message.reply_text(f"⚠️ <b>{name}</b> Iꜱ Aʟʀᴇᴀᴅʏ Bᴀɴɴᴇᴅ.", parse_mode='HTML')

        await chat.ban_member(target_id)
        await message.reply_text(f"🎖️ Uᴘᴅᴀᴛᴇᴅ Sᴛᴀᴛᴜꜱ: <b>{name}</b> ɪꜱ ɴᴏᴡ ʙᴀɴɴᴇᴅ!", parse_mode='HTML')
    except BadRequest as e:
        err = str(e).lower()
        if "not enough rights" in err or "admin_privileges" in err:
            await message.reply_text("❌ I Dᴏɴ'ᴛ Hᴀᴠᴇ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ Bᴀɴ Uꜱᴇʀꜱ.")
        else:
            await message.reply_text(f"❌ API Eʀʀᴏʀ: {err}")


async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if chat.type == "private":
        return await message.reply_text("❌ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Cᴀɴ Bᴇ Uꜱᴇᴅ Oɴʟʏ Iɴ Gʀᴏᴜᴘ Cʜᴀᴛꜱ.")

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>/kick @username or reply</code>", parse_mode='HTML')

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        return await message.reply_text("🧐 Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ Kɪᴄᴋ Oᴛʜᴇʀꜱ.")

    if target_id == OWNER_ID:
        return await message.reply_text("👑 Oᴏᴘꜱ I Cᴀɴ'ᴛ Kɪᴄᴋ Tʜᴇ Bᴏꜱꜱ ☠️")

    try:
        target_member = await chat.get_member(target_id)
        if target_member.status in ['creator', 'administrator']:
            return await message.reply_text("⚠️ I Cᴀɴ'ᴛ Kɪᴄᴋ Aᴅᴍɪɴꜱ Oʀ Tʜᴇ Oᴡɴᴇʀ.")
        if target_member.status in ['left', 'kicked']:
            return await message.reply_text(f"⚠️ <b>{name}</b> Iꜱ Nᴏᴛ Iɴ Tʜᴇ Cʜᴀᴛ.", parse_mode='HTML')

        await chat.ban_member(target_id)
        await chat.unban_member(target_id)
        await message.reply_text(f"🎖️ Uᴘᴅᴀᴛᴇᴅ Sᴛᴀᴛᴜꜱ: <b>{name}</b> ɪꜱ ɴᴏᴡ ᴋɪᴄᴋᴇᴅ!", parse_mode='HTML')
    except BadRequest as e:
        err = str(e).lower()
        if "not enough rights" in err or "admin_privileges" in err:
            await message.reply_text("❌ I Dᴏɴ'ᴛ Hᴀᴠᴇ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ Kɪᴄᴋ Uꜱᴇʀꜱ.")
        else:
            await message.reply_text(f"❌ API Eʀʀᴏʀ: {err}")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if chat.type == "private":
        return await message.reply_text("❌ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Cᴀɴ Bᴇ Uꜱᴇᴅ Oɴʟʏ Iɴ Gʀᴏᴜᴘ Cʜᴀᴛꜱ.")

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>/unban @username or reply</code>", parse_mode='HTML')

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        return await message.reply_text("🧐 Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ Uɴʙᴀɴ Oᴛʜᴇʀꜱ.")

    try:
        target_member = await chat.get_member(target_id)
        if target_member.status in ['member', 'administrator', 'creator', 'restricted']:
            return await message.reply_text(f"⚠️ <b>{name}</b> Iꜱ Nᴏᴛ Bᴀɴɴᴇᴅ.", parse_mode='HTML')

        await chat.unban_member(target_id, only_if_banned=True)
        await message.reply_text(f"🎖️ Uᴘᴅᴀᴛᴇᴅ Sᴛᴀᴛᴜꜱ: <b>{name}</b> ɪꜱ ɴᴏᴡ ᴜɴʙᴀɴɴᴇᴅ!", parse_mode='HTML')
    except BadRequest as e:
        err = str(e).lower()
        if "not enough rights" in err or "admin_privileges" in err:
            await message.reply_text("❌ I Dᴏɴ'ᴛ Hᴀᴠᴇ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ Uɴʙᴀɴ Uꜱᴇʀꜱ.")
        elif "user_id_invalid" in err:
            await message.reply_text("❌ Iɴᴠᴀʟɪᴅ Uꜱᴇʀ ID.")
        else:
            await message.reply_text(f"❌ API Eʀʀᴏʀ: {err}")


# ================= MUTE / UNMUTE / TMUTE =================

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if chat.type == "private":
        return await message.reply_text("❌ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Cᴀɴ Bᴇ Uꜱᴇᴅ Oɴʟʏ Iɴ Gʀᴏᴜᴘ Cʜᴀᴛꜱ.")

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>/mute @username or reply</code>", parse_mode='HTML')

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        return await message.reply_text("🧐 Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ Mᴜᴛᴇ Oᴛʜᴇʀꜱ.")
    if target_id == OWNER_ID:
        return await message.reply_text("👑 I Cᴀɴ'ᴛ Mᴜᴛᴇ Mʏ Oᴡɴᴇʀ.")

    try:
        target_member = await chat.get_member(target_id)
        if target_member.status in ['creator', 'administrator']:
            return await message.reply_text("🪵 I Cᴀɴ'ᴛ Mᴜᴛᴇ Aᴅᴍɪɴꜱ.")
        if target_member.status == 'restricted' and not target_member.can_send_messages:
            return await message.reply_text(f"⚠️ <b>{name}</b> Iꜱ Aʟʀᴇᴀᴅʏ Mᴜᴛᴇᴅ.", parse_mode='HTML')

        await chat.restrict_member(target_id, permissions=ChatPermissions(can_send_messages=False))
        await message.reply_text(f"🎖️ Uᴘᴅᴀᴛᴇᴅ Sᴛᴀᴛᴜꜱ: <b>{name}</b> ɪꜱ ɴᴏᴡ ᴍᴜᴛᴇᴅ!", parse_mode='HTML')
    except BadRequest as e:
        err = str(e).lower()
        if "not enough rights" in err or "admin_privileges" in err:
            await message.reply_text("❌ I Dᴏɴ'ᴛ Hᴀᴠᴇ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ Mᴜᴛᴇ Uꜱᴇʀꜱ.")
        else:
            await message.reply_text(f"❌ API Eʀʀᴏʀ: {err}")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if chat.type == "private":
        return await message.reply_text("❌ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Cᴀɴ Bᴇ Uꜱᴇᴅ Oɴʟʏ Iɴ Gʀᴏᴜᴘ Cʜᴀᴛꜱ.")

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>/unmute @username or reply</code>", parse_mode='HTML')

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        return await message.reply_text("🧐 Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ Uɴᴍᴜᴛᴇ Oᴛʜᴇʀꜱ.")

    try:
        target_member = await chat.get_member(target_id)
        if target_member.status in ['member', 'administrator', 'creator'] and getattr(target_member, 'can_send_messages', True):
            return await message.reply_text(f"⚠️ <b>{name}</b> Iꜱ Nᴏᴛ Mᴜᴛᴇᴅ.", parse_mode='HTML')

        await chat.restrict_member(
            target_id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_invite_users=True
            )
        )
        await message.reply_text(f"🎖️ Uᴘᴅᴀᴛᴇᴅ Sᴛᴀᴛᴜꜱ: <b>{name}</b> ɪꜱ ɴᴏᴡ ᴜɴᴍᴜᴛᴇᴅ!", parse_mode='HTML')
    except BadRequest as e:
        err = str(e).lower()
        if "not enough rights" in err or "admin_privileges" in err:
            await message.reply_text("❌ I Dᴏɴ'ᴛ Hᴀᴠᴇ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ Uɴᴍᴜᴛᴇ Uꜱᴇʀꜱ.")
        else:
            await message.reply_text(f"❌ API Eʀʀᴏʀ: {err}")


async def tmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import time as _time
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        return

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return

    if not context.args:
        await message.reply_text("<code>⚠️ ᴜsᴀɢᴇ: /ᴛᴍᴜᴛᴇ [ᴛɪᴍᴇ] (ᴇ.ɢ. 30ᴍ, 1ʜ, 1ᴅ)</code>", parse_mode='HTML')
        return

    time_str = context.args[-1].lower()
    match = re.match(r"(\d+)(m|h|d)", time_str)
    if not match:
        await message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ᴛɪᴍᴇ ғᴏʀᴍᴀᴛ (ᴜsᴇ ᴍ, ʜ, ᴏʀ ᴅ)")
        return

    amount = int(match.group(1))
    unit = match.group(2)
    seconds = amount * {"m": 60, "h": 3600, "d": 86400}[unit]
    until_date = int(_time.time()) + seconds

    try:
        await chat.restrict_member(target_id, permissions=ChatPermissions(can_send_messages=False), until_date=until_date)
        response = f"ᴜsᴇʀ: <b>{name}</b>\nsᴛᴀᴛᴜs: ᴛᴇᴍᴘ-ᴍᴜᴛᴇᴅ\nᴅᴜʀᴀᴛɪᴏɴ: {amount}{unit.upper()}"
        await message.reply_text(response, parse_mode='HTML')
    except BadRequest as e:
        await message.reply_text(f"❌ API ᴇʀʀᴏʀ: {str(e).lower()}")


# ================= WARN / UNWARN =================

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        await update.message.reply_text("🧐 Oᴘᴘs! Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ Wᴀʀɴ Oᴛʜᴇʀs... 🧩")
        return

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        await update.message.reply_text("<code>🧩 Rᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴏʀ ᴘʀᴏᴠɪᴅᴇ ᴀɴ ID.</code>", parse_mode='HTML')
        return

    try:
        target_member = await chat.get_member(target_id)
        if target_id == OWNER_ID:
            await update.message.reply_text("👑 Eʜᴇʜᴇ... Tʜᴀᴛ's Mʏ Oᴡɴᴇʀ! I Cᴀɴ'ᴛ Wᴀʀɴ Tʜᴇ Kɪɴɢ. 🫠")
            return
        if target_member.status == 'creator':
            await update.message.reply_text("👑 Gʀᴏᴜᴘ Oᴡɴᴇʀ Cᴀɴ'ᴛ Bᴇ Wᴀʀɴᴇᴅ. Tʜᴇʏ Mᴀᴋᴇ Tʜᴇ Rᴜʟᴇs!")
            return
        if target_member.status == 'administrator':
            await update.message.reply_text("⚠️ Yᴏᴜ Cᴀɴ'ᴛ Wᴀʀɴ A Fᴇʟʟᴏᴡ Aᴅᴍɪɴ! 🙀")
            return
    except Exception:
        pass

    res = admins_db.find_one_and_update(
        {"chat_id": chat.id, "user_id": target_id},
        {"$inc": {"warns": 1}}, upsert=True, return_document=True
    )
    warn_count = res.get("warns", 0)

    if warn_count >= 3:
        try:
            await chat.ban_member(target_id)
            admins_db.update_one({"chat_id": chat.id, "user_id": target_id}, {"$set": {"warns": 0}})
            await update.message.reply_text(f"<b>🛑 {name} ʀᴇᴀᴄʜᴇᴅ 3 ᴡᴀʀɴs ᴀɴᴅ ᴡᴀs ʙᴀɴɴᴇᴅ!</b>", parse_mode='HTML')
        except BadRequest:
            await update.message.reply_text("❌ I ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ʙᴀɴ ᴛʜɪs ᴜsᴇʀ!")
    else:
        await update.message.reply_text(f"<b>⚠️ {name} ʜᴀs ʙᴇᴇɴ ᴡᴀʀɴᴇᴅ. ({warn_count}/3)</b>", parse_mode='HTML')


async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        await update.message.reply_text("🧐 Oᴘᴘs! Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ Rᴇsᴇᴛ Wᴀʀɴs... 🧩")
        return

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return

    admins_db.update_one({"chat_id": chat.id, "user_id": target_id}, {"$set": {"warns": 0}})
    await update.message.reply_text(f"<b>✅ ᴡᴀʀɴs ғᴏʀ {name} ʜᴀs ʙᴇᴇɴ ʀᴇsᴇᴛ.</b>", parse_mode='HTML')


# ================= PROMOTE / DEMOTE / TITLE =================

async def promote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    args = context.args

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ:<code> /promote @username or reply [1/2/3]</code>", parse_mode=ParseMode.HTML)

    try:
        target_member = await chat.get_member(target_id)
        if target_member.status == 'creator':
            return await message.reply_text("👑 Gʀᴏᴜᴘ Oᴡɴᴇʀ Cᴀɴ'ᴛ Bᴇ Pʀᴏᴍᴏᴛᴇᴅ.")
        if target_member.status == 'administrator':
            return await message.reply_text("🎗️ Uꜱᴇʀ Iꜱ Aʟʀᴇᴀᴅʏ Aɴ Aᴅᴍɪɴ.")

        if not await is_user_allowed(chat, user.id):
            return await message.reply_text("⚠️ Oɴʟʏ Aᴅᴍɪɴꜱ Cᴀɴ Pʀᴏᴍᴏᴛᴇ Uꜱᴇʀꜱ. 🧩")

        bot_member = await chat.get_member(context.bot.id)
        if not getattr(bot_member, 'can_promote_members', False):
            return await message.reply_text("💠 I Dᴏɴᴛ Hᴀᴠᴇ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ Pʀᴏᴍᴏᴛᴇ Uꜱᴇʀꜱ.")

        level = 1
        if args:
            val = args[-1]
            if val in ("3", "full"):
                level = 3
            elif val in ("2", "mod"):
                level = 2
            elif val == "0":
                level = 0

        perms = {
            0: {"can_pin_messages": True},
            1: {"can_change_info": True, "can_delete_messages": True, "can_invite_users": True,
                "can_pin_messages": True, "can_manage_chat": True, "can_manage_video_chats": True},
            2: {"can_change_info": True, "can_delete_messages": True, "can_invite_users": True,
                "can_pin_messages": True, "can_manage_chat": True, "can_restrict_members": True,
                "can_manage_video_chats": True, "can_post_stories": True, "can_edit_stories": True,
                "can_delete_stories": True},
            3: {"can_change_info": True, "can_delete_messages": True, "can_invite_users": True,
                "can_pin_messages": True, "can_manage_chat": True, "can_restrict_members": True,
                "can_promote_members": True, "can_manage_video_chats": True, "can_post_stories": True,
                "can_edit_stories": True, "can_delete_stories": True},
        }
        await context.bot.promote_chat_member(chat.id, target_id, **perms[level])

        access_map = {3: "Fᴜʟʟ Pᴏᴡᴇʀ", 2: "Sᴛᴀɴᴅᴀʀᴅ", 1: "Jᴜɴɪᴏʀ", 0: "Pin Only"}
        await message.reply_text(f"🎖️ <b>{name}</b> Pʀᴏᴍᴏᴛᴇ Tᴏ <b>{access_map[level]}</b>!", parse_mode=ParseMode.HTML)
    except BadRequest as e:
        await message.reply_text(f"❌ Eʀʀᴏʀ: {e}")


async def demote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>/demote @username or reply</code>", parse_mode=ParseMode.HTML)

    if not await is_user_allowed(chat, user.id):
        return await message.reply_text("⚠️ Oɴʟʏ Aᴅᴍɪɴꜱ Cᴀɴ Dᴇᴍᴏᴛᴇ Uꜱᴇʀꜱ!", parse_mode=ParseMode.HTML)

    try:
        bot_member = await chat.get_member(context.bot.id)
        if not getattr(bot_member, 'can_promote_members', False):
            return await message.reply_text("⚠️ I Nᴇᴇᴅ Aᴅᴅ Nᴇᴡ Aᴅᴍɪɴꜱ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ Dᴇᴍᴏᴛᴇ Uꜱᴇʀꜱ.", parse_mode=ParseMode.HTML)

        target_member = await chat.get_member(target_id)
        if target_member.user.is_bot:
            return await message.reply_text("👀 I Cᴀɴɴᴏᴛ Dᴇᴍᴏᴛᴇ Bᴏᴛꜱ. 👾")
        if target_member.status == 'creator':
            return await message.reply_text("👑 Gʀᴏᴜᴘ Oᴡɴᴇʀ Cᴀɴ'ᴛ Bᴇ Dᴇᴍᴏᴛᴇᴅ.")
        if target_member.status != 'administrator':
            return await message.reply_text(f"⚠️ <b>{name}</b> Iꜱ Nᴏᴛ Aɴ Aᴅᴍɪɴ!", parse_mode=ParseMode.HTML)

        await context.bot.promote_chat_member(
            chat.id, target_id,
            can_change_info=False, can_delete_messages=False, can_invite_users=False,
            can_restrict_members=False, can_pin_messages=False, can_promote_members=False,
            can_manage_chat=False, can_manage_video_chats=False
        )
        await message.reply_text(f"🎖️ <b>{name}</b> Hᴀꜱ Bᴇᴇɴ Dᴇᴍᴏᴛᴇᴅ! 🥱", parse_mode=ParseMode.HTML)
    except BadRequest as e:
        err = str(e).lower()
        if "not enough rights" in err or "chat_admin_required" in err:
            await message.reply_text(
                "⚠️ I Cᴀɴ'ᴛ Dᴇᴍᴏᴛᴇ Tʜɪꜱ Aᴅᴍɪɴ. Tʜᴇʏ Mɪɢʜᴛ Hᴀᴠᴇ Bᴇᴇɴ Pʀᴏᴍᴏᴛᴇᴅ Bʏ Tʜᴇ Aɴᴏᴛʜᴇʀ Aᴅᴍɪɴ.",
                parse_mode=ParseMode.HTML
            )
        else:
            await message.reply_text(f"❌ API Eʀʀᴏʀ: {e}")


async def set_admin_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    args = context.args

    target_id, name = await resolve_user_all(update, context)
    if not target_id:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ:<code> /title @username [text] or reply</code>", parse_mode=ParseMode.HTML)

    if message.reply_to_message:
        title = " ".join(args)
    else:
        title = " ".join(args[1:]) if len(args) > 1 else ""

    if not title:
        return await message.reply_text("✨ Pʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴛɪᴛʟᴇ!")

    if not await is_user_allowed(chat, user.id):
        return await message.reply_text("🪢 Oɴʟʏ Aᴅᴍɪɴꜱ Cᴀɴ Cʜᴀɴɢᴇ Tɪᴛʟᴇ!")

    try:
        await context.bot.set_chat_administrator_custom_title(chat.id, target_id, title)
        await message.reply_text(f"✅ ᴛɪᴛʟᴇ ᴜᴘᴅᴀᴛᴇᴅ to: <b>{title}</b>", parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "Not enough rights" in str(e):
            await message.reply_text("❌ I Cᴀɴᴛ Cʜᴀɴɢᴇ Tʜᴇ Uꜱᴇʀ Tɪᴛʟᴇ, Tʜᴇʏ Mɪɢʜᴛ Pʀᴏᴍᴏᴛᴇᴅ Oᴛʜᴇʀ Tʜᴀɴ Mᴇ.")
        else:
            await message.reply_text(f"❌ Eʀʀᴏʀ: {e}")


# ================= PIN / UNPIN / PURGE =================

async def pin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if chat.type != "private" and user.id != OWNER_ID and not await is_admin(update, context, user.id):
        return await message.reply_text("🧐 Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ Pɪɴ Mᴇꜱꜱᴀɢᴇꜱ.")

    if not message.reply_to_message:
        return await message.reply_text("⚠️ Uꜱᴀɢᴇ: <code>ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ᴘɪɴ ɪᴛ</code>", parse_mode='HTML')

    try:
        target_user = message.reply_to_message.from_user
        name = target_user.first_name if target_user else "Sʏꜱᴛᴇᴍ"
        await context.bot.pin_chat_message(chat_id=chat.id, message_id=message.reply_to_message.message_id, disable_notification=False)
        await message.reply_text(f"🎖️ Uᴘᴅᴀᴛᴇᴅ Sᴛᴀᴛᴜꜱ: <b>{name}'ꜱ</b> ᴍᴇꜱꜱᴀɢᴇ ɪꜱ ɴᴏᴡ ᴘɪɴɴᴇᴅ!", parse_mode='HTML')
    except BadRequest as e:
        err = str(e).lower()
        if "not enough rights" in err or "admin_privileges" in err:
            await message.reply_text("❌ I Dᴏɴ'ᴛ Hᴀᴠᴇ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ Pɪɴ Mᴇꜱꜱᴀɢᴇꜱ.")
        else:
            await message.reply_text(f"❌ API Eʀʀᴏʀ: {err}")


async def unpin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if chat.type != "private" and user.id != OWNER_ID and not await is_admin(update, context, user.id):
        return await message.reply_text("🧐 Yᴏᴜ Nᴇᴇᴅ Tᴏ Bᴇ Aᴅᴍɪɴ Tᴏ UɴPɪɴ Mᴇꜱꜱᴀɢᴇꜱ.")

    try:
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            name = target_user.first_name if target_user else "Sʏꜱᴛᴇᴍ"
            await context.bot.unpin_chat_message(chat_id=chat.id, message_id=message.reply_to_message.message_id)
        else:
            name = "Lᴀᴛᴇꜱᴛ Pɪɴ"
            await context.bot.unpin_chat_message(chat_id=chat.id)

        await message.reply_text(f"🎖️ Uᴘᴅᴀᴛᴇᴅ Sᴛᴀᴛᴜꜱ: <b>{name}</b> ɪꜱ ɴᴏᴡ ᴜɴᴘɪɴɴᴇᴅ!", parse_mode='HTML')
    except BadRequest as e:
        err = str(e).lower()
        if "not enough rights" in err or "admin_privileges" in err:
            await message.reply_text("❌ I Dᴏɴ'ᴛ Hᴀᴠᴇ Pᴇʀᴍɪꜱꜱɪᴏɴ Tᴏ UɴPɪɴ Mᴇꜱꜱᴀɢᴇꜱ.")
        elif "no message to unpin" in err:
            await message.reply_text("⚠️ Tʜᴇʀᴇ Aʀᴇ Nᴏ Pɪɴɴᴇᴅ Mᴇꜱꜱᴀɢᴇꜱ Tᴏ Rᴇᴍᴏᴠᴇ.")
        else:
            await message.reply_text(f"❌ API Eʀʀᴏʀ: {err}")


async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if user.id != OWNER_ID and not await is_admin(update, context, user.id):
        await message.reply_text("🧐 ᴏᴘᴘs ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ʙᴇ ᴀᴅᴍɪɴ ᴛᴏ ᴘᴜʀɢᴇ")
        return

    if not message.reply_to_message:
        await message.reply_text("<code>⚠️ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ sᴛᴀʀᴛ ᴘᴜʀɢᴇ ғʀᴏᴍ ᴛʜᴇʀᴇ</code>", parse_mode='HTML')
        return

    try:
        message_id = message.reply_to_message.message_id
        delete_ids = list(range(message_id, message.message_id))
        for i in range(0, len(delete_ids), 100):
            await context.bot.delete_messages(chat_id=chat.id, message_ids=delete_ids[i:i + 100])
        await message.delete()
        await chat.send_message("sᴛᴀᴛᴜs: ᴘᴜʀɢᴇ ᴄᴏᴍᴘʟᴇᴛᴇ")
    except BadRequest as e:
        await message.reply_text(f"❌ API ᴇʀʀᴏʀ: {str(e).lower()}")
