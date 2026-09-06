#!/usr/bin/env python3
"""Owner-only tools: DB reset menu, broadcasting, user/group listing,
block/unblock, premium activate/deactivate, custom icons, stats, misc."""

import re
import html
import time
import random
import string
import asyncio
import logging
import psutil
import os
from datetime import datetime, timezone, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputSticker
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.config import OWNER_ID, users, db, async_db, image_db, BOT_START_TIME
from bot.helpers import get_user, save_user, is_premium

# ============================ RESET SYSTEM ============================

RESET_TARGETS = {
    "coins": {"label": "💰 Coins", "desc": "Resets every user's coins back to 100 (starter balance).", "scope": "users"},
    "kills": {"label": "⚔️ Kills", "desc": "Wipes all kill counts (sets to 0).", "scope": "users"},
    "xp": {"label": "✨ XP", "desc": "Resets XP to 0 for every user.", "scope": "users"},
    "level": {"label": "🎖 Level", "desc": "Resets level to 1 for every user.", "scope": "users"},
    "inventory": {"label": "🎒 Inventory", "desc": "Clears every user's item inventory.", "scope": "users"},
    "warned": {"label": "⚠️ Warns", "desc": "Clears all warn counts from the users collection.", "scope": "users"},
    "premium": {"label": "💎 Premium", "desc": "Revokes premium status and expiry from all users.", "scope": "users"},
    "claimed_groups": {"label": "🏠 Claimed Groups", "desc": "Clears the list of groups each user has claimed.", "scope": "users"},
    "old_names": {"label": "📛 Name History", "desc": "Wipes stored old-name history for every user.", "scope": "users"},
    "blocked": {"label": "🚫 Blocked Flags", "desc": "Un-blocks every user (sets blocked=False).", "scope": "users"},
    "snake_scores": {"label": "🐍 Snake Scores", "desc": "Deletes all snake_sessions arrays from every user.", "scope": "users"},
    "referral_data": {"label": "🔗 Referral Data", "desc": "Drops the entire referral_codes collection.", "scope": "collection", "collection": "referral_codes"},
    "redeem_codes": {"label": "🎫 Redeem Codes", "desc": "Drops the entire redeem_codes collection.", "scope": "collection", "collection": "redeem_codes"},
    "feedbacks": {"label": "📝 Feedbacks", "desc": "Drops the entire feedbacks collection.", "scope": "collection", "collection": "feedbacks"},
    "torture_registry": {"label": "🔒 Torture Registry", "desc": "Drops the torture_registry collection.", "scope": "collection", "collection": "torture_registry"},
    "heists": {"label": "🏦 Heists", "desc": "Drops the heists collection.", "scope": "collection", "collection": "heists"},
    "designs": {"label": "🎨 Designs", "desc": "Drops all uploaded designs from the designs collection.", "scope": "collection", "collection": "designs"},
    "users_data": {"label": "👤 Users Data", "desc": "Drops the ENTIRE users collection. All profiles gone.", "scope": "nuke_collection", "collection": "users"},
    "wipe_all": {"label": "💣 WIPE ALL",
                 "desc": ("⚠️ DANGER: Drops users, referral_codes, redeem_codes, feedbacks, torture_registry, heists, "
                          "designs AND clears snake_sessions/kills/coins/xp/level on every document. This is irreversible."),
                 "scope": "wipe_all"},
}


async def _do_reset(target: str) -> str:
    cfg = RESET_TARGETS[target]
    scope = cfg["scope"]

    if scope == "users":
        field_defaults = {
            "coins": {"coins": 100}, "kills": {"kills": 0}, "xp": {"xp": 0}, "level": {"level": 1},
            "inventory": {"inventory": []}, "warned": {"warns": 0},
            "premium": {"premium": False, "premium_until": None, "membership_type": None},
            "claimed_groups": {"claimed_groups": []}, "old_names": {"old_names": []}, "blocked": {"blocked": False},
            "snake_scores": {},
        }
        if target == "snake_scores":
            res = await async_db["users"].update_many({}, {"$unset": {"snake_sessions": ""}})
        else:
            res = await async_db["users"].update_many({}, {"$set": field_defaults[target]})
        return f"✅ <b>{cfg['label']}</b> reset — {res.modified_count} users affected."

    elif scope == "collection":
        await async_db[cfg["collection"]].drop()
        return f"✅ <b>{cfg['label']}</b> collection dropped."

    elif scope == "nuke_collection":
        await async_db[cfg["collection"]].drop()
        return f"✅ <b>{cfg['label']}</b> — entire users collection dropped."

    elif scope == "wipe_all":
        nuked = []
        for col_name in ["users", "referral_codes", "redeem_codes", "feedbacks", "torture_registry", "heists", "designs"]:
            await async_db[col_name].drop()
            nuked.append(col_name)
        return f"💣 <b>WIPE ALL complete.</b>\nDropped collections: <code>{', '.join(nuked)}</code>"

    return "❓ Unknown scope — nothing was changed."


async def cmd_resetlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Owner only.")
        return

    lines = ["📋 <b>Resettable Targets</b>\n", "Use: <code>/reset &lt;target&gt;</code>\n"]
    sections = {"👤 User Fields (partial reset)": [], "🗄 Full Collection Wipes": [], "☢️ Nuclear Options": []}

    for key, cfg in RESET_TARGETS.items():
        scope = cfg["scope"]
        entry = f"• <code>/reset {key}</code> — {cfg['label']}\n  ↳ {cfg['desc']}"
        if scope == "users":
            sections["👤 User Fields (partial reset)"].append(entry)
        elif scope == "collection":
            sections["🗄 Full Collection Wipes"].append(entry)
        else:
            sections["☢️ Nuclear Options"].append(entry)

    for section_title, entries in sections.items():
        if entries:
            lines.append(f"\n<b>{section_title}</b>")
            lines.extend(entries)

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


USAGE_TEXT = (
    "⚙️ <b>/reset — Usage Guide</b>\n\n"
    "<b>Syntax:</b> <code>/reset &lt;target&gt;</code>\n\n"
    "<b>Quick Examples:</b>\n"
    "• <code>/reset coins</code> — Reset all coins to 100\n"
    "• <code>/reset kills</code> — Wipe kill counts\n"
    "• <code>/reset snake_scores</code> — Clear snake sessions\n"
    "• <code>/reset xp</code> — Reset XP to 0\n"
    "• <code>/reset level</code> — Reset levels to 1\n"
    "• <code>/reset inventory</code> — Clear inventories\n"
    "• <code>/reset warned</code> — Clear all warns\n"
    "• <code>/reset premium</code> — Revoke all premium\n"
    "• <code>/reset blocked</code> — Unblock all users\n"
    "• <code>/reset referral_data</code> — Wipe referrals\n"
    "• <code>/reset redeem_codes</code> — Wipe redeem codes\n"
    "• <code>/reset feedbacks</code> — Wipe feedbacks\n"
    "• <code>/reset heists</code> — Wipe heist data\n"
    "• <code>/reset designs</code> — Wipe uploaded designs\n"
    "• <code>/reset users_data</code> — ⚠️ Drop entire users DB\n"
    "• <code>/reset wipe_all</code> — 💣 Nuke EVERYTHING\n\n"
    "📋 See full list: <code>/resetlist</code>"
)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ This command is for the bot owner only.")
        return

    args = context.args
    if not args:
        await update.message.reply_text(USAGE_TEXT, parse_mode="HTML")
        return

    target = args[0].lower().strip()
    if target not in RESET_TARGETS:
        await update.message.reply_text(
            f"❓ <b>Unknown target:</b> <code>{target}</code>\n\nRun <code>/resetlist</code> to see all valid targets.",
            parse_mode="HTML"
        )
        return

    DANGEROUS = {"users_data", "wipe_all"}
    if target in DANGEROUS:
        confirm = args[1].lower() if len(args) > 1 else ""
        if confirm != "confirm":
            cfg = RESET_TARGETS[target]
            await update.message.reply_text(
                f"⚠️ <b>Dangerous Operation: {cfg['label']}</b>\n\n{cfg['desc']}\n\n"
                f"This <b>cannot be undone</b>.\nTo proceed, type:\n<code>/reset {target} confirm</code>",
                parse_mode="HTML"
            )
            return

    await update.message.reply_text("⏳ Working...", parse_mode="HTML")
    try:
        result_msg = await _do_reset(target)
        await update.message.reply_text(result_msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ <b>Reset failed:</b> <code>{e}</code>", parse_mode="HTML")


# ============================ BLOCK / UNBLOCK ============================

async def block_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Oᴏᴘꜱ! Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Iꜱ Fᴏʀ Mʏ Oᴡɴᴇʀ Oɴʟʏ 😊")

    target_id = None
    target_name = "Uꜱᴇʀ"

    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
        target_name = target_user.first_name
    elif context.args:
        try:
            target_id = int(context.args[0])
            user_data = users.find_one({"id": target_id})
            target_name = user_data.get("name", f"Uꜱᴇʀ ({target_id})") if user_data else f"Uꜱᴇʀ ({target_id})"
        except ValueError:
            return await update.message.reply_text("❌ Pʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ Uꜱᴇʀ ID.")

    bot_id = context.bot.id
    if target_id == OWNER_ID:
        return await update.message.reply_text("Yᴏᴜ ᴄᴀɴ'ᴛ ʙʟᴏᴄᴋ ʏᴏᴜʀsᴇʟғ, Bᴏss! Tʜᴀᴛ's ᴀ ᴛʀᴀᴘ. ⛔")
    if target_id == bot_id:
        return await update.message.reply_text("Eʜ? Yᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙʟᴏᴄᴋ ᴍᴇ? I'ᴍ Yᴜᴜʀɪ! I ᴄᴀɴ'ᴛ ʙʟᴏᴄᴋ ᴍʏsᴇʟғ! 🌸")

    if target_id:
        users.update_one({"id": target_id}, {"$set": {"blocked": True}}, upsert=True)
        await update.message.reply_text(f"{target_name} Bʟᴏᴄᴋᴇᴅ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ✅")


async def unblock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Oᴏᴘꜱ! Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Iꜱ Fᴏʀ Mʏ Oᴡɴᴇʀ Oɴʟʏ 😊")

    target_id = None
    first_name = "Uꜱᴇʀ"
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        first_name = update.message.reply_to_message.from_user.first_name
    elif context.args:
        try:
            target_id = int(context.args[0])
            first_name = f"Uꜱᴇʀ ({target_id})"
        except ValueError:
            return await update.message.reply_text("❌ Pʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ Uꜱᴇʀ ID.")

    if target_id:
        users.update_one({"id": target_id}, {"$set": {"blocked": False}}, upsert=True)
        await update.message.reply_text(f"{first_name} Uɴʙʟᴏᴄᴋᴇᴅ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ✅")


# ============================ PREMIUM ACTIVATE/DEACTIVATE ============================

async def activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if user.id != OWNER_ID:
        return

    if not context.args or len(context.args) < 3:
        usage = ("⚠️ <b>Iɴᴠᴀʟɪᴅ Usᴀɢᴇ</b>\n\nUsᴇ: <code>/activate [premium|membership] [validity] [user_id]</code>\n"
                 "Exᴀᴍᴘʟᴇ: <code>/activate premium 15d 5773908061</code>")
        return await msg.reply_text(usage, parse_mode=ParseMode.HTML)

    type_choice = context.args[0].lower()
    validity_raw = context.args[1].lower()

    try:
        target_id = int(context.args[2])
    except ValueError:
        return await msg.reply_text("❌ <b>Iɴᴠᴀʟɪᴅ Usᴇʀ ID.</b>", parse_mode=ParseMode.HTML)

    match = re.match(r"(\d+)d", validity_raw)
    if not match:
        return await msg.reply_text("❌ <b>Usᴇ 'd' ғᴏʀ ᴅᴀʏs (ᴇ.ɢ., 30ᴅ).</b>", parse_mode=ParseMode.HTML)

    days_to_add = int(match.group(1))
    expiry_date = (datetime.utcnow() + timedelta(days=days_to_add)).strftime("%Y-%m-%d %H:%M:%S")

    result = users.update_one({"id": target_id}, {"$set": {"premium": True, "premium_until": expiry_date, "membership_type": type_choice}})
    if result.matched_count == 0:
        return await msg.reply_text("❌ <b>Usᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ Dᴀᴛᴀʙᴀsᴇ.</b>", parse_mode=ParseMode.HTML)

    await msg.reply_text(f"✅ <b>Pʀᴇᴍɪᴜᴍ Aᴄᴛɪᴠᴀᴛᴇᴅ!</b>\n👤 ID: <code>{target_id}</code>\n⏳ Dᴜʀᴀᴛɪᴏɴ: {days_to_add} days", parse_mode=ParseMode.HTML)

    try:
        dm_text = (
            "🎉 <b>Hᴇʏ! Yᴏᴜʀ Pʀᴇᴍɪᴜᴍ Hᴀs Bᴇᴇɴ Aᴄᴛɪᴠᴀᴛᴇᴅ!</b>\n\n"
            f"⏳ <b>Vᴀʟɪᴅɪᴛʏ:</b> {days_to_add} Dᴀʏs\n📅 <b>Exᴘɪʀᴇs ᴏɴ:</b> <code>{expiry_date}</code>\n\n"
            "Tʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ʏᴏᴜʀ sᴜᴘᴘᴏʀᴛ! ✨"
        )
        await context.bot.send_message(chat_id=target_id, text=dm_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"⚠️ <b>Aᴄᴛɪᴠᴀᴛᴇᴅ, ʙᴜᴛ ᴄᴏᴜʟᴅɴ'ᴛ DM ᴜsᴇʀ:</b> <code>{e}</code>", parse_mode=ParseMode.HTML)


async def deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if user.id != OWNER_ID:
        return

    if not context.args:
        return await msg.reply_text("⚠️ <b>Usᴇ:</b> <code>/deactivate [user_id]</code>", parse_mode=ParseMode.HTML)

    try:
        target_id = int(context.args[0])
    except ValueError:
        return await msg.reply_text("❌ <b>Iɴᴠᴀʟɪᴅ Usᴇʀ ID.</b>", parse_mode=ParseMode.HTML)

    result = users.update_one({"id": target_id}, {"$set": {"premium": False}, "$unset": {"premium_until": "", "membership_type": ""}})
    if result.matched_count == 0:
        return await msg.reply_text("❌ <b>Usᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ.</b>", parse_mode=ParseMode.HTML)

    await msg.reply_text(f"🚫 <b>Pʀᴇᴍɪᴜᴍ Dᴇᴀᴄᴛɪᴠᴀᴛᴇᴅ ғᴏʀ</b> <code>{target_id}</code>", parse_mode=ParseMode.HTML)

    try:
        await context.bot.send_message(chat_id=target_id, text="⚠️ <b>Yᴏᴜʀ Pʀᴇᴍɪᴜᴍ Hᴀꜱ Bᴇᴇɴ Dᴇᴀᴄᴛɪᴠᴀᴛᴇᴅ Bʏ Oᴡɴᴇʀ.</b>", parse_mode=ParseMode.HTML)
    except Exception:
        pass


# ============================ CUSTOM ICON ============================

BANNED_ICONS = ["🖕", "💩", "🤡", "❌", "🫧", "🫥", "🌚", "👾", "🤖", "🫦", "👅", "👄", "💢", "💨", "👤"]


async def set_icon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    user = update.effective_user
    data = get_user(user)

    if not is_premium(data, context):
        return await msg.reply_text("❌ <b>Tʜɪs ɪs ᴀ Pʀᴇᴍɪᴜᴍ-Oɴʟʏ ғᴇᴀᴛᴜʀᴇ!</b>\nUsᴇ /pay ᴛᴏ ᴜᴘɢʀᴀᴅᴇ.", parse_mode='HTML')

    if not context.args:
        return await msg.reply_text(
            "⚠️ <b>Uꜱᴀɢᴇ:</b> <code>/seticon <emoji></code>\n✨ <b>Exᴀᴍᴘʟᴇ:</b> <code>/seticon 🔥</code>",
            parse_mode='HTML'
        )

    new_icon = context.args[0]
    if new_icon in BANNED_ICONS:
        return await msg.reply_text(f"⚠️ <b>Tʜɪꜱ ɪᴄᴏɴ ({new_icon}) ɪꜱ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ.</b>\nPʟᴇᴀꜱᴇ ᴄʜᴏᴏꜱᴇ ᴀɴᴏᴛʜᴇʀ.", parse_mode='HTML')

    data["custom_icon"] = new_icon
    save_user(data)
    await msg.reply_text(f"✅ <b>Iᴄᴏɴ Uᴘᴅᴀᴛᴇᴅ!</b>\nYᴏᴜʀ ᴘʀᴏғɪʟᴇ ɪᴄᴏɴ ɪs ɴᴏᴡ: {new_icon}", parse_mode='HTML')


async def deny_icon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        return
    if not context.args:
        return await update.message.reply_text("⚠️ Uꜱᴀɢᴇ: /denyicon <emoji>")

    icon_to_block = context.args[0]
    if icon_to_block not in BANNED_ICONS:
        BANNED_ICONS.append(icon_to_block)
        await update.message.reply_text(f"🚫 Icon {icon_to_block} has been added to the blacklist.")
    else:
        await update.message.reply_text("ℹ️ Tʜɪꜱ Iᴄᴏɴ Iꜱ Aʟʀᴇᴀᴅʏ Bʟᴀᴄᴋʟɪꜱᴛᴇᴅ.")


# ============================ SET IMAGE FOR COMMAND ============================

async def set_png(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return

    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ, sᴛɪᴄᴋᴇʀ, ᴏʀ ɢɪғ!")
    if not context.args:
        return await update.message.reply_text("❌ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ɴᴀᴍᴇ.\nᴇx: <code>/sᴇᴛᴘɴɢ sᴛᴀʀᴛ</code>", parse_mode='HTML')

    img_name = context.args[0].lower()
    replied = update.message.reply_to_message
    file_id = None

    if replied.photo:
        file_id = replied.photo[-1].file_id
    elif replied.sticker:
        file_id = replied.sticker.file_id
    elif replied.animation:
        file_id = replied.animation.file_id
    elif replied.document:
        file_id = replied.document.file_id

    if not file_id:
        return await update.message.reply_text("❌ ɪ ᴄᴀɴ'ᴛ ꜰɪɴᴅ ᴀ ᴠᴀʟɪᴅ ꜰɪʟᴇ ɪᴅ ɪɴ ᴛʜᴀᴛ ᴍᴇssᴀɢᴇ.")

    await image_db.update_one(
        {"name": img_name}, {"$set": {"file_id": file_id, "set_by": user_id, "updated_at": datetime.now()}}, upsert=True
    )
    await update.message.reply_text(
        f"✅ <b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ꜱᴇᴛ!</b>\n\nᴛᴀɢ: <code>{img_name}</code>\n\nʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜsᴇ ᴛʜɪs ɪɴ ʏᴏᴜʀ ᴄᴏᴍᴍᴀɴᴅs.",
        parse_mode='HTML'
    )


# ============================ PERSONAL / LEAVE / STATS / PING ============================

async def leave_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("Aᴡᴡᴡ Sᴡᴇᴇᴛʏ Sɪʟʟʏ Uꜱᴇ Tʜɪꜱ Iɴ Gʀᴏᴜᴘꜱ ☺️")
        return

    group_name = chat.title
    await update.message.reply_text(f"🚪 Lᴇᴀᴠɪɴɢ {group_name} ... Bʏᴇ! 💥")
    await context.bot.leave_chat(chat_id=chat.id)


async def send_personal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Uꜱᴀɢᴇ: /ᴘᴇʀꜱᴏɴᴀʟ <ᴜꜱᴇʀɪᴅ> [ʀᴇᴘʟʏ|ᴍᴇꜱꜱᴀɢᴇ]\nᴏʙᴊᴇᴄᴛ Cᴀɴ Bᴇ Sᴇɴᴛ 📤\n"
            "1. ꜱᴛɪᴄᴋᴇʀ ( Rᴇᴘʟʏ )\n2. ᴍᴇꜱꜱᴀɢᴇ ( Rᴇᴘʟʏ|ɪɴ-ᴄᴏᴍᴍᴀɴᴅ )\n3. ᴇᴍᴏᴊɪ ( Rᴇᴘʟʏ|ɪɴ-ᴄᴏᴍᴍᴀɴᴅ )"
        )
        return

    try:
        target_id = context.args[0]
    except IndexError:
        await update.message.reply_text("⚠️ I need a UserID first!")
        return

    try:
        if update.message.reply_to_message:
            reply = update.message.reply_to_message
            await context.bot.copy_message(chat_id=target_id, from_chat_id=update.effective_chat.id, message_id=reply.message_id)
        elif len(context.args) > 1:
            text_to_send = " ".join(context.args[1:])
            await context.bot.send_message(chat_id=target_id, text=text_to_send)
        else:
            await update.message.reply_text("❓ Nothing to send. Reply to something or type text.")
            return

        await update.message.reply_text(f"✅ Oʙᴊᴇᴄᴛ Sᴇɴᴛ Tᴏ `{target_id}` 🚀")
    except Exception as e:
        await update.message.reply_text(f"❌ Fᴀɪʟᴇᴅ Tᴏ Dᴇʟɪᴠᴇʀ: {e}")


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import feedback_db
    user = update.effective_user
    if not context.args:
        return await update.message.reply_text("<code>⚠️ ᴜsᴀɢᴇ: /ғᴇᴇᴅʙᴀᴄᴋ [ʏᴏᴜʀ ᴍᴇssᴀɢᴇ]</code>", parse_mode=ParseMode.HTML)

    fb_text = " ".join(context.args)
    feedback_db.insert_one({"user_id": user.id, "username": user.username, "msg": fb_text, "date": datetime.now()})

    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"📩 <b>ɴᴇᴡ ғᴇᴇᴅʙᴀᴄᴋ!</b>\n\nғʀᴏᴍ: {user.first_name} (<code>{user.id}</code>)\nᴍsɢ: {fb_text}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Failed to notify owner: {e}")

    await update.message.reply_text("✅ <b>ᴛʜᴀɴᴋ ʏᴏᴜ! ʏᴏᴜʀ ғᴇᴇᴅʙᴀᴄᴋ ʜᴀs ʙᴇᴇɴ sᴇɴᴛ.</b>", parse_mode=ParseMode.HTML)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    now = datetime.now(timezone.utc)
    uptime_delta = now - BOT_START_TIME
    days = uptime_delta.days
    hours, remainder = divmod(uptime_delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{days}ᴅ {hours}ʜ {minutes}ᴍ {seconds}ꜱ"

    process = psutil.Process(os.getpid())
    ram_mb = round(process.memory_info().rss / (1024 ** 2), 1)
    sys_ram = psutil.virtual_memory()
    ram_str = f"{sys_ram.percent}% ({ram_mb} MB)"

    chats_col = db["chats"]
    groups = chats_col.count_documents({"type": {"$in": ["group", "supergroup"]}})
    private = chats_col.count_documents({"type": "private"})
    blocked = users.count_documents({"blocked": True})
    total_users = users.count_documents({})

    text = (
        "📊 **𝗬𝘂𝘂𝗿𝗶 𝗕𝗼𝘁 𝗦𝘁𝗮𝘁𝘀**\n\n"
        f"👥 Gʀᴏᴜᴘꜱ : `{groups}`\n💬 Cʜᴀᴛꜱ : `{private}`\n🧑‍💻 Tᴏᴛᴀʟ Uꜱᴇʀꜱ : `{total_users}`\n"
        f"⏱ Uᴘᴛɪᴍᴇ : `{uptime_str}`\n💾 Rᴀᴍ : `{ram_str}`\n\n🚫 Bʟᴏᴄᴋᴇᴅ Uꜱᴇʀꜱ : `{blocked}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    message = await update.message.reply_text("📡 Pɪɴɢɪɴɢ...")
    latency = round((time.time() - start_time) * 1000)
    await message.edit_text(f"<b>Pᴏɴɢ!</b> 🏓\n📡 Lᴀᴛᴇɴᴄʏ: <code>{latency}ms</code>", parse_mode='HTML')


async def owner_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Yᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ.")
        return

    help_text = (
        "👑 <b>Oᴡɴᴇʀ Hɪᴅᴅᴇɴ Cᴏᴍᴍᴀɴᴅs</b> 👑\n\n"
        "📡 <code>/ping</code> - Cʜᴇᴄᴋ ʙᴏᴛ ʟᴀᴛᴇɴᴄʏ\n📊 <code>/stats</code> - Vɪᴇᴡ ʙᴏᴛ ᴜsᴀɢᴇ\n\n"
        "<b>Aᴅᴍɪɴ Tᴏᴏʟs:</b>\n👤 <code>/personal [reply] &lt;user-id&gt;</code>\n🔡 <code>/font 1|2|3</code>\n"
        "🎟 <code>/create &lt;code&gt; &lt;limit&gt; &lt;item|coins|xp:amount&gt;</code>"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')


async def connect_log_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    group_id = update.effective_chat.id
    try:
        await async_db.settings.update_one({"config": "log_group"}, {"$set": {"group_id": group_id}}, upsert=True)
        await update.message.reply_text("✅ <b>Gʀᴏᴜᴘ Cᴏɴɴᴇᴄᴛᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\nPremium logs will now be sent to this chat.")
    except Exception as e:
        print(f"Database Error in /connect: {e}")


# ============================ ECONOMY OPEN/CLOSE ============================

async def close_economy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import groups_col
    from bot.moderation import is_admin
    chat = update.effective_chat
    user_id = update.effective_user.id

    if chat.type == "private":
        return await update.message.reply_text("❌ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iꜱ Fᴏʀ Gʀᴏᴜᴘꜱ Oɴʟʏ.")

    member = await chat.get_member(user_id)
    is_admin_status = member.status in ["administrator", "creator"]
    if not is_admin_status and user_id != OWNER_ID:
        return await update.message.reply_text("❌ Oɴʟʏ Aᴅᴍɪɴs Cᴀɴ Uꜱᴇ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ.")

    await groups_col.update_one({"chat_id": chat.id}, {"$set": {"economy_closed": True}}, upsert=True)
    await update.message.reply_text("🛑 **Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Cʟᴏsᴇᴅ**\n\nAʟʟ ᴇᴄᴏɴᴏᴍʏ ᴄᴏᴍᴍᴀɴᴅs ʜᴀᴠᴇ ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ.", parse_mode="Markdown")


async def open_economy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import groups_col
    chat = update.effective_chat
    user_id = update.effective_user.id

    if chat.type == "private":
        return await update.message.reply_text("❌ Tʜɪs Cᴏᴍᴍᴀɴᴅ Iꜱ Fᴏʀ Gʀᴏᴜᴘꜱ Oɴʟʏ.")

    member = await chat.get_member(user_id)
    is_admin_status = member.status in ["administrator", "creator"]
    if not is_admin_status and user_id != OWNER_ID:
        return await update.message.reply_text("❌ Oɴʟʏ Aᴅᴍɪɴs Cᴀɴ Uꜱᴇ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ.")

    await groups_col.update_one({"chat_id": chat.id}, {"$set": {"economy_closed": False}}, upsert=True)
    await update.message.reply_text("✅ **Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Oᴘᴇɴᴇᴅ**\n\nAʟʟ ᴇᴄᴏɴᴏᴍʏ ᴄᴏᴍᴍᴀɴᴅs ᴀʀᴇ ɴᴏᴡ ᴀᴄᴛɪᴠᴇ ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ.", parse_mode="Markdown")


# ============================ SAVED GROUPS ============================

async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import SAVED_GROUPS
    if not SAVED_GROUPS:
        return await update.message.reply_text("<b>⚠️ ɴᴏ ɢʀᴏᴜᴘs ʜᴀᴠᴇ ʙᴇᴇɴ sᴀᴠᴇᴅ ʏᴇᴛ.</b>", parse_mode='HTML')

    keyboard = []
    if 1 in SAVED_GROUPS:
        keyboard.append([InlineKeyboardButton(SAVED_GROUPS[1]["name"], url=SAVED_GROUPS[1]["url"])])
    row2 = [InlineKeyboardButton(SAVED_GROUPS[p]["name"], url=SAVED_GROUPS[p]["url"]) for p in [2, 3] if p in SAVED_GROUPS]
    if row2:
        keyboard.append(row2)
    row3 = [InlineKeyboardButton(SAVED_GROUPS[p]["name"], url=SAVED_GROUPS[p]["url"]) for p in [4, 5] if p in SAVED_GROUPS]
    if row3:
        keyboard.append(row3)
    if 6 in SAVED_GROUPS:
        keyboard.append([InlineKeyboardButton(SAVED_GROUPS[6]["name"], url=SAVED_GROUPS[6]["url"])])

    await update.message.reply_text("✨ <b>ᴊᴏɪɴ ᴏᴜʀ ᴏꜰꜰɪᴄɪᴀʟ ɢʀᴏᴜᴘꜱ</b> ✨", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def save_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import groups_collection, SAVED_GROUPS
    if update.effective_user.id != OWNER_ID:
        return
    args = context.args
    if len(args) < 3:
        return await update.message.reply_text("<code>⚠️ ᴜsᴀɢᴇ: /sᴀᴠᴇ [ɴᴀᴍᴇ] [ᴜʀʟ] [ᴘᴏs]</code>", parse_mode='HTML')

    try:
        pos = int(args[-1])
        url = args[-2]
        name = " ".join(args[:-2])
        groups_collection.update_one({"pos": pos}, {"$set": {"name": name, "url": url}}, upsert=True)
        SAVED_GROUPS[pos] = {"name": name, "url": url}
        await update.message.reply_text(f"✅ <b>ɢʀᴏᴜᴘ sᴀᴠᴇᴅ ᴛᴏ ᴘᴏsɪᴛɪᴏɴ {pos}</b>", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ ᴇʀʀᴏʀ: {e}")


async def del_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import groups_collection, SAVED_GROUPS
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        return await update.message.reply_text("<code>⚠️ ᴜsᴀɢᴇ: /ᴅᴇʟ [ᴘᴏsɪᴛɪᴏɴ]</code>", parse_mode='HTML')

    try:
        pos = int(context.args[0])
        groups_collection.delete_one({"pos": pos})
        if pos in SAVED_GROUPS:
            del SAVED_GROUPS[pos]
            await update.message.reply_text(f"🗑️ <b>ɢʀᴏᴜᴘ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ᴘᴏsɪᴛɪᴏɴ {pos}</b>", parse_mode='HTML')
        else:
            await update.message.reply_text("🧐 ɴᴏᴛʜɪɴɢ sᴀᴠᴇᴅ ᴀᴛ ᴛʜᴀᴛ ᴘᴏsɪᴛɪᴏɴ.")
    except Exception as e:
        await update.message.reply_text(f"❌ ᴇʀʀᴏʀ: {e}")


# ============================ USER LIST (paginated) ============================

async def list_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("ᴘʟᴇᴀsᴇ sᴘᴇᴄɪꜰʏ <b>ᴜsᴇʀs</b> ᴏʀ <b>ɢʀᴏᴜᴘs</b>", parse_mode="HTML")
        return
    choice = context.args[0].lower()
    await show_page(update, context, choice, page=1)


async def show_page(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str, page: int):
    limit = 10
    skip = (page - 1) * limit
    try:
        if choice == "users":
            collection = async_db["users"]
            query = {}
            title = "ᴜsᴇʀ ʟɪsᴛ"
        elif choice == "groups":
            collection = async_db["chats"]
            query = {"type": {"$in": ["group", "supergroup"]}}
            title = "ɢʀᴏᴜᴘ ʟɪsᴛ"
        else:
            return

        total = await collection.count_documents(query)
        cursor = collection.find(query).skip(skip).limit(limit)
        data = await cursor.to_list(length=limit)

        if not data:
            await update.effective_message.reply_text("ɴᴏ ᴅᴀᴛᴀ ꜰᴏᴜɴᴅ")
            return

        total_pages = ((total - 1) // limit) + 1
        text = f"📖 <b>{title}</b> (ᴘᴀɢᴇ: {page}/{total_pages})\n\n"

        for i, item in enumerate(data, start=skip + 1):
            try:
                if choice == "users":
                    uid = item.get('id') or item.get('user_id') or "N/A"
                    uname = html.escape(str(item.get('username') or "No Username"))
                    name = html.escape(str(item.get('name') or "Unknown")).replace("@", "")
                    text += f"{i}. {name} | <code>{uid}</code> | <code>@{uname}</code>\n"
                else:
                    gid = item.get('id') or item.get('chat_id')
                    gname = html.escape(str(item.get('title') or "Unknown Group"))
                    text += f"{i}. <b>{gname}</b>\nID: <code>{gid}</code>\n\n"
            except Exception:
                continue

        buttons = []
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("ᴘʀᴇᴠ", callback_data=f"plist_{choice}_{page - 1}"))
        if (page * limit) < total:
            nav_row.append(InlineKeyboardButton("ɴᴇxᴛ", callback_data=f"plist_{choice}_{page + 1}"))
        if nav_row:
            buttons.append(nav_row)

        markup = InlineKeyboardMarkup(buttons)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"List Error: {e}")


async def list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID:
        return
    _, choice, page = query.data.split("_")
    await show_page(update, context, choice, int(page))


# ============================ USER INFO ============================

async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.error import BadRequest
    from bot.config import users_col
    msg = update.effective_message
    if not msg:
        return

    chat = update.effective_chat
    user_id = None
    label = "👤 Uꜱᴇʀ ID"

    if msg.reply_to_message:
        target_user = msg.reply_to_message.from_user
        if target_user:
            user_id = target_user.id
            label = "👤 Rᴇᴘʟɪᴇᴅ Uꜱᴇʀ ID"
    elif context.args:
        query = context.args[0].strip().replace("@", "")
        user_data = await users_col.find_one({"$or": [
            {"username": {"$regex": f"^{query}$", "$options": "i"}},
            {"name": {"$regex": f"^{query}$", "$options": "i"}}
        ]})
        if user_data:
            user_id = user_data.get("id") or user_data.get("user_id")
            label = f"👤 @{query}'ꜱ Uꜱᴇʀ ID"
        if not user_id:
            try:
                target_chat = await context.bot.get_chat(f"@{query}")
                user_id = target_chat.id
                label = f"👤 @{query}'ꜱ Uꜱᴇʀ ID"
            except (BadRequest, Exception):
                return await msg.reply_text("⚠️ <b>Uꜱᴇʀ Nᴏᴛ Fᴏᴜɴᴅ.</b>\nI ᴄᴏᴜʟᴅ ɴᴏᴛ ғɪɴᴅ ᴛʜᴀᴛ ᴜꜱᴇʀɴᴀᴍᴇ.", parse_mode=ParseMode.HTML)
    else:
        user_id = update.effective_user.id
        label = "👤 Uꜱᴇʀ ID"

    text = f"<b>{label}</b>: <code>{user_id}</code>\n<b>👥 Gʀᴏᴜᴘ ID</b>: <code>{chat.id}</code>"
    await msg.reply_text(text, parse_mode=ParseMode.HTML)


async def inform_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    target_user = None
    if msg.reply_to_message:
        target_user = msg.reply_to_message.from_user
    elif context.args:
        try:
            user_id = int(context.args[0])
            target_user = await context.bot.get_chat(user_id)
        except Exception:
            await msg.reply_text("<code>❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ</code>", parse_mode='HTML')
            return
    else:
        target_user = update.effective_user

    data = get_user(target_user)
    chat_info = await context.bot.get_chat(target_user.id)
    is_prem = "ʏᴇs" if getattr(target_user, 'is_premium', False) else "ɴᴏ"

    photos = await context.bot.get_user_profile_photos(target_user.id, limit=1)
    pfp = photos.photos[0][-1].file_id if photos.total_count > 0 else None

    old_names = data.get("old_names", [])
    names_list = "\n".join([f"  ├ <code>{n}</code>" for n in old_names]) if old_names else "  └ <code>ɴᴏɴᴇ</code>"

    caption = (
        f"🧩 ɴᴀᴍᴇ: <code>{target_user.first_name}</code>\n"
        f"🧩 ᴜꜱᴇʀ ɪᴅ: <code>{target_user.id}</code>\n"
        f"🧩 ᴜꜱᴇʀɴᴀᴍᴇ: <code>@{target_user.username or 'ɴᴏɴᴇ'}</code>\n"
        f"🧩 ᴛᴇʟᴇɢʀᴀᴍ ᴘʀᴇᴍɪᴜᴍ: <code>{is_prem}</code>\n"
        f"🧩 ʙɪᴏ: <code>{getattr(chat_info, 'bio', 'ɴᴏɴᴇ')}</code>\n"
        f"🧩 ᴅᴄ ɪᴅ: <code>{getattr(target_user, 'dc_id', 'ᴜɴᴋɴᴏᴡɴ')}</code>\n\n"
        f"📜 ᴏʟᴅ ɴᴀᴍᴇ ʟɪꜱᴛ 🧩:\n{names_list}"
    )

    if pfp:
        await msg.reply_photo(photo=pfp, caption=caption, parse_mode='HTML')
    else:
        await msg.reply_text(caption, parse_mode='HTML')


# ============================ BROADCAST SYSTEM ============================

def is_owner(user_id):
    return user_id == OWNER_ID


def gen_batch_id() -> str:
    digits = ''.join(random.choices(string.digits, k=8))
    return f"BC_{digits}"


broadcast_control = {"running": False, "cancel": False}


async def send_gro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ Oᴡɴᴇʀ Oɴʟʏ.")
    all_groups = list(db["chats"].find({"type": {"$in": ["group", "supergroup"]}}))
    await _perform_broadcast(update, context, all_groups, bc_type="group")


async def send_pri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ Oᴡɴᴇʀ Oɴʟʏ.")
    all_privates = list(db["chats"].find({"type": "private"}))
    await _perform_broadcast(update, context, all_privates, bc_type="private")


async def _perform_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, target_chats: list, bc_type: str):
    msg = update.message

    if broadcast_control["running"]:
        return await msg.reply_text("⚠️ Aɴᴏᴛʜᴇʀ ʙʀᴏᴀᴅᴄᴀsᴛ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ʀᴜɴɴɪɴɢ!")
    if not msg.reply_to_message:
        return await msg.reply_text(
            "❌ Rᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ.\n\n"
            "📌 <b>Usage:</b> /send_gro [copy|forward] [save|none]\n"
            "📌 <b>Usage:</b> /send_pri [copy|forward] [save|none]",
            parse_mode=ParseMode.HTML
        )

    args = context.args or []
    mode = "forward"
    do_save = False
    for arg in args:
        a = arg.lower().strip()
        if a in ("copy", "forward"):
            mode = a
        elif a == "save":
            do_save = True

    total = len(target_chats)
    from_chat_id = update.effective_chat.id
    target_msg = msg.reply_to_message.message_id
    label = "Gʀᴏᴜᴘ" if bc_type == "group" else "Pʀɪᴠᴀᴛᴇ"
    save_note = "\n💾 <b>Sᴀᴠɪɴɢ ᴅᴀᴛᴀ...</b>" if do_save else ""

    if total == 0:
        return await msg.reply_text("❌ Nᴏ ᴄʜᴀᴛs ꜰᴏᴜɴᴅ.")

    broadcast_control["running"] = True
    broadcast_control["cancel"] = False

    progress_msg = await msg.reply_text(f"📢 <b>Bʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴏɴ {total} {label}s</b> [{mode}]{save_note}", parse_mode=ParseMode.HTML)

    success = 0
    failed = 0
    saved_records = []
    start_time = time.time()

    for i, chat in enumerate(target_chats, start=1):
        if broadcast_control["cancel"]:
            break
        try:
            if mode == "forward":
                sent = await context.bot.forward_message(chat_id=chat["id"], from_chat_id=from_chat_id, message_id=target_msg)
            else:
                sent = await context.bot.copy_message(chat_id=chat["id"], from_chat_id=from_chat_id, message_id=target_msg)

            if do_save:
                saved_records.append({"c": chat["id"], "m": sent.message_id})

            if bc_type == "group":
                try:
                    await context.bot.pin_chat_message(chat_id=chat["id"], message_id=sent.message_id)
                except Exception:
                    pass
            success += 1
        except Exception:
            failed += 1

        if i % 10 == 0 or i == total:
            percent = int((i / total) * 100)
            bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
            try:
                await progress_msg.edit_text(
                    f"📊 <b>{label} Bʀᴏᴀᴅᴄᴀsᴛɪɴɢ...</b>\n\n<code>[{bar}]</code> {percent}%\n"
                    f"✅ Sᴜᴄᴄᴇss: <b>{success}</b>\n❌ Fᴀɪʟᴇᴅ: <b>{failed}</b>\n📦 Tᴏᴛᴀʟ: <b>{total}</b>",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

        await asyncio.sleep(0.08)

    broadcast_control["running"] = False

    batch_id = None
    batch_line = ""
    if do_save and saved_records:
        batch_id = gen_batch_id()
        db["broadcasts"].insert_one({"batch_id": batch_id, "type": bc_type, "messages": saved_records, "created_at": time.time()})
        batch_line = f"\n📦 <b>Bᴀᴛᴄʜ Sᴀᴠᴇᴅ:</b> <code>{batch_id}</code>"

    status = "🛑 Sᴛᴏᴘᴘᴇᴅ" if broadcast_control["cancel"] else "✅ Dᴏɴᴇ"
    elapsed = round(time.time() - start_time, 2)

    await progress_msg.edit_text(
        f"📢 <b>{label} Bʀᴏᴀᴅᴄᴀsᴛ {status}</b>\n\n✅ <b>Sᴇɴᴛ ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ {success} {label}s</b>\n"
        f"❌ Fᴀɪʟᴇᴅ: <b>{failed}</b>\n⏱ Tɪᴍᴇ: <b>{elapsed}s</b>{batch_line}",
        parse_mode=ParseMode.HTML
    )


async def stop_broad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    broadcast_control["cancel"] = True
    await update.message.reply_text("🛑 Sᴛᴏᴘ ʀᴇǫᴜᴇsᴛ sᴇɴᴛ.")


async def del_broad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    msg = update.message
    args = context.args or []

    if not args:
        return await msg.reply_text(
            "📌 <b>Usage:</b>\n/del_broad group — Lɪsᴛ ɢʀᴏᴜᴘ ʙᴀᴛᴄʜᴇs\n/del_broad private — Lɪsᴛ ᴘʀɪᴠᴀᴛᴇ ʙᴀᴛᴄʜᴇs\n"
            "/del_broad group 1 — Dᴇʟᴇᴛᴇ ɢʀᴏᴜᴘ ʙᴀᴛᴄʜ #1",
            parse_mode=ParseMode.HTML
        )

    bc_type = args[0].lower()
    if bc_type not in ("group", "private"):
        return await msg.reply_text("❌ Tʏᴘᴇ ᴍᴜsᴛ ʙᴇ <b>group</b> ᴏʀ <b>private</b>.", parse_mode=ParseMode.HTML)

    if len(args) == 1:
        batches = list(db["broadcasts"].find({"type": bc_type}).sort("created_at", 1))
        if not batches:
            return await msg.reply_text(f"📭 Nᴏ sᴀᴠᴇᴅ {bc_type} ʙᴀᴛᴄʜᴇs.")

        lines = f"📦 <b>Sᴀᴠᴇᴅ {bc_type.capitalize()} Bᴀᴛᴄʜᴇs:</b>\n\n"
        for i, batch in enumerate(batches, start=1):
            count = len(batch.get("messages", []))
            batch_id = batch["batch_id"]
            ts = batch.get("created_at", 0)
            date_str = datetime.utcfromtimestamp(ts).strftime("%d %b %Y")
            lines += f"{i}. <code>{batch_id}</code> — {count} ᴍsɢs — {date_str}\n"
        lines += f"\n💡 /del_broad {bc_type} [number] ᴛᴏ ᴅᴇʟᴇᴛᴇ"
        return await msg.reply_text(lines, parse_mode=ParseMode.HTML)

    try:
        index = int(args[1]) - 1
    except ValueError:
        return await msg.reply_text("❌ Pʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ.")

    batches = list(db["broadcasts"].find({"type": bc_type}).sort("created_at", 1))
    if index < 0 or index >= len(batches):
        return await msg.reply_text(f"❌ Bᴀᴛᴄʜ #{index + 1} ɴᴏᴛ ꜰᴏᴜɴᴅ.")

    target_batch = batches[index]
    batch_id = target_batch["batch_id"]
    records = target_batch.get("messages", [])

    status_msg = await msg.reply_text(f"🗑️ <b>Dᴇʟᴇᴛɪɴɢ</b> <code>{batch_id}</code>...", parse_mode=ParseMode.HTML)

    deleted = 0
    for item in records:
        try:
            await context.bot.delete_message(chat_id=item["c"], message_id=item["m"])
            deleted += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)

    db["broadcasts"].delete_one({"batch_id": batch_id})
    await status_msg.edit_text(f"✅ <b>Dᴇʟᴇᴛᴇᴅ <code>{batch_id}</code></b>\n\n🗑️ Mᴇssᴀɢᴇs Rᴇᴍᴏᴠᴇᴅ: <b>{deleted}</b>", parse_mode=ParseMode.HTML)
