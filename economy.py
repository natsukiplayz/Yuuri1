#!/usr/bin/env python3
"""Economy system: balance/profile, give, rob, kill, revive, protect,
bounty, daily reward, leaderboards, shop/redeem, group claim."""

import html
import random
import asyncio
from datetime import datetime, timezone, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.config import OWNER_ID, users, redeem_col, users_col
from bot.helpers import (
    get_user, save_user, is_premium, get_user_icon, is_economy_disabled,
    get_rank_data, create_progress_bar, font_text, get_leaderboard_icon,
)
from bot.captcha import spam_guard, _is_premium, _token, _captcha_url, pending_captcha, CAPTCHA_TIMEOUT

# ============================ PROFILE ============================

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")

    target_user = msg.reply_to_message.from_user if msg.reply_to_message else user
    data = get_user(target_user)
    icon = get_user_icon(data, context)

    updated = False
    while True:
        need = int(100 * (1.5 ** (max(1, data.get("level", 1)) - 1)))
        if data.get("xp", 0) >= need and data.get("level", 1) < 100:
            data["xp"] -= need
            data["level"] = data.get("level", 1) + 1
            updated = True
        else:
            break
    if updated:
        save_user(data)

    xp, lvl = data.get("xp", 0), data.get("level", 1)
    coins, kills = data.get("coins", 0), data.get("kills", 0)
    inventory = data.get("inventory", [])
    inv_text = ", ".join(inventory) if inventory else "Nᴏɴᴇ"

    current_rank_data, _ = get_rank_data(lvl)
    need = int(100 * (1.5 ** (lvl - 1)))
    percent = int((xp / need) * 100) if need > 0 else 0
    bar = create_progress_bar(min(max(0, percent), 100))

    bot_id = context.bot.id
    xp_rank = 1 + users.count_documents({"id": {"$ne": bot_id}, "$or": [{"level": {"$gt": lvl}}, {"level": lvl, "xp": {"$gt": xp}}]})
    wealth_rank = 1 + users.count_documents({"id": {"$ne": bot_id}, "coins": {"$gt": coins}})
    kill_rank = 1 + users.count_documents({"id": {"$ne": bot_id}, "kills": {"$gt": kills}})

    status = "💀 Dᴇᴀᴅ" if data.get("dead") else "❤️ Aʟɪᴠᴇ"
    guild = data.get("guild", "Nᴏɴᴇ")
    safe_name = html.escape(data.get('name', target_user.first_name))

    text = (
        f"{icon} <b>Nᴀᴍᴇ:</b> {safe_name}\n"
        f"🛡️ <b>Tɪᴛʟᴇ:</b> {current_rank_data['name']}\n"
        f"🏅 <b>Lᴇᴠᴇʟ:</b> {lvl}\n"
        f"⚔️ <b>Kɪʟʟs:</b> {kills:,}\n"
        f"💰 <b>Cᴏɪɴꜱ:</b> {coins:,}\n"
        f"🎒 <b>Iɴᴠᴇɴᴛᴏʀʏ:</b> {inv_text}\n"
        f"🎯 <b>Sᴛᴀᴛᴜꜱ:</b> {status}\n\n"
        f"📊 <b>Pʀᴏɢʀᴇꜱꜱ:</b> {xp:,} / {need:,} XP\n"
        f"{bar} ({percent}%)\n\n"
        f"🌐 <b>Gʟᴏʙᴀʟ Rᴀɴᴋ (XP):</b> {xp_rank}\n"
        f"💸 <b>Wᴇᴀʟᴛʜ Rᴀɴᴋ:</b> {wealth_rank}\n"
        f"🩸 <b>Kɪʟʟ Rᴀɴᴋ:</b> {kill_rank}\n"
        f"🏰 <b>Gᴜɪʟᴅ:</b> {guild}"
    )
    await msg.reply_text(text, parse_mode='HTML')


async def bal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")

    target_user = msg.reply_to_message.from_user if msg.reply_to_message else update.effective_user
    data = get_user(target_user)
    icon = get_user_icon(data, context)

    coins = data.get("coins", 0)
    kills = data.get("kills", 0)
    status = "💀 Dᴇᴀᴅ" if data.get("dead") else "❤️ Aʟɪᴠᴇ"

    bot_id = context.bot.id
    wealth_rank = 1 + users.count_documents({"id": {"$ne": bot_id}, "coins": {"$gt": coins}})
    safe_name = html.escape(target_user.first_name)

    text = (
        f"{icon} <b>Nᴀᴍᴇ:</b> {safe_name}\n"
        f"💰 <b>Cᴏɪɴꜱ:</b> {coins:,}\n"
        f"💸 <b>Wᴇᴀʟᴛʜ Rᴀɴᴋ:</b> {wealth_rank}\n"
        f"🎯 <b>Sᴛᴀᴛᴜꜱ:</b> {status}\n"
        f"⚔️ <b>Kɪʟʟs:</b> {kills:,}"
    )
    await msg.reply_text(text, parse_mode='HTML')


# ============================ ROB ============================

@spam_guard("rob")
async def robe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    msg = update.message
    chat = update.effective_chat
    robber_user = update.effective_user

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")
    if chat.type == "private":
        return await msg.reply_text("❌ Tʜɪs Cᴏᴍᴍᴀɴᴅ Cᴀɴ Oɴʟʏ Bᴇ Usᴇᴅ Iɴ Gʀᴏᴜᴘs.")
    if not msg.reply_to_message:
        return await msg.reply_text("⚠️ Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ Yᴏᴜ Wᴀɴᴛ Tᴏ Rᴏʙ.")

    target_user = msg.reply_to_message.from_user
    if target_user.id == context.bot.id or target_user.is_bot:
        return await msg.reply_text("🤖 Yᴏᴜ Cᴀɴɴᴏᴛ Rᴏʙ A Bᴏᴛ.")
    if target_user.id == robber_user.id:
        return await msg.reply_text("❌ Yᴏᴜ Cᴀɴ'ᴛ Rᴏʙ Yᴏᴜʀsᴇʟғ.")
    if target_user.id == OWNER_ID:
        return await msg.reply_text("👑 Yᴏᴜ Cᴀɴ'ᴛ Rᴏʙ Mʏ Dᴇᴀʀᴇsᴛ Oᴡɴᴇʀ 😒")
    if not context.args:
        return await msg.reply_text("⚠️ Uꜱᴀɢᴇ: /rob <amount>")

    try:
        amount = int(context.args[0])
    except ValueError:
        return await msg.reply_text("❌ Iɴᴠᴀʟɪᴅ Aᴍᴏᴜɴᴛ.")
    if amount <= 0:
        return await msg.reply_text("❌ Aᴍᴏᴜɴᴛ Mᴜsᴛ Bᴇ Pᴏsɪᴛɪᴠᴇ.")

    robber = get_user(robber_user)
    target = get_user(target_user)

    if target.get("protect_until"):
        try:
            expire = datetime.strptime(target["protect_until"], "%Y-%m-%d %H:%M:%S")
            if expire > datetime.utcnow():
                return await msg.reply_text(
                    "🛡️ Tʜɪꜱ Uꜱᴇʀ Iꜱ Pʀᴏᴛᴇᴄᴛᴇᴅ.\n"
                    "🔒 Cʜᴇᴄᴋ Pʀᴏᴛᴇᴄᴛɪᴏɴ Tɪᴍᴇ » /check"
                )
        except (ValueError, TypeError):
            pass

    if robber.get("coins", 0) < 50:
        return await msg.reply_text("💰 Yᴏᴜ Nᴇᴇᴅ Aᴛ Lᴇᴀsᴛ 50 Cᴏɪɴs Tᴏ Rᴏʙ Sᴏᴍᴇᴏɴᴇ.")

    premium_active = is_premium(robber, context)
    if premium_active:
        icon = robber.get("custom_icon", "💓")
        max_rob_limit = 100000
    else:
        icon = "👤"
        max_rob_limit = 10000

    if amount > max_rob_limit:
        user_status = "💗 Pʀᴇᴍɪᴜᴍ" if premium_active else "👤 Nᴏʀᴍᴀʟ"
        return await msg.reply_text(
            f"❌ Aꜱ ᴀ {user_status} ᴜꜱᴇʀ, ʏᴏᴜ ᴄᴀɴ ᴏɴʟʏ ʀᴏʙ ᴜᴘ ᴛᴏ {max_rob_limit:,} ᴄᴏɪɴꜱ ᴀᴛ ᴀ ᴛɪᴍᴇ."
        )

    if target.get("coins", 0) < amount:
        return await msg.reply_text(
            f"💸 {target_user.first_name} ᴅᴏᴇꜱɴ'ᴛ ʜᴀᴠᴇ {amount:,} ᴄᴏɪɴꜱ!\n"
            f"Tʜᴇʏ ᴏɴʟʏ ʜᴀᴠᴇ {target.get('coins', 0):,} ᴄᴏɪɴꜱ."
        )

    robber["coins"] += amount
    target["coins"] -= amount
    save_user(robber)
    save_user(target)

    await msg.reply_text(
        f"{icon} <b>{robber_user.first_name} Sᴜᴄᴄᴇssғᴜʟʟʏ Rᴏʙʙᴇᴅ {target_user.first_name}</b>\n"
        f"💰 <b>Sᴛᴏʟᴇɴ:</b> <code>{amount:,}$</code>",
        parse_mode='HTML'
    )


# ============================ GIVE ============================

async def givee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    sender = update.effective_user
    reply = msg.reply_to_message

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")
    if not reply:
        return await msg.reply_text("⚠️ Rᴇᴘʟʏ Tᴏ A Pʟᴀʏᴇʀ Tᴏ Gɪᴠᴇ Cᴏɪɴs")

    target = reply.from_user
    if not target:
        return await msg.reply_text("❌ Pʟᴀʏᴇʀ Nᴏᴛ Fᴏᴜɴᴅ")
    if target.is_bot:
        return await msg.reply_text("🤖 Yᴏᴜ Cᴀɴ'ᴛ Gɪᴠᴇ Cᴏɪɴs Tᴏ Bᴏᴛs")
    if not context.args:
        return await msg.reply_text("⚠️ Usᴀɢᴇ: /give <amount>")

    try:
        amount = int(context.args[0])
    except ValueError:
        return await msg.reply_text("❌ Iɴᴠᴀʟɪᴅ Aᴍᴏᴜɴᴛ")
    if amount <= 0:
        return await msg.reply_text("❌ Aᴍᴏᴜɴᴛ Mᴜsᴛ Bᴇ Pᴏsɪᴛɪᴠᴇ")
    if target.id == sender.id:
        return await msg.reply_text("⚠️ Yᴏᴜ Cᴀɴ'ᴛ Gɪᴠᴇ Cᴏɪɴs Tᴏ Yᴏᴜʀsᴇʟғ")
    if target.id == OWNER_ID:
        return await msg.reply_text("🧸 Nᴏᴛ Nᴇᴇᴅ Tᴏ Gɪᴠᴇ Mʏ Oᴡɴᴇʀ 🧸✨")

    sender_data = get_user(sender)
    if sender_data.get("coins", 0) < amount:
        return await msg.reply_text("💰 Yᴏᴜ Dᴏɴ'ᴛ Hᴀᴠᴇ Eɴᴏᴜɢʜ Cᴏɪɴs")

    premium_active = is_premium(sender_data, context)
    tax_rate = 0.05 if premium_active else 0.10
    tax_percent = "5%" if premium_active else "10%"
    tax = int(amount * tax_rate)
    received = amount - tax
    xp_loss = max(1, min(amount // 30, 50))

    anim = await msg.reply_text("💸 Tʀᴀɴsғᴇʀ Iɴɪᴛɪᴀᴛᴇᴅ...")
    await asyncio.sleep(1.2)
    await anim.edit_text("💰 Cᴀʟᴄᴜʟᴀᴛɪɴɢ Tᴀx...")
    await asyncio.sleep(1.2)

    users.update_one({"id": sender.id}, {"$inc": {"coins": -amount, "xp": -xp_loss}})
    users.update_one({"id": target.id}, {"$inc": {"coins": received}})
    users.update_one({"id": OWNER_ID}, {"$inc": {"coins": tax}})

    premium_tag = "🌟 (Pʀᴇᴍɪᴜᴍ Bᴇɴᴇꜰɪᴛ)" if premium_active else ""

    await anim.edit_text(
        f"""
✅ Tʀᴀɴsᴀᴄᴛɪᴏɴ Cᴏᴍᴘʟᴇᴛᴇᴅ

👤 Sᴇɴᴅᴇʀ: {sender.first_name}
🎁 Rᴇᴄᴇɪᴠᴇʀ: {target.first_name}

✅ {target.first_name} Rᴇᴄᴇɪᴠᴇᴅ ${received:,}
💸 Tᴀx: ${tax:,} ({tax_percent}) {premium_tag}
⚡ Xᴘ Dᴇᴅᴜᴄᴛᴇᴅ: -{xp_loss}
"""
    )


# ============================ KILL ============================

BOT_ID = None


@spam_guard("kill")
async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ID
    if BOT_ID is None:
        BOT_ID = context.bot.id
    if not update.message:
        return

    msg = update.message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")
    if chat.type == "private":
        return await msg.reply_text("❌ Tʜɪs Cᴏᴍᴍᴀɴᴅ Cᴀɴ Oɴʟʏ Bᴇ Usᴇᴅ Iɴ Gʀᴏᴜᴘs.")
    if not msg.reply_to_message:
        return await msg.reply_text("⚠️ Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ Yᴏᴜ Wᴀɴᴛ Tᴏ Kɪʟʟ.")

    target_user = msg.reply_to_message.from_user
    if not target_user:
        return await msg.reply_text("❌ Iɴᴠᴀʟɪᴅ Tᴀʀɢᴇᴛ.")

    if target_user.is_bot:
        if target_user.id == BOT_ID:
            return await msg.reply_text("😂 Nɪᴄᴇ Tʀʏ Oɴ Mᴇ!")
        return await msg.reply_text("🤖 Yᴏᴜ Cᴀɴ'ᴛ Kɪʟʟ Bᴏᴛs, Tʜᴇʏ Hᴀᴠᴇ Nᴏ Sᴏᴜʟ.")
    if target_user.id == OWNER_ID:
        return await msg.reply_text("😒 Yᴏᴜ Cᴀɴ'ᴛ Kɪʟʟ Mʏ Dᴇᴀʀᴇsᴛ Oᴡɴᴇʀ.")
    if target_user.id == user.id:
        return await msg.reply_text("❌ Yᴏᴜ Cᴀɴ'ᴛ Kɪʟʟ Yᴏᴜʀsᴇʟғ.")

    killer = get_user(user)
    victim = get_user(target_user)

    if victim.get("protect_until"):
        try:
            expire = datetime.strptime(victim["protect_until"], "%Y-%m-%d %H:%M:%S")
            if expire > datetime.utcnow():
                return await msg.reply_text("🛡️ Tʜɪꜱ Uꜱᴇʀ Iꜱ Pʀᴏᴛᴇᴄᴛᴇᴅ.\n 🔒 Cʜᴇᴄᴋ Pʀᴏᴛᴇᴄᴛɪᴏɴ Tɪᴍᴇ → /check")
        except (ValueError, TypeError):
            pass

    if victim.get("dead", False):
        return await msg.reply_text(f"💀 {target_user.first_name} ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴅᴇᴀᴅ!")

    premium_active = is_premium(killer, context)
    if premium_active:
        icon = killer.get("custom_icon", "💓")
        reward = random.randint(500, 1500)
        xp_gain = random.randint(35, 57)
        kill_msg = f"{icon} <b>{user.first_name} Aɴɴɪʜɪʟᴀᴛᴇᴅ {target_user.first_name}</b>"
    else:
        icon = "👤"
        reward = random.randint(100, 300)
        xp_gain = random.randint(5, 21)
        kill_msg = f"{icon} <b>{user.first_name} Sᴛᴀʙʙᴇᴅ {target_user.first_name}</b>"

    killer["coins"] = killer.get("coins", 0) + reward
    killer["xp"] = killer.get("xp", 0) + xp_gain
    killer["kills"] = killer.get("kills", 0) + 1

    bounty_reward = victim.get("bounty", 0)
    if bounty_reward > 0:
        killer["coins"] += bounty_reward
        victim["bounty"] = 0

    victim["dead"] = True
    save_user(killer)
    save_user(victim)

    response = (
        f"{kill_msg}\n"
        f"💰 <b>Eᴀʀɴᴇᴅ:</b> <code>{reward:,}$</code>\n"
        f"⭐ <b>Gᴀɪɴᴇᴅ:</b> <code>+{xp_gain} XP</code>"
    )
    if bounty_reward > 0:
        response += f"\n\n🎯 <b>Bᴏᴜɴᴛʏ Cʟᴀɪᴍᴇᴅ!</b>\n💰 <b>Eᴀʀɴᴇᴅ ᴇxᴛʀᴀ:</b> <code>{bounty_reward:,}$</code>"

    await msg.reply_text(response, parse_mode='HTML')


# ============================ BOUNTY ============================

async def bounty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = update.effective_chat

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")
    if not msg.reply_to_message:
        return await msg.reply_text("Rᴇᴘʟʏ Tᴏ Sᴏᴍᴇᴏɴᴇ Tᴏ Pʟᴀᴄᴇ Bᴏᴜɴᴛʏ.")
    if not context.args:
        return await msg.reply_text("Use: /bounty <amount>")

    try:
        amount = int(context.args[0])
    except ValueError:
        return await msg.reply_text("❌ Aᴍᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ.")

    sender = get_user(update.effective_user)
    target_user = msg.reply_to_message.from_user
    target = get_user(target_user)

    if sender.get("coins", 0) < amount:
        return await msg.reply_text("❌ Nᴏᴛ ᴇɴᴏᴜɢʜ Cᴏɪɴs.")
    if target_user.id == update.effective_user.id:
        return await msg.reply_text("❌ Yᴏᴜ ᴄᴀɴ'ᴛ ᴘʟᴀᴄᴇ ʙᴏᴜɴᴛʏ ᴏɴ ʏᴏᴜʀsᴇʟғ.")

    sender["coins"] -= amount
    target["bounty"] = target.get("bounty", 0) + amount
    save_user(sender)
    save_user(target)

    await msg.reply_text(
        f"🎯 Bᴏᴜɴᴛʏ Pʟᴀᴄᴇᴅ!\n\n"
        f"👤 Tᴀʀɢᴇᴛ: {target_user.first_name}\n"
        f"💰 Rᴇᴡᴀʀᴅ: {amount:,} Cᴏɪɴs\n\n"
        f"⚔️ Kɪʟʟ ᴛʜᴇᴍ Tᴏ Cʟᴀɪᴍ!"
    )


# ============================ REVIVE ============================

async def revive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    reply = msg.reply_to_message

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")

    target = reply.from_user if reply else user
    data = get_user(target)
    if not data:
        return await msg.reply_text("❌ Pʟᴀʏᴇʀ Nᴏᴛ Fᴏᴜɴᴅ")
    if not data.get("dead", False):
        return await msg.reply_text("⚠️ Tʜɪs Pʟᴀʏᴇʀ ɪs Aʟʀᴇᴀᴅʏ Aʟɪᴠᴇ")

    if target.id == user.id:
        coins = data.get("coins", 0)
        if coins < 400:
            return await msg.reply_text("💰 Yᴏᴜ Nᴇᴇᴅ 400 Cᴏɪɴs Tᴏ Rᴇᴠɪᴠᴇ Yᴏᴜʀsᴇʟғ")
        data["coins"] -= 400

    data["dead"] = False
    save_user(data)

    await msg.reply_text(
        f"""
✨ Rᴇᴠɪᴠᴇ Sᴜᴄᴄᴇssғᴜʟ

👤 Nᴀᴍᴇ : {target.first_name}
🆔 Iᴅ : {target.id}
❤️ Sᴛᴀᴛᴜs : Aʟɪᴠᴇ

⚔️ Rᴇᴀᴅʏ Aɢᴀɪɴ
"""
    )


# ============================ PROTECT ============================

async def protect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = update.effective_chat
    user_data = update.effective_user

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")

    if not context.args:
        return await msg.reply_text(
            "🛡️ <b>Pʀᴏᴛᴇᴄᴛɪᴏɴ Sʏsᴛᴇᴍ</b>\n\n"
            "💰 <b>Cᴏsᴛs:</b>\n"
            "1ᴅ → 200$ (Aʟʟ Uꜱᴇʀꜱ 👤)\n"
            "2ᴅ → 400$ (Pʀᴇᴍɪᴜᴍ Oɴʟʏ 💓)\n"
            "3ᴅ → 600$ (Pʀᴇᴍɪᴜᴍ Oɴʟʏ 💓)\n\n"
            "Uꜱᴀɢᴇ: <code>/protect 1d|2d|3d</code>",
            parse_mode=ParseMode.HTML
        )

    arg = context.args[0].lower()
    durations = {"1d": (1, 200), "2d": (2, 400), "3d": (3, 600)}
    if arg not in durations:
        return await msg.reply_text("🛡️ <b>Iɴᴠᴀʟɪᴅ Pʀᴏᴛᴇᴄᴛɪᴏɴ Tɪᴍᴇ.</b>", parse_mode=ParseMode.HTML)

    days_to_add, price = durations[arg]
    user = get_user(user_data)
    premium_active = is_premium(user, context)

    if days_to_add > 1 and not premium_active:
        return await msg.reply_text("❌ <b>Pʀᴇᴍɪᴜᴍ Fᴇᴀᴛᴜʀᴇ Oɴʟʏ!</b>", parse_mode=ParseMode.HTML)
    if user.get("coins", 0) < price:
        return await msg.reply_text("💰 <b>Nᴏᴛ Eɴᴏᴜɢʜ Cᴏɪɴs.</b>", parse_mode=ParseMode.HTML)

    now = datetime.utcnow()
    protect_until = user.get("protect_until")
    if protect_until:
        try:
            expire = datetime.strptime(protect_until, "%Y-%m-%d %H:%M:%S")
            if expire > now:
                diff = expire - now
                days = diff.days
                hours, remainder = divmod(diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                t_str = f"{days:02d}ᴅ {hours:02d}ʜ {minutes:02d}ᴍ {seconds:02d}ꜱ"
                return await msg.reply_text(
                    f"🛡️ <b>Yᴏᴜʀ Aʟʀᴇᴀᴅʏ Pʀᴏᴛᴇᴄᴛᴇᴅ</b>\n"
                    f"⌛ <b>Rᴇᴍᴀɪɴɪɴɢ Tɪᴍᴇ:</b> <code>{t_str}</code>",
                    parse_mode=ParseMode.HTML
                )
        except (ValueError, TypeError):
            pass

    user["coins"] -= price
    user["protect_until"] = (now + timedelta(days=days_to_add)).strftime("%Y-%m-%d %H:%M:%S")
    save_user(user)

    icon = "🌟" if premium_active else "🛡️"
    await msg.reply_text(
        f"{icon} <b>Yᴏᴜ Aʀᴇ Nᴏᴡ Pʀᴏᴛᴇᴄᴛᴇᴅ Fᴏʀ {arg.upper()}.</b>",
        parse_mode=ParseMode.HTML
    )


async def check_protection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await msg.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏꜱᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏꜱᴇᴅ Iɴ Tʜɪꜱ Gʀᴏᴜᴘ.")

    checker_data = get_user(user)
    if not is_premium(checker_data, context):
        return await msg.reply_text("❌ <b>Pʀᴇᴍɪᴜᴍ Oɴʟʏ Cᴏᴍᴍᴀɴᴅ!</b>", parse_mode=ParseMode.HTML)
    if not msg.reply_to_message:
        return await msg.reply_text("❌ <b>Pʟᴇᴀꜱᴇ Rᴇᴘʟʏ Tᴏ A Uꜱᴇʀ.</b>", parse_mode=ParseMode.HTML)

    target_user = msg.reply_to_message.from_user
    target_data = get_user(target_user)

    protect_until = target_data.get("protect_until")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    status_text = "🚫 <b>Nᴏ Pʀᴏᴛᴇᴄᴛɪᴏɴ Aᴄᴛɪᴠᴇ</b>"

    if protect_until:
        try:
            expire = datetime.strptime(protect_until, "%Y-%m-%d %H:%M:%S")
            if expire > now:
                remaining = expire - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                status_text = f"🛡️ <b>Sᴛᴀᴛᴜꜱ:</b> Pʀᴏᴛᴇᴄᴛᴇᴅ\n⏳ <b>Tɪᴍᴇ Lᴇғᴛ:</b> <code>{hours}ʜ {minutes}ᴍ</code>"
        except Exception:
            pass

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"🔍 <b>Pʀᴏᴛᴇᴄᴛɪᴏɴ Cʜᴇᴄᴋ</b>\n\n👤 <b>Uꜱᴇʀ:</b> {target_user.first_name}\n\n{status_text}",
            parse_mode=ParseMode.HTML
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Oᴘᴇɴ DM 💸", url=f"t.me/{context.bot.username}")]])
        await msg.reply_text("✅ <b>Pʀᴏᴛᴇᴄᴛɪᴏɴ Tɪᴍᴇ Sᴇɴᴛ Tᴏ DM</b>", parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception:
        await msg.reply_text("❌ <b>Cᴏᴜʟᴅ Nᴏᴛ Sᴇɴᴅ DM!</b> Sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ ɪɴ ᴘʀɪᴠᴀᴛᴇ.", parse_mode=ParseMode.HTML)


# ============================ REGISTER ============================

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return await update.message.reply_text("❌ Tʜɪs Cᴏᴍᴍᴀɴᴅ Cᴀɴ Oɴʟʏ Bᴇ Usᴇᴅ Iɴ Dᴍ.")

    user = update.effective_user
    user_data = users.find_one({"id": user.id})

    if not user_data:
        user_data = {"id": user.id, "name": user.first_name, "coins": 0, "xp": 0,
                     "level": 1, "inventory": [], "registered": False}
        users.insert_one(user_data)

    if user_data.get("registered", False):
        return await update.message.reply_text("⚠️ Yᴏᴜ Aʟʀᴇᴀᴅʏ Rᴇɢɪsᴛᴇʀᴇᴅ.")

    users.update_one({"id": user.id}, {"$set": {"registered": True}, "$inc": {"coins": 1000}})
    await update.message.reply_text(
        "🎉 Rᴇɢɪsᴛʀᴀᴛɪᴏɴ Sᴜᴄᴄᴇssғᴜʟ!\n💰 Rᴇᴄᴇɪᴠᴇᴅ: $1000\n✨ Wᴇʟᴄᴏᴍᴇ Tᴏ Yᴜᴜʀɪ!"
    )


# ============================ DAILY ============================

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    msg = update.message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type != "private":
        if await is_economy_disabled(chat.id):
            return await msg.reply_text("🛑 ᴛʜᴇ ᴇᴄᴏɴᴏᴍʏ sʏsᴛᴇᴍ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴄʟᴏsᴇᴅ ɪɴ ᴛʜɪs ɢʀᴏᴜᴘ.")

        u = get_user(user)
        if _is_premium(u, context):
            deep = f"https://t.me/{context.bot.username}?start=daily"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💗 ᴄʟᴀɪᴍ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ", url=deep)]])
            return await msg.reply_text(
                f"💗 <b>{user.first_name}</b>, ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ ɪs ʀᴇᴀᴅʏ!\n"
                "ᴛᴀᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴄʟᴀɪᴍ ɪɴ DM — ɴᴏ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ɴᴇᴇᴅᴇᴅ.",
                parse_mode=ParseMode.HTML, reply_markup=kb
            )

        tok = _token()
        pending_captcha[user.id] = {
            "token": tok, "expires": asyncio.get_event_loop().time() + CAPTCHA_TIMEOUT,
            "pending_cmd": "daily", "pending_chat": chat.id,
        }
        url = _captcha_url(tok)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔒 ᴠᴇʀɪꜰʏ & ᴄʟᴀɪᴍ ᴅᴀɪʟʏ", url=url)]])
        return await msg.reply_text(
            f"🎁 <b>{user.first_name}</b>, ᴛᴀᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴠᴇʀɪꜰʏ ᴀɴᴅ ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ.\n"
            "<i>ʟɪɴᴋ ᴇxᴘɪʀᴇs ɪɴ 5 ᴍɪɴᴜᴛᴇs.</i>",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )

    u = get_user(user)
    today = datetime.now().date()

    if "last_daily" in u:
        last_claim = datetime.strptime(u["last_daily"], "%Y-%m-%d").date()
        if last_claim == today:
            return await msg.reply_text(
                "⛔ ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ ʏᴏᴜʀ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ ᴛᴏᴅᴀʏ.\nᴄᴏᴍᴇ ʙᴀᴄᴋ ᴛᴏᴍᴏʀʀᴏᴡ! 💗"
            )

    premium_active = _is_premium(u, context)
    if premium_active:
        reward = 2000
        label = "🌟 ᴘʀᴇᴍɪᴜᴍ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ"
        extra_note = "\n<i>+2000 ᴄᴏɪɴs — ᴘʀᴇᴍɪᴜᴍ ʙᴏɴᴜs ᴀᴘᴘʟɪᴇᴅ 💗</i>"
    else:
        reward = random.randint(50, 120)
        label = "🎁 ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ"
        extra_note = ""

    u["coins"] += reward
    u["last_daily"] = today.strftime("%Y-%m-%d")
    save_user(u)

    await msg.reply_text(f"{label}\n\n💰 <b>+{reward:,} ᴄᴏɪɴs</b> ʜᴀᴠᴇ ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ!{extra_note}", parse_mode=ParseMode.HTML)


# ============================ LEADERBOARDS ============================

async def richest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await update.message.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")

    top_list = users.find({"id": {"$ne": context.bot.id}}).sort("coins", -1).limit(10)
    text = "🏆 <b>Tᴏᴘ 10 Rɪᴄʜᴇꜱᴛ Uꜱᴇʀꜱ:</b>\n\n"
    for i, u in enumerate(top_list, start=1):
        user_id = u.get("id")
        safe_name = html.escape(str(u.get("name", "Uɴᴋɴᴏᴡɴ")))
        icon = get_leaderboard_icon(u, context)
        clickable_name = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
        text += f"{icon} {i}. {clickable_name}: <code>{u.get('coins', 0):,}$</code>\n"
    text += "\n✨ = Cᴜsᴛᴏᴍ • 💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ\n\n<i>✅ Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ : /pay</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def rankers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await update.message.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")

    top_list = users.find({"id": {"$ne": context.bot.id}}).sort([("level", -1), ("xp", -1)]).limit(10)
    text = "🎖️ <b>Tᴏᴘ 10 Gʟᴏʙᴀʟ Rᴀɴᴋᴇʀꜱ:</b>\n\n"
    for i, u in enumerate(top_list, start=1):
        user_id = u.get("id")
        safe_name = html.escape(str(u.get("name", "Uɴᴋɴᴏᴡɴ")))
        icon = get_leaderboard_icon(u, context)
        clickable_name = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
        text += f"{icon} {i}. {clickable_name}: Lᴠʟ {u.get('level', 1)} ({u.get('xp', 0):,} XP)\n"
    text += "\n✨ = Cᴜsᴛᴏᴍ • 💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ\n\n<i>✅ Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ : /pay</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def top_killers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type != "private" and await is_economy_disabled(chat.id):
        return await update.message.reply_text("🛑 Tʜᴇ Eᴄᴏɴᴏᴍʏ Sʏsᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Cʟᴏsᴇᴅ Iɴ Tʜɪs Gʀᴏᴜᴘ.")

    query = {"kills": {"$gt": 0}, "id": {"$ne": context.bot.id}}
    top_list = list(users.find(query).sort("kills", -1).limit(10))
    if not top_list:
        return await update.message.reply_text("<b>🚫 Nᴏ Kɪʟʟᴇʀs Fᴏᴜɴᴅ Yᴇᴛ!</b>", parse_mode=ParseMode.HTML)

    text = "🏆 <b>Tᴏᴘ 10 Dᴇᴀᴅʟɪᴇsᴛ Kɪʟʟᴇʀs:</b>\n\n"
    for i, u in enumerate(top_list, start=1):
        user_id = u.get("id")
        safe_name = html.escape(str(u.get("name", "Uɴᴋɴᴏᴡɴ")))
        icon = get_leaderboard_icon(u, context)
        clickable_name = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
        text += f"{icon} {i}. {clickable_name}: <code>{u.get('kills', 0):,} Kɪʟʟs</code>\n"
    text += "\n✨ = Cᴜsᴛᴏᴍ • 💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ\n\n<i>✅ Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ : /pay</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ============================ SHOP / REDEEM ============================

SHOP_ITEMS = {
    "rose": (500, "🌹"), "chocolate": (800, "🍫"), "ring": (2000, "💍"),
    "teddy": (1500, "🧸"), "pizza": (600, "🍕"), "box": (2500, "🎁"),
    "puppy": (3000, "🐶"), "cake": (1000, "🍰"), "letter": (400, "💌"),
    "cat": (2500, "🐱"), "hepikute": (1500, "💖"),
}


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🎁 Aᴠᴀɪʟᴀʙʟᴇ Gɪꜰᴛs:\n\n"
    for k, (v, emoji) in SHOP_ITEMS.items():
        msg += f"{emoji} {font_text(k.capitalize())} — {font_text(str(v))} ᴄᴏɪɴs\n"
    await update.message.reply_text(msg)


async def purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Uꜱᴀɢᴇ: /purchase item")
    item = context.args[0].lower()
    if item not in SHOP_ITEMS:
        return await update.message.reply_text("Iᴛᴇᴍ ɴᴏᴛ ꜰᴏᴜɴᴅ")

    u = get_user(update.effective_user)
    price, emoji = SHOP_ITEMS[item]
    if u["coins"] < price:
        return await update.message.reply_text("ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴄᴏɪɴs")

    u["coins"] -= price
    u["inventory"].append(item)
    save_user(u)
    await update.message.reply_text(f"✅ {emoji} Yᴏᴜ ʙᴏᴜɢʜᴛ {font_text(item.capitalize())}")


async def create_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/create <code> <limit> <type:value> - Owner Only"""
    if update.effective_user.id != OWNER_ID:
        return
    if len(context.args) < 3:
        usage = (
            "📑 𝗖𝗿𝗲𝗮𝘁𝗲 𝗥𝗲𝗱𝗲𝗲𝗺 𝗖𝗼𝗱𝗲\n\n"
            "Usage: `/create <code> <limit> <type:value>`\n"
            "Types: `coins` or `item`\n\n"
            "Examples:\n"
            "• `/create GIFT10 5 coins:5000`\n"
            "• `/create TEDDY 1 item:Teddy 🧸`"
        )
        return await update.message.reply_text(usage, parse_mode="Markdown")

    code = context.args[0].upper()
    try:
        limit = int(context.args[1])
    except ValueError:
        return await update.message.reply_text("❌ Lɪᴍɪᴛ ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ!")

    reward_raw = context.args[2]
    if ":" not in reward_raw:
        return await update.message.reply_text("❌ Fᴏʀᴍᴀᴛ ᴍᴜsᴛ ʙᴇ `type:value` (e.g., `coins:100`)!")

    redeem_col.update_one(
        {"code": code},
        {"$set": {"code": code, "limit": limit, "used_by": [], "reward": reward_raw, "created_at": datetime.now()}},
        upsert=True
    )
    await update.message.reply_text(
        f"✅ 𝗥𝗲𝗱𝗲𝗲𝗺 𝗖𝗼𝗱𝗲 𝗖𝗿𝗲𝗮𝘁𝗲𝗱\n\n🎫 Cᴏᴅᴇ : `{code}`\n👥 Lɪᴍɪᴛ : `{limit}`\n🎁 Rᴇᴡᴀʀᴅ : `{reward_raw}`",
        parse_mode="Markdown"
    )


async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/redeem <code> - For Users"""
    user = update.effective_user
    msg = update.effective_message

    if not context.args:
        usage = (
            "🎫 <b>𝗥𝗲𝗱𝗲𝗲𝗺 𝗖𝗼𝗱𝗲</b>\n\n"
            "Uꜱᴀɢᴇ: <code>/redeem &lt;code&gt;</code>\n\n"
            "Exᴀᴍᴘʟᴇ: <code>/redeem GIFT10</code>"
        )
        return await msg.reply_text(usage, parse_mode="HTML")

    code_input = context.args[0].upper()
    result = redeem_col.find_one_and_update(
        {"code": code_input, "used_by": {"$ne": user.id},
         "$expr": {"$lt": [{"$size": "$used_by"}, "$limit"]}},
        {"$push": {"used_by": user.id}},
        return_document=False
    )

    if not result:
        data = redeem_col.find_one({"code": code_input})
        if not data:
            return await msg.reply_text("❌ Tʜᴀᴛ ᴄᴏᴅᴇ ɪs ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ!")
        if user.id in data.get("used_by", []):
            return await msg.reply_text("⚠️ Yᴏᴜ ʜᴀᴠᴇ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ ᴛʜɪs ᴄᴏᴅᴇ!")
        return await msg.reply_text("😔 Sᴏʀʀʏ! Tʜɪs ᴄᴏᴅᴇ ʜᴀs ʀᴇᴀᴄʜᴇᴅ ɪᴛs ᴜsᴀɢᴇ ʟɪᴍɪᴛ.")

    reward_raw = result.get("reward", "")
    reward_type, reward_val = reward_raw.split(":", 1)
    display_reward = ""

    try:
        if reward_type == "coins":
            val = int(reward_val)
            await users_col.update_one({"id": user.id}, {"$inc": {"coins": val}}, upsert=True)
            display_reward = f"💰 <code>{val:,} Cᴏɪɴs</code>"
        elif reward_type == "xp":
            val = int(reward_val)
            await users_col.update_one({"id": user.id}, {"$inc": {"xp": val}}, upsert=True)
            display_reward = f"✨ <code>{val:,} XP</code>"
        elif reward_type == "item":
            await users_col.update_one({"id": user.id}, {"$push": {"inventory": reward_val}}, upsert=True)
            display_reward = f"🎁 <code>{reward_val}</code>"
    except (ValueError, IndexError):
        return await msg.reply_text("❌ Eʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ʀᴇᴡᴀʀᴅ ᴠᴀʟᴜᴇ.")

    await msg.reply_text(
        f"✅ <b>𝗥𝗲𝗱𝗲𝗲𝗺 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹</b>\n\n👤 Uꜱᴇʀ : <b>{user.first_name}</b>\n🎁 Rᴇᴡᴀʀᴅ : {display_reward}\n\n"
        "Cʜᴇᴄᴋ ʏᴏᴜʀ /status ᴛᴏ sᴇᴇ ʏᴏᴜʀ ɢʀᴏᴡᴛʜ! 🚀",
        parse_mode="HTML"
    )


# ============================ CLAIM (group reward) ============================

async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.config import db as _db  # local import to avoid cycle
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if chat.type == "private":
        return await msg.reply_text("⚠️ Tʜɪꜱ Cᴏᴍᴍᴀɴᴅ Cᴀɴ Oɴʟʏ Bᴇ Uꜱᴇᴅ Iɴ Gʀᴏᴜᴘꜱ.")

    chat_data = _db["chats"].find_one({"id": chat.id})
    if chat_data and chat_data.get("is_claimed"):
        claimed_by_name = chat_data.get("claimed_by_name", "Sᴏᴍᴇᴏɴᴇ")
        return await msg.reply_text(
            f"❌ <b>Tʜɪꜱ Gʀᴏᴜᴘ Rᴇᴡᴀʀᴅ Hᴀꜱ Aʟʀᴇᴀᴅʏ Bᴇᴇɴ Cʟᴀɪᴍᴇᴅ!</b>\n\n"
            f"👤 <b>Wɪɴɴᴇʀ:</b> {claimed_by_name}\n"
            f"<i>Bᴇ ꜰᴀꜱᴛᴇʀ ɪɴ ᴛʜᴇ ɴᴇxᴛ ɢʀᴏᴜᴘ!</i>",
            parse_mode="HTML"
        )

    data = get_user(user)
    if not data:
        return await msg.reply_text("❌ Yᴏᴜ Aʀᴇ Nᴏᴛ Rᴇɢɪꜱᴛᴇʀᴇᴅ Iɴ Tʜᴇ Dᴀᴛᴀʙᴀꜱᴇ.")

    try:
        member_count = await chat.get_member_count()
    except Exception:
        return await msg.reply_text("⚠️ Eʀʀᴏʀ Rᴇᴀᴅɪɴɢ Gʀᴏᴜᴘ Sɪᴢᴇ. Tʀʏ Aɢᴀɪɴ Lᴀᴛᴇʀ.")

    reward = 0
    tiers = [
        (10000, 5000000), (9000, 2500000), (8000, 1900000), (7000, 1500000),
        (6000, 1000000), (5000, 900000), (4000, 650000), (3000, 500000),
        (2500, 300000), (2000, 250000), (1500, 200000), (1000, 150000),
        (900, 120000), (800, 100000), (700, 80000), (600, 65000),
        (500, 50000), (400, 40000), (300, 30000), (200, 20000), (100, 10000)
    ]
    for req_mems, payout in tiers:
        if member_count >= req_mems:
            reward = payout
            break

    if reward == 0:
        return await msg.reply_text(f"⚠️ Yᴏᴜʀ Gʀᴏᴜᴘ Oɴʟʏ Hᴀꜱ {member_count} Mᴇᴍʙᴇʀꜱ.\nYᴏᴜ Nᴇᴇᴅ Aᴛ Lᴇᴀꜱᴛ 100 Mᴇᴍʙᴇʀꜱ Tᴏ Uꜱᴇ /claim.")

    users.update_one({"id": user.id}, {"$inc": {"coins": reward}, "$push": {"claimed_groups": chat.id}})
    _db["chats"].update_one(
        {"id": chat.id},
        {"$set": {"is_claimed": True, "claimed_by_id": user.id, "claimed_by_name": user.first_name,
                  "claim_date": datetime.now()}},
        upsert=True
    )

    await msg.reply_text(
        f"🎁 <b>Gʀᴏᴜᴘ Cʟᴀɪᴍ Sᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n\n"
        f"👤 <b>Wɪɴɴᴇʀ:</b> {user.first_name}\n"
        f"👥 <b>Gʀᴏᴜᴘ Sɪᴢᴇ:</b> {member_count} Mᴇᴍʙᴇʀꜱ\n"
        f"💰 <b>Rᴇᴡᴀʀᴅ:</b> {reward:,} Cᴏɪɴꜱ\n\n"
        f"<i>Tʜɪꜱ ɢʀᴏᴜᴘ's ʀᴇᴡᴀʀᴅ ʜᴀꜱ ʙᴇᴇɴ ᴇxʜᴀᴜꜱᴛᴇᴅ. Nᴏ ᴏɴᴇ ᴇʟꜱᴇ ᴄᴀɴ ᴄʟᴀɪᴍ ʜᴇʀᴇ!</i>",
        parse_mode="HTML"
    )
