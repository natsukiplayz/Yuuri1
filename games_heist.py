#!/usr/bin/env python3
"""Heist mini-game: /heist, /joinheist, /stfast, /stopheist + steal/share/out callbacks."""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config import OWNER_ID, heists, users
from bot.helpers import sc

HEIST_REWARD = 10000
HEIST_MAX_PLAYERS = 10
HEIST_MIN_PLAYERS = 2
HEIST_WAIT_TIME = 60
HEIST_DECISION_TIME = 40
MIN_JOIN_FEE = 100


async def heist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return await msg.reply_text(sc("This command only works in groups."))

    active = heists.find_one({"chat_id": chat.id})
    if active:
        return await msg.reply_text(
            f"❌ <b>{sc('A heist is already running.')}</b>\n💡 {sc('Use')} /stopheist {sc('if it is stuck.')}",
            parse_mode="HTML"
        )

    heists.insert_one({
        "chat_id": chat.id, "host": user.id, "started": False,
        "players": [{"id": user.id, "name": user.first_name, "bet": 0}], "choices": {}
    })

    await msg.reply_text(
        f"🏦 <b>{sc('Heist Created!')}</b>\n\n"
        f"💰 {sc('Prize Pot')}: <b>{HEIST_REWARD:,} {sc('Coins')}</b>\n"
        f"👑 {sc('Host')}: <b>{user.first_name}</b>\n"
        f"👥 {sc('Players')}: <b>1/{HEIST_MAX_PLAYERS}</b>\n\n"
        f"🔫 {sc('Join using')} /joinheist &lt;{sc('amount')}&gt;\n"
        f"⚡ {sc('Min fee')}: <b>{MIN_JOIN_FEE} {sc('coins')}</b>\n"
        f"⏳ {sc('Starting in')} <b>{HEIST_WAIT_TIME} {sc('seconds')}</b>",
        parse_mode="HTML"
    )
    context.job_queue.run_once(heist_timer, HEIST_WAIT_TIME, chat_id=chat.id)


async def joinheist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return await msg.reply_text(sc("This command only works in groups."))

    heist_data = heists.find_one({"chat_id": chat.id})
    if not heist_data:
        return await msg.reply_text(f"❌ <b>{sc('No active heist to join.')}</b>", parse_mode="HTML")
    if heist_data["started"]:
        return await msg.reply_text(f"❌ <b>{sc('The heist has already moved in!')}</b>", parse_mode="HTML")
    if any(p["id"] == user.id for p in heist_data["players"]):
        return await msg.reply_text(f"❌ <b>{sc('You are already in the crew.')}</b>", parse_mode="HTML")
    if len(heist_data["players"]) >= HEIST_MAX_PLAYERS:
        return await msg.reply_text(f"❌ <b>{sc('Crew is full!')} ({HEIST_MAX_PLAYERS}/{HEIST_MAX_PLAYERS})</b>", parse_mode="HTML")

    try:
        amount = int(context.args[0]) if context.args else MIN_JOIN_FEE
    except (ValueError, IndexError):
        return await msg.reply_text(f"❌ {sc('Use a valid number')}: /joinheist {MIN_JOIN_FEE}", parse_mode="HTML")

    if amount < MIN_JOIN_FEE:
        return await msg.reply_text(f"❌ {sc('Minimum join fee is')} <b>{MIN_JOIN_FEE} {sc('coins.')}</b>", parse_mode="HTML")

    user_db = users.find_one({"id": user.id})
    if not user_db or user_db.get("coins", 0) < amount:
        return await msg.reply_text(f"❌ <b>{sc('Not enough coins to join this heist!')}</b>", parse_mode="HTML")

    users.update_one({"id": user.id}, {"$inc": {"coins": -amount}})
    heists.update_one({"chat_id": chat.id}, {"$push": {"players": {"id": user.id, "name": user.first_name, "bet": amount}}})

    heist_data = heists.find_one({"chat_id": chat.id})
    player_count = len(heist_data["players"])
    players_list = "\n".join(
        f"  {'👑' if p['id'] == heist_data['host'] else '🔫'} <b>{p['name']}</b> — {p['bet']:,} {sc('coins')}"
        for p in heist_data["players"]
    )

    await msg.reply_text(
        f"✅ <b>{user.first_name}</b> {sc('joined the crew!')}\n\n💸 {sc('Entry')}: <b>{amount:,} {sc('coins')}</b>\n\n"
        f"👥 {sc('Crew')} ({player_count}/{HEIST_MAX_PLAYERS}):\n{players_list}",
        parse_mode="HTML"
    )


async def stfast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    heist_data = heists.find_one({"chat_id": chat.id})
    if not heist_data:
        return await msg.reply_text(f"❌ <b>{sc('No active heist.')}</b>", parse_mode="HTML")
    if heist_data["started"]:
        return await msg.reply_text(f"❌ <b>{sc('Heist already started.')}</b>", parse_mode="HTML")
    if heist_data["host"] != user.id:
        return await msg.reply_text(f"❌ <b>{sc('Only the host can start early.')}</b>", parse_mode="HTML")

    await msg.reply_text(f"⚡ <b>{sc('Host started the heist early!')}</b>", parse_mode="HTML")
    await start_heist(chat.id, context)


async def stopheist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    heist_data = heists.find_one({"chat_id": chat.id})
    if not heist_data:
        return await msg.reply_text(f"❌ <b>{sc('No heist is running.')}</b>", parse_mode="HTML")

    chat_member = await chat.get_member(user.id)
    is_admin = chat_member.status in ("administrator", "creator")
    if user.id != heist_data["host"] and not is_admin and user.id != OWNER_ID:
        return await msg.reply_text(f"❌ <b>{sc('Only the host or an admin can stop the heist.')}</b>", parse_mode="HTML")

    refunded = 0
    if not heist_data["started"]:
        for p in heist_data["players"]:
            if p["bet"] > 0:
                users.update_one({"id": p["id"]}, {"$inc": {"coins": p["bet"]}})
                refunded += p["bet"]

    heists.delete_one({"chat_id": chat.id})
    await msg.reply_text(f"🛑 <b>{sc('Heist stopped.')}</b>\n\n💸 {sc('Total refunded')}: <b>{refunded:,} {sc('coins')}</b>", parse_mode="HTML")


async def heist_timer(context: ContextTypes.DEFAULT_TYPE):
    await start_heist(context.job.chat_id, context)


async def start_heist(chat_id: int, context):
    heist_data = heists.find_one({"chat_id": chat_id})
    if not heist_data or heist_data["started"]:
        return

    if len(heist_data["players"]) < HEIST_MIN_PLAYERS:
        await context.bot.send_message(
            chat_id,
            f"❌ <b>{sc('Not enough players. Heist failed!')}</b>\n\n💸 {sc('All entry fees have been refunded.')}",
            parse_mode="HTML"
        )
        for p in heist_data["players"]:
            if p["bet"] > 0:
                users.update_one({"id": p["id"]}, {"$inc": {"coins": p["bet"]}})
        heists.delete_one({"chat_id": chat_id})
        return

    heists.update_one({"chat_id": chat_id}, {"$set": {"started": True}})

    player_count = len(heist_data["players"])
    total_pot = sum(p["bet"] for p in heist_data["players"]) + HEIST_REWARD

    await context.bot.send_animation(
        chat_id, "https://media.tenor.com/U1Xw3ZL0E7kAAAAC/money-heist-mask.gif",
        caption=(f"🏦 <b>{sc('Breaking into the vault...')}</b>\n\n👥 {sc('Crew Size')}: <b>{player_count}</b>\n"
                 f"💰 {sc('Total Pot')}: <b>{total_pot:,} {sc('coins')}</b>\n\n📩 <b>{sc('Check your DM to make your choice!')}</b>"),
        parse_mode="HTML"
    )

    await asyncio.sleep(4)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"😈 {sc('Steal')}", callback_data=f"heist_steal_{chat_id}"),
         InlineKeyboardButton(f"🤝 {sc('Share')}", callback_data=f"heist_share_{chat_id}")],
        [InlineKeyboardButton(f"🚪 {sc('Out')}", callback_data=f"heist_out_{chat_id}")]
    ])

    for p in heist_data["players"]:
        try:
            await context.bot.send_message(
                p["id"],
                f"🏦 <b>{sc('Choose Wisely!')}</b>\n\n💰 {sc('Vault Prize')}: <b>{HEIST_REWARD:,} {sc('coins')}</b>\n"
                f"👥 {sc('Crew')}: <b>{player_count} {sc('players')}</b>\n\n"
                f"😈 <b>{sc('Steal')}</b> — {sc('Take everything. If others steal too, all lose.')}\n"
                f"🤝 <b>{sc('Share')}</b> — {sc('Split fairly with sharers.')}\n"
                f"🚪 <b>{sc('Out')}</b> — {sc('Walk away. Get your entry fee back.')}\n\n"
                f"⏳ {sc('You have')} <b>{HEIST_DECISION_TIME} {sc('seconds')}</b>",
                parse_mode="HTML", reply_markup=keyboard
            )
        except Exception:
            pass

    context.job_queue.run_once(heist_result_timer, HEIST_DECISION_TIME, chat_id=chat_id)


async def heist_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    choice = data[1]
    chat_id = int(data[2])
    uid = query.from_user.id

    heist_data = heists.find_one({"chat_id": chat_id})
    if not heist_data:
        return await query.edit_message_text(f"❌ <b>{sc('Heist no longer active.')}</b>", parse_mode="HTML")
    if not heist_data.get("started"):
        return await query.answer(sc("Heist hasn't started yet."), show_alert=True)
    if not any(p["id"] == uid for p in heist_data["players"]):
        return await query.answer(sc("You are not in this heist."), show_alert=True)
    if str(uid) in heist_data.get("choices", {}):
        return await query.answer(sc("You already made your choice."), show_alert=True)

    heists.update_one({"chat_id": chat_id}, {"$set": {f"choices.{uid}": choice}})

    choice_text = {
        "steal": f"😈 <b>{sc('You chose to Steal!')}</b>\n{sc('Bold move. Hope no one else steals...')}",
        "share": f"🤝 <b>{sc('You chose to Share!')}</b>\n{sc('Honorable. Hope the crew agrees.')}",
        "out": f"🚪 <b>{sc('You chose to walk Out.')}</b>\n{sc('Your entry fee will be returned.')}",
    }.get(choice, sc("Choice recorded."))

    await query.edit_message_text(choice_text, parse_mode="HTML")


async def heist_result_timer(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    heist_data = heists.find_one({"chat_id": chat_id})
    if not heist_data:
        return

    players = heist_data["players"]
    choices = heist_data.get("choices", {})

    stealers = [p for p in players if choices.get(str(p["id"])) == "steal"]
    sharers = [p for p in players if choices.get(str(p["id"])) == "share"]
    outers = [p for p in players if choices.get(str(p["id"])) == "out"]
    silent = [p for p in players if str(p["id"]) not in choices]

    for p in outers + silent:
        if p["bet"] > 0:
            users.update_one({"id": p["id"]}, {"$inc": {"coins": p["bet"]}})

    result = f"🏦 <b>{sc('Heist Result')}</b>\n\n"

    if not stealers and not sharers:
        result += f"🚪 <b>{sc('Everyone walked out.')}</b>\n{sc('No one gained or lost anything.')}"
    elif not stealers and sharers:
        total_pot = HEIST_REWARD + sum(p["bet"] for p in sharers)
        reward = total_pot // len(sharers)
        for p in sharers:
            users.update_one({"id": p["id"]}, {"$inc": {"coins": reward}})
        names = ", ".join(f"<b>{p['name']}</b>" for p in sharers)
        result += (f"🤝 <b>{sc('The crew shared the loot!')}</b>\n\n👥 {sc('Sharers')}: {names}\n"
                   f"💰 {sc('Each received')}: <b>{reward:,} {sc('coins')}</b>")
    elif len(stealers) == 1 and not sharers:
        bonus = int(HEIST_REWARD * 1.5) + stealers[0]["bet"]
        users.update_one({"id": stealers[0]["id"]}, {"$inc": {"coins": bonus}})
        result += (f"😈 <b>{stealers[0]['name']} {sc('stole everything!')}</b>\n\n"
                   f"💰 {sc('Total haul')}: <b>{bonus:,} {sc('coins')}</b>\n😢 {sc('The rest of the crew got nothing.')}")
    elif len(stealers) == 1 and sharers:
        total_pot = HEIST_REWARD + sum(p["bet"] for p in sharers) + stealers[0]["bet"]
        users.update_one({"id": stealers[0]["id"]}, {"$inc": {"coins": total_pot}})
        result += (f"😈 <b>{stealers[0]['name']} {sc('betrayed the crew!')}</b>\n\n"
                   f"💰 {sc('Stealer took')}: <b>{total_pot:,} {sc('coins')}</b>\n💔 {sc('Sharers lost their entry fees.')}")
    else:
        result += (f"🚨 <b>{sc('Too many greedy players!')}</b>\n\n😈 {sc('Stealers')}: "
                   + ", ".join(f"<b>{p['name']}</b>" for p in stealers)
                   + f"\n💸 {sc('Everyone lost their entry fee. Vault alarm triggered!')}")

    result += (f"\n\n📊 <b>{sc('Summary')}</b>\n😈 {sc('Stealers')}: <b>{len(stealers)}</b>  "
               f"🤝 {sc('Sharers')}: <b>{len(sharers)}</b>  🚪 {sc('Out')}: <b>{len(outers) + len(silent)}</b>")

    await context.bot.send_message(chat_id, result, parse_mode="HTML")
    heists.delete_one({"chat_id": chat_id})
