#!/usr/bin/env python3
"""Multiplayer card game: /card <amount> | /bet <amount> | /flip <slot>
plus /card2../5 invite modes, /cardlock, /cancelgames, /topcarder."""

import asyncio
import random
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatAction, ParseMode

from bot.config import OWNER_ID, users
from bot.helpers import get_user, save_user, is_premium, sc

MIN_BET = 500
JOIN_WINDOW = 120
REMIND_EVERY = 15
FLIP_TIMEOUT = 60
MAX_ROUNDS = 4
TAX_NORMAL = 0.10
TAX_PREMIUM = 0.05
XP_PER_WIN = 180


def card_points(val: int) -> int:
    return val * 2


active_games: dict = {}
CARD_SLOTS = ['a', 'b', 'c', 'd']
card_game_locked: dict = {}


def is_card_locked(chat_id: int) -> bool:
    return card_game_locked.get(chat_id, False)


def deal_equal_sum_cards(num_players: int) -> list:
    while True:
        first_hand = [random.randint(1, 10) for _ in range(4)]
        target = sum(first_hand)
        all_hands = [first_hand]
        success = True
        for _ in range(num_players - 1):
            hand = _generate_hand_with_sum(target)
            if hand is None:
                success = False
                break
            all_hands.append(hand)
        if success:
            break

    noise_pool = list(range(num_players))
    random.shuffle(noise_pool)

    return [
        {"cards": {slot: hand[i] for i, slot in enumerate(CARD_SLOTS)}, "_point_noise": noise_pool[idx]}
        for idx, hand in enumerate(all_hands)
    ]


def _generate_hand_with_sum(target: int, attempts: int = 300):
    for _ in range(attempts):
        cards = []
        remaining = target
        for i in range(3):
            slots_left = 3 - i
            lo = max(1, remaining - slots_left * 10)
            hi = min(10, remaining - slots_left)
            if lo > hi:
                break
            c = random.randint(lo, hi)
            cards.append(c)
            remaining -= c
        else:
            if 1 <= remaining <= 10:
                cards.append(remaining)
                return cards
    return None


def _build_cards_text(pdata: dict, played_slot=None, played_val=None) -> str:
    lines = []
    for s, v in pdata["cards"].items():
        lines.append(f"  {s.upper()} ➜ ✖️ {sc('used')}" if v is None else f"  {s.upper()} ➜ {v}")

    header = ""
    if played_slot and played_val is not None:
        pts = card_points(played_val)
        header = f"✅ {sc('Played')} {played_slot.upper()} ➜ <b>{played_val}</b>  (+{pts} {sc('pts')})\n\n"

    available = [s for s, v in pdata["cards"].items() if v is not None]
    slots_left = ", ".join(s.upper() for s in available) or sc("None")
    flip_hint = " / ".join(available) if available else sc("none left")

    footer = f"\n\n🎴 {sc('Available')}: {slots_left}\n📌 /flip {flip_hint}"
    return f"{header}🃏 {sc('Your Cards')}:\n" + "\n".join(lines) + footer


def _build_cards_text_with_points(pdata: dict) -> str:
    lines = [f"  {s.upper()} ➜ ✖️ {sc('used')}" for s in CARD_SLOTS]
    total_pts_label = sc("Total Points")
    return "🃏 " + sc("Your Cards") + ":\n" + "\n".join(lines) + f"\n\n🧮 {total_pts_label}: <b>{pdata['points']}</b>"


GAME_INFO = (
    "👑 <b>Yuuri Mɪɴɪ Gᴀᴍᴇꜱ Uꜱɪɴɢ Eᴀʀɴᴇᴅ Eᴄᴏɴᴏᴍʏ Bᴀʟᴀɴᴄᴇ</b> 👑\n\n"
    "🎮 <b>Yuuri Cᴀʀᴅ Gᴀᴍᴇ</b> 🎮\n\n"
    "❤️‍🔥 Eᴀᴄʜ ᴘʟᴀʏᴇʀ ɢᴇᴛꜱ <b>4 ʜɪᴅᴅᴇɴ ᴄᴀʀᴅꜱ</b> ʟᴀʙᴇʟᴇᴅ A, B, C, D.\n"
    "❤️‍🔥 Iɴ ᴇᴠᴇʀʏ ʀᴏᴜɴᴅ, ᴀʟʟ ᴘʟᴀʏᴇʀꜱ ᴄʜᴏᴏꜱᴇ ᴏɴᴇ ᴄᴀʀᴅ ᴛᴏ ꜰʟɪᴘ — ᴛʜᴇ ʜɪɢʜᴇꜱᴛ ᴡɪɴꜱ ᴛʜᴇ ʀᴏᴜɴᴅ.\n"
    "❤️‍🔥 Tʜᴇ ɢᴀᴍᴇ ʟᴀꜱᴛꜱ <b>4 ʀᴏᴜɴᴅꜱ</b> — ʜɪɢʜᴇꜱᴛ ᴛᴏᴛᴀʟ ꜱᴄᴏʀᴇ ᴡɪɴꜱ 🏆\n"
    "❤️‍🔥 Aʟʟ ᴘʟᴀʏᴇʀꜱ ɢᴇᴛ ᴇǫᴜᴀʟ ᴄᴀʀᴅ ꜱᴜᴍꜱ — ꜰᴀɪʀ ꜰᴏʀ ᴇᴠᴇʀʏᴏɴᴇ!\n\n"
    "📊 <b>Pᴏɪɴᴛꜱ Sʏꜱᴛᴇᴍ</b> (Cᴀʀᴅ × 2)\n"
    "  1➜2  2➜4  3➜6  4➜8  5➜10\n  6➜12  7➜14  8➜16  9➜18  10➜20\n\n"
    "👼👼 <b>Cᴏᴍᴍᴀɴᴅꜱ</b>\n"
    "/card <amount> — Sᴛᴀʀᴛ ᴀ ɴᴇᴡ ɢᴀᴍᴇ\n"
    "/card2 <amount> @user> — 1ᴠ1 ᴘʀɪᴠᴀᴛᴇ ɢᴀᴍᴇ\n"
    "/card3-5 <amount> — ɪɴᴠɪᴛᴇ-ᴏɴʟʏ ɢᴀᴍᴇ\n"
    "/bet <amount> — Jᴏɪɴ ᴛʜᴇ ɢᴀᴍᴇ\n"
    "/flip a/b/c/d — Pʟᴀʏ ʏᴏᴜʀ ᴍᴏᴠᴇ\n\n"
    "😀 <b>Nᴏᴛᴇꜱ & Iɴꜱᴛʀᴜᴄᴛɪᴏɴꜱ</b>\n"
    "✅ Eᴀᴄʜ ᴛᴜʀɴ ʜᴀꜱ ᴀ <b>60-ꜱᴇᴄᴏɴᴅ</b> ᴛɪᴍᴇ ʟɪᴍɪᴛ\n"
    "✅ Aᴜᴛᴏ-ᴘʟᴀʏ ᴀᴄᴛɪᴠᴀᴛᴇꜱ ɪꜰ ʏᴏᴜ ᴅᴏɴ'ᴛ ʀᴇꜱᴘᴏɴᴅ ɪɴ ᴛɪᴍᴇ\n"
    "✅ Eᴀᴄʜ ᴄᴀʀᴅ ᴄᴀɴ ʙᴇ ᴜꜱᴇᴅ ᴏɴʟʏ ᴏɴᴄᴇ ᴘᴇʀ ɢᴀᴍᴇ\n"
    "✅ Tʜᴇ ꜰɪɴᴀʟ ᴡɪɴɴᴇʀ ɢᴇᴛꜱ ᴛʜᴇ ʀᴇᴡᴀʀᴅ\n"
    "✅ Iɴ ᴄᴀꜱᴇ ᴏꜰ ᴀ ᴛɪᴇ, ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ ɢᴇᴛꜱ ᴘʀɪᴏʀɪᴛʏ 👑"
)


async def cmd_cardhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(GAME_INFO, parse_mode="HTML")


def _track_bot_msg(game: dict, chat_id: int, msg):
    if msg:
        game.setdefault("tracked_msgs", []).append((chat_id, msg.message_id))


async def _delete_tracked(context, game: dict):
    for chat_id, msg_id in game.get("tracked_msgs", []):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass


# ============================ /card ============================

async def cmd_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    if chat.type == "private":
        await msg.reply_text(sc("Group only."))
        return
    chat_id = chat.id

    if is_card_locked(chat_id):
        return await msg.reply_text("🔒 <b>Cᴀʀᴅ Gᴀᴍᴇ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Lᴏᴄᴋᴇᴅ Iɴ Tʜɪꜱ Gʀᴏᴜᴘ.</b>", parse_mode="HTML")

    if not context.args:
        return await msg.reply_text(f"<b>{sc('Usage')}:</b> /card <{sc('amount')}>", parse_mode="HTML")

    try:
        bet = int(context.args[0])
    except ValueError:
        return await msg.reply_text(sc("Invalid amount."))

    if bet <= MIN_BET:
        return await msg.reply_text(f"⚠️ {sc('Min bet is')} {MIN_BET}.")

    if chat_id in active_games and active_games[chat_id]["phase"] != "done":
        return await msg.reply_text(f"🚫 {sc('Game already running.')}")

    host_data = get_user(user)
    if not host_data or host_data.get("coins", 0) < bet:
        return await msg.reply_text(sc("Insufficient coins."))

    host_data["coins"] -= bet
    save_user(host_data)

    game = {
        "host_id": user.id, "bet": bet,
        "players": {user.id: {"name": user.first_name, "cards": {}, "points": 0, "_point_noise": 0,
                               "premium": is_premium(host_data, context), "dm_msg_id": None}},
        "round": 1, "turn_order": [], "current_turn": 0, "round_plays": {}, "phase": "joining",
        "join_task": None, "remind_task": None, "tracked_msgs": [], "invite_mode": False,
    }
    active_games[chat_id] = game
    game["tracked_msgs"].append((chat_id, msg.message_id))

    sent = await msg.reply_text(
        f"♠️ <b>{sc('Card Game Started.')}</b>\n\n💰 {sc('Entry Fee')}: <b>{bet}</b>\n"
        f"👉 {sc('Use')} /bet {bet} {sc('to join.')}\n⏳ {sc('Game Starts In 2 Minutes.')}",
        parse_mode="HTML"
    )
    _track_bot_msg(game, chat_id, sent)

    game["remind_task"] = asyncio.create_task(_remind_loop(context, chat_id, bet))
    game["join_task"] = asyncio.create_task(_join_countdown(context, chat_id))


async def _remind_loop(context, chat_id: int, bet: int):
    elapsed = 0
    while elapsed < JOIN_WINDOW:
        await asyncio.sleep(REMIND_EVERY)
        elapsed += REMIND_EVERY
        game = active_games.get(chat_id)
        if not game or game["phase"] != "joining":
            return
        remaining = JOIN_WINDOW - elapsed
        count = len(game["players"])
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏳ <b>{remaining} {sc('sec Left.')}</b> {sc('Use')} /bet &lt;{sc('amount')}&gt;\n👥 {sc('Joined')}: <b>{count}</b>",
            parse_mode="HTML"
        )
        _track_bot_msg(game, chat_id, sent)


async def _join_countdown(context, chat_id: int):
    await asyncio.sleep(JOIN_WINDOW)
    game = active_games.get(chat_id)
    if not game or game["phase"] != "joining":
        return
    if game.get("remind_task"):
        game["remind_task"].cancel()

    players = game["players"]
    if len(players) < 2:
        for uid in players:
            u = users.find_one({"id": uid})
            if u:
                u["coins"] += game["bet"]
                save_user(u)
        sent = await context.bot.send_message(chat_id=chat_id, text=f"👥 {sc('Need at least 2 players.')}\n💸 {sc('Refunded.')}")
        _track_bot_msg(game, chat_id, sent)
        await _delete_tracked(context, game)
        active_games.pop(chat_id, None)
        return

    await _launch_game(context, chat_id)


async def _launch_game(context, chat_id: int):
    game = active_games.get(chat_id)
    players = game["players"]

    hands = deal_equal_sum_cards(len(players))
    for i, (uid, pdata) in enumerate(players.items()):
        pdata["cards"] = hands[i]["cards"]
        pdata["_point_noise"] = hands[i]["_point_noise"]

    game["phase"] = "playing"
    game["turn_order"] = list(players.keys())
    random.shuffle(game["turn_order"])

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🃏 <b>{sc('Game Started!')}</b>\n\n👥 {sc('Total Players')}: <b>{len(players)}</b>\n\n📩 {sc('Check Your Cards In My DM.')}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📩 " + sc("View My Cards"), url="https://t.me/im_yuuribot")]])
    )
    _track_bot_msg(game, chat_id, sent)

    for uid, pdata in players.items():
        await _send_cards_dm(context, uid, pdata)

    await _start_round(context, chat_id)


# ============================ /bet ============================

async def cmd_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message

    if chat.type == "private":
        await msg.reply_text(sc("Group only."))
        return
    chat_id = chat.id

    if is_card_locked(chat_id):
        return await msg.reply_text("🔒 <b>Cᴀʀᴅ Gᴀᴍᴇ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Lᴏᴄᴋᴇᴅ Iɴ Tʜɪꜱ Gʀᴏᴜᴘ.</b>", parse_mode="HTML")

    game = active_games.get(chat_id)
    if not game or game["phase"] == "done":
        return await msg.reply_text(f"{sc('No game running.')}  /card <{sc('amount')}>")
    if game["phase"] != "joining":
        return await msg.reply_text(sc("Game already started."))
    if game.get("invite_mode"):
        return await msg.reply_text(sc("This is a private invite-only game."))

    game["tracked_msgs"].append((chat_id, msg.message_id))
    bet = game["bet"]

    if not context.args:
        return await msg.reply_text(f"<b>{sc('Usage')}:</b> /bet {bet}", parse_mode="HTML")

    try:
        user_bet = int(context.args[0])
    except ValueError:
        return await msg.reply_text(sc("Invalid amount."))

    if user_bet != bet:
        return await msg.reply_text(f"<b>{sc('Usage')}:</b> /bet {bet}", parse_mode="HTML")

    if user.id in game["players"]:
        return await msg.reply_text(f"🙅 {sc('Already joined.')}  👥 {len(game['players'])}")

    user_data = get_user(user)
    if not user_data or user_data.get("coins", 0) < bet:
        return await msg.reply_text(sc("Insufficient coins."))

    user_data["coins"] -= bet
    save_user(user_data)

    game["players"][user.id] = {"name": user.first_name, "cards": {}, "points": 0, "_point_noise": 0,
                                 "premium": is_premium(user_data, context), "dm_msg_id": None}

    sent = await msg.reply_text(f"🧚 <b>{user.first_name}</b> {sc('joined.')}  👥 {len(game['players'])}", parse_mode="HTML")
    _track_bot_msg(game, chat_id, sent)


async def _send_cards_dm(context, uid: int, pdata: dict, played_slot=None, played_val=None):
    text = _build_cards_text(pdata, played_slot, played_val)
    try:
        mid = pdata.get("dm_msg_id")
        if mid:
            await context.bot.edit_message_text(chat_id=uid, message_id=mid, text=text, parse_mode="HTML")
        else:
            sent = await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            pdata["dm_msg_id"] = sent.message_id
    except Exception:
        pass


# ============================ ROUND MANAGEMENT ============================

async def _start_round(context, chat_id: int):
    game = active_games.get(chat_id)
    if not game:
        return
    game["round_plays"] = {}
    game["current_turn"] = 0
    random.shuffle(game["turn_order"])
    await _prompt_next_player(context, chat_id)


async def _prompt_next_player(context, chat_id: int):
    game = active_games.get(chat_id)
    if not game:
        return

    rnd = game["round"]
    order = game["turn_order"]
    turn_index = game["current_turn"]

    if turn_index >= len(order):
        await _finish_round(context, chat_id)
        return

    uid = order[turn_index]
    pdata = game["players"][uid]
    name = pdata["name"]

    remaining = {s: v for s, v in pdata["cards"].items() if v is not None}
    if not remaining:
        game["current_turn"] += 1
        await _prompt_next_player(context, chat_id)
        return

    slots = " / ".join(s for s in remaining)
    clickable_name = f'<a href="tg://user?id={uid}">{name}</a>'

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=f"👉 {clickable_name} {sc('Its Your Turn.')}\n⏰ {sc('You Have 60 Seconds.')}\n\n🎴 {sc('Use')} /flip <code>{slots}</code>",
        parse_mode="HTML"
    )
    _track_bot_msg(game, chat_id, sent)

    try:
        await context.bot.send_message(
            chat_id=uid,
            text=f"🔔 {sc('Its your turn!')} — {sc('Round')} {rnd}\n🎴 {sc('Flip')} /flip <code>{slots}</code> {sc('in the group.')}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    asyncio.create_task(_auto_flip(context, chat_id, uid, rnd))


async def _auto_flip(context, chat_id: int, uid: int, rnd: int):
    await asyncio.sleep(FLIP_TIMEOUT)
    game = active_games.get(chat_id)
    if not game or game["phase"] != "playing" or game["round"] != rnd:
        return
    if uid in game["round_plays"]:
        return

    pdata = game["players"][uid]
    remaining = {s: v for s, v in pdata["cards"].items() if v is not None}
    if not remaining:
        return

    slot, val = random.choice(list(remaining.items()))
    pdata["cards"][slot] = None
    pts = card_points(val)
    game["round_plays"][uid] = (val, pts)

    await _send_cards_dm(context, uid, pdata, played_slot=slot, played_val=val)

    plays_so_far = game["round_plays"]
    order = game["turn_order"]
    played_lines = "\n".join(
        f"⏰ <b>{game['players'][u]['name']}</b> ➜ <b>{plays_so_far[u][0]}</b> {sc('(auto)')}"
        if u == uid else f"• <b>{game['players'][u]['name']}</b> ➜ <b>{plays_so_far[u][0]}</b>"
        for u in order if u in plays_so_far
    )
    waiting_uids = [u for u in order if u not in plays_so_far]
    waiting_line = (
        f"\n⏳ {sc('Waiting')}: " + ", ".join(f'<a href="tg://user?id={u}">{game["players"][u]["name"]}</a>' for u in waiting_uids)
    ) if waiting_uids else ""

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🃏 <b>{sc('Round')} {rnd} — {sc('Flips So Far')}</b>\n\n{played_lines}{waiting_line}",
        parse_mode="HTML"
    )
    _track_bot_msg(game, chat_id, sent)

    game["current_turn"] += 1
    await _prompt_next_player(context, chat_id)


# ============================ /flip ============================

async def cmd_flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == "private":
        return await msg.reply_text(f"🚫 {sc('Use in group.')}  /flip a / b / c / d")

    uid = user.id
    target_chat_id = None
    for cid, g in active_games.items():
        if uid in g["players"] and g["phase"] == "playing":
            target_chat_id = cid
            break

    if target_chat_id is None:
        return await msg.reply_text(sc("No active game."))

    game = active_games[target_chat_id]
    game["tracked_msgs"].append((chat.id, msg.message_id))

    rnd = game["round"]
    order = game["turn_order"]

    if game["current_turn"] >= len(order) or order[game["current_turn"]] != uid:
        return await msg.reply_text(sc("Not your turn."))
    if uid in game["round_plays"]:
        return await msg.reply_text(sc("Already played this round."))
    if not context.args:
        return await msg.reply_text(f"<b>{sc('Usage')}:</b> /flip a / b / c / d", parse_mode="HTML")

    raw_slot = context.args[0].lower().strip()
    if raw_slot not in CARD_SLOTS:
        return await msg.reply_text(f"❌ {sc('Invalid slot.')}  a / b / c / d")

    pdata = game["players"][uid]
    if pdata["cards"].get(raw_slot) is None:
        return await msg.reply_text(sc("Card already used."))

    val = pdata["cards"][raw_slot]
    pdata["cards"][raw_slot] = None
    pts = card_points(val)
    game["round_plays"][uid] = (val, pts)

    await _send_cards_dm(context, uid, pdata, played_slot=raw_slot, played_val=val)

    plays_so_far = game["round_plays"]
    played_lines = "\n".join(f"• <b>{game['players'][u]['name']}</b> ➜ <b>{plays_so_far[u][0]}</b>" for u in order if u in plays_so_far)
    waiting_uids = [u for u in order if u not in plays_so_far]
    waiting_line = (
        f"\n⏳ {sc('Waiting')}: " + ", ".join(f'<a href="tg://user?id={u}">{game["players"][u]["name"]}</a>' for u in waiting_uids)
    ) if waiting_uids else ""

    sent = await context.bot.send_message(
        chat_id=target_chat_id,
        text=f"🃏 <b>{sc('Round')} {rnd} — {sc('Flips So Far')}</b>\n\n{played_lines}{waiting_line}",
        parse_mode="HTML"
    )
    _track_bot_msg(game, target_chat_id, sent)

    game["current_turn"] += 1
    await _prompt_next_player(context, target_chat_id)


# ============================ FINISH ROUND / GAME ============================

async def _finish_round(context, chat_id: int):
    game = active_games.get(chat_id)
    if not game:
        return

    rnd = game["round"]
    plays = game["round_plays"]
    players = game["players"]

    if plays:
        max_val = max(v for v, _ in plays.values())
        r_winners = [uid for uid, (v, _) in plays.items() if v == max_val]
        round_total_pts = sum(pts for _, pts in plays.values())

        for uid in r_winners:
            players[uid]["points"] += round_total_pts

        sorted_plays = sorted(plays.items(), key=lambda x: x[1][0], reverse=True)
        lines = "\n".join(
            f"{'🏆' if uid in r_winners else '•'} <b>{players[uid]['name']}</b> ➜ <b>{val}</b>  (+{pts} {sc('pts')})"
            for uid, (val, pts) in sorted_plays
        )
        winner_names = ", ".join(f"<b>{players[uid]['name']}</b>" for uid in r_winners)

        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=(f"🎯 <b>{sc('Round')} {rnd} {sc('Result')}</b>\n\n{lines}\n\n"
                  f"🏆 {sc('Winner')}: {winner_names}\n🎴 {sc('Highest Card')}: <b>{max_val}</b>\n"
                  f"💰 {sc('Points Awarded')}: <b>{round_total_pts}</b>"),
            parse_mode="HTML"
        )
        _track_bot_msg(game, chat_id, sent)

    if rnd >= MAX_ROUNDS:
        await _finish_game(context, chat_id)
        return

    game["round"] += 1
    game["round_plays"] = {}
    game["current_turn"] = 0

    sent = await context.bot.send_message(chat_id=chat_id, text=f"✅ {sc('Round')} {game['round']} {sc('Started.')}", parse_mode="HTML")
    _track_bot_msg(game, chat_id, sent)
    await _start_round(context, chat_id)


def _resolve_tie(tied_uids: list, players: dict):
    premium_tied = [uid for uid in tied_uids if players[uid].get("premium")]
    if premium_tied and len(premium_tied) < len(tied_uids):
        return random.choice(premium_tied), True
    pool = premium_tied if premium_tied else tied_uids
    return random.choice(pool), False


async def _finish_game(context, chat_id: int):
    game = active_games.get(chat_id)
    if not game:
        return

    game["phase"] = "done"
    players = game["players"]
    bet = game["bet"]
    total_pot = bet * len(players)

    for pdata in players.values():
        pdata["points"] += pdata.get("_point_noise", 0)

    max_points = max(p["points"] for p in players.values())
    tied_uids = [uid for uid, p in players.items() if p["points"] == max_points]
    premium_priority_used = False

    if len(tied_uids) > 1:
        winner_uid, premium_priority_used = _resolve_tie(tied_uids, players)
    else:
        winner_uid = tied_uids[0]

    winner_pdata = players[winner_uid]
    tax_rate = TAX_PREMIUM if winner_pdata["premium"] else TAX_NORMAL
    tax_label = "5%" if winner_pdata["premium"] else "10%"
    net_each = int(total_pot * (1 - tax_rate))
    winner_name = winner_pdata["name"]
    total_points = winner_pdata["points"]
    xp_gained = random.randint(10, 300)

    u = users.find_one({"id": winner_uid})
    if u:
        u["coins"] = u.get("coins", 0) + net_each
        u["xp"] = u.get("xp", 0) + xp_gained
        streak = u.get("card_streak", 0) + 1
        u["card_streak"] = streak
        u["card_wins_total"] = u.get("card_wins_total", 0) + net_each
        save_user(u)
    else:
        streak = 1

    winners_pts_label = sc("Winner's Points")
    for uid, pdata in players.items():
        is_winner = (uid == winner_uid)
        try:
            mid = pdata.get("dm_msg_id")
            if mid:
                try:
                    await context.bot.edit_message_text(chat_id=uid, message_id=mid, text=_build_cards_text_with_points(pdata), parse_mode="HTML")
                except Exception:
                    pass

            dm_text = (
                f"🏁 <b>{sc('Game Over!')}</b>\n\n🧮 {sc('Your Total Points')}: <b>{pdata['points']}</b>\n"
                f"👑 {sc('You Won!')}\n💰 {sc('Winning Amount')}: <b>{net_each}</b>"
            ) if is_winner else (
                f"🏁 <b>{sc('Game Over!')}</b>\n\n🧮 {sc('Your Total Points')}: <b>{pdata['points']}</b>\n"
                f"🏆 {winners_pts_label}: <b>{total_points}</b>\n👑 {sc('Final Winner')}: <b>{winner_name}</b>\n"
                f"💰 {sc('Winning Amount')}: <b>{net_each}</b>"
            )
            await context.bot.send_message(chat_id=uid, text=dm_text, parse_mode="HTML")
        except Exception:
            pass

    await _delete_tracked(context, game)

    winner_photo_file = None
    try:
        photos = await context.bot.get_user_profile_photos(winner_uid, limit=1)
        if photos.total_count > 0:
            winner_photo_file = photos.photos[0][-1].file_id
    except Exception:
        pass

    clickable_winner = f'<a href="tg://user?id={winner_uid}">{winner_name}</a>'
    fee_emoji = "💓" if winner_pdata["premium"] else "💔"
    tie_notice = f"💸 <b>{sc('Tie detected! Premium priority.')}</b>\n\n" if premium_priority_used else ""

    announcement = (
        f"{tie_notice}👑 <b>Fɪɴᴀʟ Wɪɴɴᴇʀ</b> 👑\n\n🌺 {clickable_winner}\n"
        f"🎯 {sc('Total Points')}: <b>{total_points}</b>\n"
        f"💰 {sc('Won')}: <b>{net_each}</b> ({fee_emoji} {tax_label} {sc('Fee')})\n"
        f"🔥 {sc('Streak')}: <b>{streak}</b>\n⚡ {sc('Xp Gained')}: <b>+{xp_gained}</b>\n\n"
        f"👉 {sc('Play Again Using')} : /card {sc('Amount')}"
    )

    if winner_photo_file:
        winner_msg = await context.bot.send_photo(chat_id=chat_id, photo=winner_photo_file, caption=announcement, parse_mode="HTML")
    else:
        winner_msg = await context.bot.send_message(chat_id=chat_id, text=announcement, parse_mode="HTML")

    try:
        await context.bot.pin_chat_message(chat_id=chat_id, message_id=winner_msg.message_id, disable_notification=False)
    except Exception:
        pass

    active_games.pop(chat_id, None)


# ============================ LOCK / CANCEL / STATS ============================

async def cmd_cardlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        return await msg.reply_text("❌ Gʀᴏᴜᴘ Oɴʟʏ.")

    chat_member = await chat.get_member(user.id)
    is_admin = chat_member.status in ("administrator", "creator")
    if not is_admin and user.id != OWNER_ID:
        return await msg.reply_text("❌ Aᴅᴍɪɴs Oɴʟʏ.")

    chat_id = chat.id
    current = card_game_locked.get(chat_id, False)
    card_game_locked[chat_id] = not current

    if card_game_locked[chat_id]:
        await msg.reply_text(
            "🔒 <b>Cᴀʀᴅ Gᴀᴍᴇ Lᴏᴄᴋᴇᴅ!</b>\n\n♠️ Nᴏ ɴᴇᴡ ɢᴀᴍᴇs ᴄᴀɴ ʙᴇ sᴛᴀʀᴛᴇᴅ.\n💡 Usᴇ /cardlock ᴀɢᴀɪɴ ᴛᴏ ᴜɴʟᴏᴄᴋ.",
            parse_mode="HTML"
        )
    else:
        await msg.reply_text("🔓 <b>Cᴀʀᴅ Gᴀᴍᴇ Uɴʟᴏᴄᴋᴇᴅ!</b>\n\n♠️ Pʟᴀʏᴇʀs ᴄᴀɴ sᴛᴀʀᴛ ɴᴇᴡ ɢᴀᴍᴇs ᴀɢᴀɪɴ.", parse_mode="HTML")


async def cmd_cancelgames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user

    if user.id != OWNER_ID:
        return await msg.reply_text("❌ Oᴡɴᴇʀ Oɴʟʏ.")
    if not active_games:
        return await msg.reply_text("✅ Nᴏ Aᴄᴛɪᴠᴇ Gᴀᴍᴇs Rɪɢʜᴛ Nᴏᴡ.")

    games_cancelled = 0
    for chat_id, game in list(active_games.items()):
        for task_key in ("join_task", "remind_task"):
            t = game.get(task_key)
            if t:
                t.cancel()

        bet = game["bet"]
        players = game["players"]
        for uid in players:
            u = users.find_one({"id": uid})
            if u:
                u["coins"] = u.get("coins", 0) + bet
                save_user(u)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="🛑 <b>Cᴀʀᴅ Gᴀᴍᴇ Sᴛᴏᴘᴘᴇᴅ Gʟᴏʙᴀʟʟʏ</b>\n\n💸 <b>Aʟʟ Cᴀʀᴅ Aᴍᴏᴜɴᴛs Hᴀᴠᴇ Bᴇᴇɴ Rᴇꜰᴜɴᴅᴇᴅ.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

        await _delete_tracked(context, game)
        games_cancelled += 1
        active_games.pop(chat_id, None)

    await msg.reply_text(
        f"✅ <b>Gʟᴏʙᴀʟ Cᴀɴᴄᴇʟ Sᴜᴄᴄᴇssꜰᴜʟ</b>\n\n♠️ <b>Cᴀʀᴅ Gʀᴏᴜᴘs Cʟᴇᴀʀᴇᴅ:</b> <code>{games_cancelled}</code>",
        parse_mode="HTML"
    )


async def cmd_topcarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    top_list = list(users.find(
        {"card_wins_total": {"$exists": True, "$gt": 0}},
        {"id": 1, "name": 1, "card_wins_total": 1, "card_streak": 1, "custom_icon": 1, "premium": 1}
    ).sort("card_wins_total", -1).limit(10))

    if not top_list:
        return await msg.reply_text(f"📭 {sc('No card game winners yet.')}", parse_mode="HTML")

    def build_text(show_streak: bool) -> str:
        header = ("♠️ <b>Tᴏᴘ 10 Cᴀʀᴅ Gᴀᴍᴇ Pʟᴀʏᴇʀs — Sᴛʀᴇᴀᴋs</b> ♠️\n\n" if show_streak
                  else "♠️ <b>Tᴏᴘ 10 Cᴀʀᴅ Gᴀᴍᴇ Pʟᴀʏᴇʀs</b> ♠️\n\n")
        lines = ""
        for i, u in enumerate(top_list, start=1):
            user_id = u.get("id")
            safe_name = html.escape(str(u.get("name", "Unknown")))
            clickable = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
            total_won = u.get("card_wins_total", 0)
            streak = u.get("card_streak", 0)
            custom_icon = u.get("custom_icon", "").strip()
            is_prem = u.get("premium", False)
            icon = custom_icon if custom_icon else ("💓" if is_prem else "👤")
            if show_streak:
                lines += f"<b>{i}.</b> {icon} {clickable}\n     🔥 {sc('Streak')}: <b>{streak}</b>\n\n"
            else:
                lines += f"<b>{i}.</b> {icon} {clickable} — <code>{total_won:,}</code> 💰\n"
        footer = "\n\n✨ = Cᴜsᴛᴏᴍ • 💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ\n<i>♠️ Pʟᴀʏ ᴍᴏʀᴇ ᴡɪᴛʜ /card &lt;ᴀᴍᴏᴜɴᴛ&gt;</i>"
        return header + lines + footer

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔥 " + sc("View Streaks"), callback_data="topcarder_streak"),
        InlineKeyboardButton("💰 " + sc("View Earnings"), callback_data="topcarder_earnings"),
    ]])
    await msg.reply_text(build_text(show_streak=False), parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def cb_topcarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    top_list = list(users.find(
        {"card_wins_total": {"$exists": True, "$gt": 0}},
        {"id": 1, "name": 1, "card_wins_total": 1, "card_streak": 1, "custom_icon": 1, "premium": 1}
    ).sort("card_wins_total", -1).limit(10))

    if not top_list:
        return await query.edit_message_text(f"📭 {sc('No card game winners yet.')}", parse_mode="HTML")

    show_streak = query.data == "topcarder_streak"
    header = ("♠️ <b>Tᴏᴘ 10 Cᴀʀᴅ Gᴀᴍᴇ Pʟᴀʏᴇʀs — Sᴛʀᴇᴀᴋs</b> ♠️\n\n" if show_streak
              else "♠️ <b>Tᴏᴘ 10 Cᴀʀᴅ Gᴀᴍᴇ Pʟᴀʏᴇʀs</b> ♠️\n\n")
    lines = ""
    for i, u in enumerate(top_list, start=1):
        user_id = u.get("id")
        safe_name = html.escape(str(u.get("name", "Unknown")))
        clickable = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
        total_won = u.get("card_wins_total", 0)
        streak = u.get("card_streak", 0)
        custom_icon = u.get("custom_icon", "").strip()
        is_prem = u.get("premium", False)
        icon = custom_icon if custom_icon else ("💓" if is_prem else "👤")
        if show_streak:
            lines += f"<b>{i}.</b> {icon} {clickable}\n     🔥 {sc('Streak')}: <b>{streak}</b>\n\n"
        else:
            lines += f"<b>{i}.</b> {icon} {clickable} — <code>{total_won:,}</code> 💰\n"

    footer = "\n\n✨ = Cᴜsᴛᴏᴍ • 💓 = Pʀᴇᴍɪᴜᴍ • 👤 = Nᴏʀᴍᴀʟ\n<i>♠️ Pʟᴀʏ ᴍᴏʀᴇ ᴡɪᴛʜ /card &lt;ᴀᴍᴏᴜɴᴛ&gt;</i>"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔥 " + sc("View Streaks"), callback_data="topcarder_streak"),
        InlineKeyboardButton("💰 " + sc("View Earnings"), callback_data="topcarder_earnings"),
    ]])
    await query.edit_message_text(header + lines + footer, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def cmd_activecards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user

    if user.id != OWNER_ID:
        return await msg.reply_text("❌ Oᴡɴᴇʀ Oɴʟʏ.")
    if not active_games:
        return await msg.reply_text("✅ <b>Nᴏ Aᴄᴛɪᴠᴇ Cᴀʀᴅ Gᴀᴍᴇs Rɪɢʜᴛ Nᴏᴡ.</b>", parse_mode="HTML")

    text = "♠️ <b>Aᴄᴛɪᴠᴇ Cᴀʀᴅ Gᴀᴍᴇs</b> ♠️\n\n"
    count = 0
    for chat_id, game in active_games.items():
        count += 1
        phase = game.get("phase", "unknown")
        bet = game.get("bet", 0)
        players = game.get("players", {})
        rnd = game.get("round", 1)
        host_id = game.get("host_id")
        inv_mode = "🔒 " + sc("Invite") if game.get("invite_mode") else "🌐 " + sc("Open")

        try:
            chat_obj = await context.bot.get_chat(chat_id)
            group_name = html.escape(chat_obj.title or str(chat_id))
        except Exception:
            group_name = str(chat_id)

        host_name = "Unknown"
        if host_id and host_id in players:
            host_name = html.escape(players[host_id].get("name", "Unknown"))

        player_names = [html.escape(p.get("name", "?")) for p in players.values()]
        shown = player_names[:5]
        extra = len(player_names) - 5
        players_line = ", ".join(shown)
        if extra > 0:
            players_line += f" +{extra} {sc('more')}"

        phase_icon = {"joining": "⏳", "playing": "🎮", "done": "✅"}.get(phase, "❓")

        text += (
            f"{count}. 🏠 <b>{group_name}</b>\n    🆔 <code>{chat_id}</code>\n"
            f"    {phase_icon} {sc('Phase')}: <b>{phase.upper()}</b>\n    {inv_mode}\n"
            f"    💰 {sc('Bet')}: <b>{bet:,}</b>\n    👥 {sc('Players')} ({len(players)}): {players_line}\n"
            f"    🔄 {sc('Round')}: <b>{rnd}/{MAX_ROUNDS}</b>\n    👑 {sc('Host')}: <b>{host_name}</b>\n\n"
        )

    text += f"📊 {sc('Total Active Games')}: <b>{count}</b>"
    await msg.reply_text(text, parse_mode=ParseMode.HTML)


# ============================ INVITE GAME (/card2../5) ============================

async def _start_invite_game(update: Update, context: ContextTypes.DEFAULT_TYPE, max_players: int, target_user=None):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    chat_id = chat.id

    if chat.type == "private":
        return await msg.reply_text(sc("Group only."))
    if is_card_locked(chat_id):
        return await msg.reply_text("🔒 <b>Cᴀʀᴅ Gᴀᴍᴇ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Lᴏᴄᴋᴇᴅ.</b>", parse_mode="HTML")
    if chat_id in active_games and active_games[chat_id]["phase"] != "done":
        return await msg.reply_text(f"🚫 {sc('Game already running.')}")

    if not context.args:
        usage_extra = f" &lt;@{sc('username or id')}&gt;" if max_players == 2 else ""
        return await msg.reply_text(f"<b>{sc('Usage')}:</b> /card{max_players} &lt;{sc('amount')}&gt;{usage_extra}", parse_mode="HTML")

    try:
        bet = int(context.args[0])
    except ValueError:
        return await msg.reply_text(sc("Invalid amount."))
    if bet <= MIN_BET:
        return await msg.reply_text(f"⚠️ {sc('Min bet is')} {MIN_BET}.")

    host_data = get_user(user)
    if not host_data or host_data.get("coins", 0) < bet:
        return await msg.reply_text(sc("Insufficient coins."))

    host_data["coins"] -= bet
    save_user(host_data)

    game = {
        "host_id": user.id, "bet": bet, "max_players": max_players,
        "players": {user.id: {"name": user.first_name, "cards": {}, "points": 0, "_point_noise": 0,
                               "premium": is_premium(host_data, context), "dm_msg_id": None}},
        "round": 1, "turn_order": [], "current_turn": 0, "round_plays": {}, "phase": "joining",
        "join_task": None, "remind_task": None, "tracked_msgs": [], "invite_mode": True,
    }
    active_games[chat_id] = game
    game["tracked_msgs"].append((chat_id, msg.message_id))

    if max_players == 2 and target_user:
        target_data = get_user(target_user)
        if not target_data or target_data.get("coins", 0) < bet:
            host_data["coins"] += bet
            save_user(host_data)
            active_games.pop(chat_id, None)
            return await msg.reply_text(
                f"❌ <b>{html.escape(target_user.first_name)}</b> {sc('does not have enough coins.')}", parse_mode="HTML"
            )

        target_data["coins"] -= bet
        save_user(target_data)
        game["players"][target_user.id] = {"name": target_user.first_name, "cards": {}, "points": 0, "_point_noise": 0,
                                            "premium": is_premium(target_data, context), "dm_msg_id": None}

        sent = await msg.reply_text(
            f"♠️ <b>{sc('Private 1v1 Card Game!')}</b>\n\n👥 <b>{html.escape(user.first_name)}</b> ᴠs <b>{html.escape(target_user.first_name)}</b>\n"
            f"💰 {sc('Bet')}: <b>{bet:,}</b>\n\n🃏 {sc('Starting now...')}",
            parse_mode="HTML"
        )
        _track_bot_msg(game, chat_id, sent)

        try:
            await context.bot.send_message(
                chat_id=target_user.id,
                text=(f"♠️ <b>{sc('You have been invited to a card game!')}</b>\n\n👑 {sc('Host')}: <b>{html.escape(user.first_name)}</b>\n"
                      f"💰 <b>{bet:,}</b> {sc('coins deducted from your balance.')}\n\n🃏 {sc('Game is starting in the group!')}"),
                parse_mode="HTML"
            )
        except Exception:
            pass

        await asyncio.sleep(1)
        await _launch_game(context, chat_id)
        return

    need = max_players - 1
    sent = await msg.reply_text(
        f"♠️ <b>{sc('Private Card Game Created!')}</b>\n\n💰 {sc('Bet')}: <b>{bet:,}</b>\n"
        f"👥 {sc('Need')}: <b>{need}</b> {sc('more players')}\n\n📩 {sc('Check your DM — send me the usernames!')}",
        parse_mode="HTML"
    )
    _track_bot_msg(game, chat_id, sent)

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=(f"♠️ <b>{sc('Card Game Setup')}</b>\n\n📝 {sc('Send me')} <b>{need}</b> {sc('usernames or user IDs')}\n"
                  f"{sc('space-separated or one per line.')}\n\n💡 {sc('Example')}:\n<code>@player1 @player2</code>\n\n"
                  f"⏳ {sc('You have 60 seconds.')}"),
            parse_mode="HTML"
        )
        context.bot_data.setdefault("pending_invite", {})[user.id] = {
            "chat_id": chat_id, "need": need, "expires_at": asyncio.get_event_loop().time() + 60,
        }
        asyncio.create_task(_invite_dm_timeout(context, user.id, chat_id))
    except Exception:
        host_data["coins"] += bet
        save_user(host_data)
        active_games.pop(chat_id, None)
        await msg.reply_text("❌ {} ".format(sc("Please start the bot in DM first, then try again.")), parse_mode="HTML")


async def _invite_dm_timeout(context, host_uid: int, chat_id: int):
    await asyncio.sleep(62)
    pending = context.bot_data.get("pending_invite", {})
    if host_uid not in pending:
        return
    pending.pop(host_uid, None)

    game = active_games.get(chat_id)
    if game:
        bet = game["bet"]
        for uid in game["players"]:
            u = users.find_one({"id": uid})
            if u:
                u["coins"] = u.get("coins", 0) + bet
                save_user(u)
        active_games.pop(chat_id, None)

    try:
        await context.bot.send_message(chat_id=host_uid, text=f"⏰ <b>{sc('Invite setup timed out. Game cancelled and coins refunded.')}</b>", parse_mode="HTML")
    except Exception:
        pass


async def handle_invite_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import re
    user = update.effective_user
    msg = update.message
    chat = update.effective_chat

    if chat.type != "private":
        return

    pending = context.bot_data.get("pending_invite", {})
    if user.id not in pending:
        return

    state = pending[user.id]
    chat_id = state["chat_id"]
    need = state["need"]
    game = active_games.get(chat_id)

    if not game:
        pending.pop(user.id, None)
        return

    bet = game["bet"]
    raw_text = msg.text or ""
    mentions = re.findall(r'@(\w+)', raw_text)
    raw_ids = re.findall(r'\b(\d{5,12})\b', raw_text)
    resolved = []

    for username in mentions:
        try:
            chat_obj = await context.bot.get_chat(f"@{username}")
            resolved.append(chat_obj)
        except Exception:
            await msg.reply_text(f"❌ {sc('Could not find')} @{username}. {sc('Skipping.')}", parse_mode="HTML")

    for uid_str in raw_ids:
        try:
            chat_obj = await context.bot.get_chat(int(uid_str))
            resolved.append(chat_obj)
        except Exception:
            await msg.reply_text(f"❌ {sc('Could not find ID')} {uid_str}. {sc('Skipping.')}", parse_mode="HTML")

    added = 0
    for target in resolved:
        if target.id == user.id or target.id in game["players"] or len(game["players"]) >= need + 1:
            continue

        target_data = users.find_one({"id": target.id})
        if not target_data or target_data.get("coins", 0) < bet:
            await msg.reply_text(f"❌ <b>{html.escape(target.first_name)}</b> {sc('not enough coins. Skipping.')}", parse_mode="HTML")
            continue

        target_data["coins"] -= bet
        save_user(target_data)
        game["players"][target.id] = {"name": target.first_name, "cards": {}, "points": 0, "_point_noise": 0,
                                       "premium": is_premium(target_data, context), "dm_msg_id": None}
        added += 1

        try:
            await context.bot.send_message(
                chat_id=target.id,
                text=(f"♠️ <b>{sc('You have been invited to a card game!')}</b>\n\n👑 {sc('Host')}: <b>{html.escape(user.first_name)}</b>\n"
                      f"💰 <b>{bet:,}</b> {sc('coins deducted from your balance.')}\n\n🃏 {sc('Game is starting in the group!')}"),
                parse_mode="HTML"
            )
        except Exception:
            pass

    total_players = len(game["players"])
    still_need = (need + 1) - total_players

    if still_need <= 0:
        pending.pop(user.id, None)
        await msg.reply_text(f"✅ <b>{sc('All players added! Starting game...')}</b>", parse_mode="HTML")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(f"♠️ <b>{sc('Private Card Game Starting!')}</b>\n\n👥 {sc('Players')}: <b>{total_players}</b>\n💰 {sc('Bet')}: <b>{bet:,}</b>"),
                parse_mode="HTML"
            )
        except Exception:
            pass
        await _launch_game(context, chat_id)
    else:
        await msg.reply_text(
            f"✅ <b>{added}</b> {sc('player(s) added.')}\n📝 {sc('Still need')} <b>{still_need}</b> {sc('more. Send their usernames.')}",
            parse_mode="HTML"
        )


async def cmd_card2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args or []) < 2:
        return await update.message.reply_text(f"<b>{sc('Usage')}:</b> /card2 &lt;{sc('amount')}&gt; &lt;@{sc('username or id')}&gt;", parse_mode="HTML")

    target_raw = context.args[1].lstrip("@")
    try:
        target_obj = await context.bot.get_chat(int(target_raw))
    except ValueError:
        try:
            target_obj = await context.bot.get_chat(f"@{target_raw}")
        except Exception:
            return await update.message.reply_text(f"❌ {sc('Could not find that user.')}", parse_mode="HTML")
    except Exception:
        return await update.message.reply_text(f"❌ {sc('Could not find that user.')}", parse_mode="HTML")

    await _start_invite_game(update, context, max_players=2, target_user=target_obj)


async def cmd_card3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _start_invite_game(update, context, max_players=3)


async def cmd_card4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _start_invite_game(update, context, max_players=4)


async def cmd_card5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _start_invite_game(update, context, max_players=5)
