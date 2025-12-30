import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import FloodWait

from Backend.config import Telegram
from Backend.helper.mediainfo import get_readable_file_size
from Backend.helper.utils import clean_filename, remove_urls
from Backend.helper.queue import file_queue
from Backend.helper.metadata import metadata  # your existing metadata function

# ---------------- /start Handler ----------------
@Client.on_message(filters.command('start') & filters.private)
async def start(bot: Client, message: Message):
    if " " not in message.text:
        await message.reply_text(
            "👋 Welcome! I provide direct download links for movies & series from https://hari-moviez.vercel.app 📥\n"
            "Just send a file link to get started!"
        )
        return

    command_part = message.text.split('start ')[-1]
    if command_part.startswith("file_"):
        usr_cmd = command_part[len("file_"):].strip()
        await send_file(bot, message, usr_cmd)

# ---------------- File Sending Logic ----------------
async def send_file(bot: Client, message: Message, usr_cmd: str):
    # your existing deep-link file sending logic here
    # unchanged, since the issue was only in update channel posting
    pass

# ---------------- AUTH_CHANNEL Listener ----------------
@Client.on_message(filters.channel & filters.chat(Telegram.AUTH_CHANNEL))
async def file_receive_handler(bot: Client, message: Message):
    try:
        if message.video or message.document:
            file = message.video or message.document
            if Telegram.USE_CAPTION and message.caption:
                title = message.caption.replace("\n", "\\n")
            else:
                title = file.file_name or file.file_id

            msg_id = message.id
            size = get_readable_file_size(file.file_size)

            # 🔎 Fetch metadata (your existing function)
            metadata_info = await metadata(clean_filename(title), file)
            if metadata_info is None:
                return

            # Queue file for backend processing
            title = remove_urls(title)
            if not title.endswith('.mkv'):
                title += '.mkv'
            await file_queue.put((metadata_info, file.file_unique_id[:6], int(str(message.chat.id).replace("-100","")), msg_id, size, title))

            # 🔔 Announce in UPDATE_CHANNEL
            tmdb_id = metadata_info.get("tmdb_id")  # ✅ use tmdb_id, not id
            media_type = metadata_info.get("media_type", "movie")

            if media_type == "tv":
                post_url = f"https://hari-moviez.vercel.app/ser/{tmdb_id}"
                caption = (
                    f"📺 **New Series Upload:** {metadata_info.get('title', title)}\n"
                    f"🗓️ Season {metadata_info.get('season_number')} Episode {metadata_info.get('episode_number')}\n"
                    f"📦 Quality: {metadata_info.get('quality')}\n"
                    f"🔗 [View Episode]({post_url})"
                )
            else:
                post_url = f"https://hari-moviez.vercel.app/mov/{tmdb_id}"
                caption = (
                    f"🎬 **New Movie Upload:** {metadata_info.get('title', title)}\n"
                    f"📦 Size: {size}\n"
                    f"📦 Quality: {metadata_info.get('quality')}\n"
                    f"🔗 [View Movie]({post_url})"
                )

            btn = [[InlineKeyboardButton("🔗 Open Post", url=post_url)]]

            await bot.send_message(
                chat_id=Telegram.UPDATE_CHANNEL,
                text=caption,
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True
            )

        else:
            await message.reply_text("Not supported")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply_text(
            text=f"Got Floodwait of {str(e.value)}s",
            disable_web_page_preview=True,
            parse_mode="markdown"
          )
