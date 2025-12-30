import asyncio
from collections import defaultdict
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Store grouped uploads temporarily
movie_updates = defaultdict(lambda: {"title": None, "media_type": None, "poster": None, "qualities": []})
pending_posts = {}

async def schedule_post(bot, tmdb_id):
    await asyncio.sleep(10)  # buffer time to collect all qualities
    info = movie_updates[tmdb_id]

    if not info["qualities"]:
        return

    # Build caption
    if info["media_type"] == "tv":
        post_url = f"https://hari-moviez.vercel.app/ser/{tmdb_id}"
        caption = (
            f"📺 **New Series Upload:** {info['title']}\n"
            f"🔗 Choose your quality below 👇"
        )
    else:
        post_url = f"https://hari-moviez.vercel.app/mov/{tmdb_id}"
        caption = (
            f"🎬 **New Movie Upload:** {info['title']}\n"
            f"🔗 Choose your quality below 👇"
        )

    # Buttons: qualities + main post
    btn = [info["qualities"]]
    btn.append([InlineKeyboardButton("📌 Open Post", url=post_url)])

    # Send poster if available
    if info["poster"]:
        await bot.send_photo(
            chat_id=Telegram.UPDATE_CHANNEL,
            photo=info["poster"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(btn)
        )
    else:
        await bot.send_message(
            chat_id=Telegram.UPDATE_CHANNEL,
            text=caption,
            reply_markup=InlineKeyboardMarkup(btn),
            disable_web_page_preview=True
        )

    # Clear after posting
    movie_updates.pop(tmdb_id, None)
    pending_posts.pop(tmdb_id, None)

@Client.on_message(filters.channel & filters.chat(Telegram.AUTH_CHANNEL))
async def file_receive_handler(bot: Client, message: Message):
    file = message.video or message.document
    title = message.caption if (Telegram.USE_CAPTION and message.caption) else file.file_name or file.file_id
    size = get_readable_file_size(file.file_size)

    metadata_info = await metadata(clean_filename(title), file)
    if metadata_info is None:
        return

    tmdb_id = metadata_info.get("tmdb_id")
    media_type = metadata_info.get("media_type", "movie")
    quality = metadata_info.get("quality", "Unknown")
    poster = metadata_info.get("poster", None)

    # Group qualities
    movie_updates[tmdb_id]["title"] = metadata_info.get("title", title)
    movie_updates[tmdb_id]["media_type"] = media_type
    movie_updates[tmdb_id]["poster"] = poster

    if media_type == "tv":
        quality_url = f"https://hari-moviez.vercel.app/ser/{tmdb_id}?q={quality}"
    else:
        quality_url = f"https://hari-moviez.vercel.app/mov/{tmdb_id}?q={quality}"

    movie_updates[tmdb_id]["qualities"].append(
        InlineKeyboardButton(f"{quality} ({size})", url=quality_url)
    )

    # Schedule post if not already pending
    if tmdb_id not in pending_posts:
        pending_posts[tmdb_id] = asyncio.create_task(schedule_post(bot, tmdb_id))
