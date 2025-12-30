import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import FloodWait
from Backend.config import Telegram
from Backend.helper.utils import clean_filename
from Backend.helper.metadata import metadata

# Temporary stores
movie_updates = {}
pending_posts = {}

async def schedule_post(bot, tmdb_id):
    await asyncio.sleep(Telegram.POST_DELAY)  # configurable delay
    info = movie_updates.get(tmdb_id)
    if not info:
        return

    # Build caption with quotes and rich metadata
    if info["media_type"] == "tv":
        post_url = f"https://hari-moviez.vercel.app/ser/{tmdb_id}"
        caption = (
            f"\"📺 {info['title']}\n"
            f"🗓️ Season {info.get('season_number')} Episode {info.get('episode_number')}\n"
            f"📅 Release Year: {info.get('year')}\n"
            f"⭐ Rating: {info.get('rate')}/10\n"
            f"🎭 Genres: {', '.join(info.get('genres', []))}\n"
            f"🌐 Languages: {', '.join(info.get('languages', []))}\n\n"
            f"📝 Plot: {info.get('description')}\n\n"
            f"🔗 [Open Post]({post_url})\""
        )
    else:
        post_url = f"https://hari-moviez.vercel.app/mov/{tmdb_id}"
        caption = (
            f"\"🎬 {info['title']}\n"
            f"📅 Release Year: {info.get('year')}\n"
            f"⭐ Rating: {info.get('rate')}/10\n"
            f"🎭 Genres: {', '.join(info.get('genres', []))}\n"
            f"🌐 Languages: {', '.join(info.get('languages', []))}\n\n"
            f"📝 Plot: {info.get('description')}\n\n"
            f"🔗 [Open Post]({post_url})\""
        )

    # Send poster if available
    if info.get("poster"):
        await bot.send_photo(
            chat_id=Telegram.UPDATE_CHANNEL,
            photo=info["poster"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📌 Open Post", url=post_url)]]
            )
        )
    else:
        await bot.send_message(
            chat_id=Telegram.UPDATE_CHANNEL,
            text=caption,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📌 Open Post", url=post_url)]]
            ),
            disable_web_page_preview=True
        )

    # Clear after posting
    movie_updates.pop(tmdb_id, None)
    pending_posts.pop(tmdb_id, None)

@Client.on_message(filters.channel & filters.chat(Telegram.AUTH_CHANNEL))
async def file_receive_handler(bot: Client, message: Message):
    try:
        file = message.video or message.document
        title = message.caption if (Telegram.USE_CAPTION and message.caption) else file.file_name or file.file_id

        metadata_info = await metadata(clean_filename(title), file)
        if metadata_info is None:
            return

        tmdb_id = metadata_info.get("tmdb_id")
        media_type = metadata_info.get("media_type", "movie")
        poster = metadata_info.get("poster", None)

        # Store info for grouping
        movie_updates[tmdb_id] = {
            "title": metadata_info.get("title", title),
            "media_type": media_type,
            "poster": poster,
            "season_number": metadata_info.get("season_number"),
            "episode_number": metadata_info.get("episode_number"),
            "year": metadata_info.get("year"),
            "rate": metadata_info.get("rate"),
            "genres": metadata_info.get("genres", []),
            "languages": metadata_info.get("languages", []),
            "description": metadata_info.get("description", "")
        }

        # Schedule post if not already pending
        if tmdb_id not in pending_posts:
            pending_posts[tmdb_id] = asyncio.create_task(schedule_post(bot, tmdb_id))

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply_text(f"Got Floodwait of {e.value}s")
