import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from Backend.logger import LOGGER
from Backend.config import Telegram
from Backend.utils import get_readable_file_size, clean_filename, remove_urls, metadata
from Backend.queue import file_queue

@StreamBot.on_message(filters.chat(Telegram.AUTH_CHANNEL) & (filters.document | filters.video))
async def file_receive_handler(bot: Client, message: Message):
    if str(message.chat.id) in Telegram.AUTH_CHANNEL:
        try:
            if message.video or message.document:
                file = message.video or message.document

                # Title handling
                if Telegram.USE_CAPTION and message.caption:
                    title = message.caption.replace("\n", "\\n")
                else:
                    title = file.file_name or file.file_id

                msg_id = message.id
                hash = file.file_unique_id[:6]
                size = get_readable_file_size(file.file_size)
                channel = str(message.chat.id).replace("-100", "")

                # Metadata lookup
                metadata_info = await metadata(clean_filename(title), file)
                if metadata_info is None:
                    return

                # Queue for DB/website indexing
                title = remove_urls(title)
                if not title.endswith('.mkv'):
                    title += '.mkv'
                await file_queue.put((metadata_info, hash, int(channel), msg_id, size, title))

                # --- NEW: Post in FORCE_SUB_CHANNEL with redirect button ---
                tmdb_id = metadata_info.get("id")  # adjust if your metadata returns tmdb_id differently
                for fsub_channel in Telegram.FORCE_SUB_CHANNEL:
                    buttons = InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔗 Get Link", url=f"https://hkspot-k66q4fh4n-kushals-projects-dc9c420d.vercel.app/id/{tmdb_id}")]]
                    )

                    await bot.send_message(
                        chat_id=fsub_channel,
                        text=(
                            f"🎬 **New Movie Uploaded!**\n\n"
                            f"📌 Title: {message.caption or file.file_name}\n"
                            f"📥 Size: {size}"
                        ),
                        reply_markup=buttons,
                        disable_web_page_preview=True
                    )

            else:
                await message.reply_text("Not supported")

        except FloodWait as e:
            LOGGER.info(f"Sleeping for {str(e.value)}s")
            await asyncio.sleep(e.value)
            await message.reply_text(
                text=f"Got Floodwait of {str(e.value)}s",
                disable_web_page_preview=True
            )
    else:
        await message.reply_text("Channel is not in AUTH_CHANNEL")



import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import FloodWait

class Telegram:
    AUTH_CHANNEL = ["-1001234567890"]   # replace with your AUTH channel ID(s)
    UPDATE_CHANNEL = -1009876543210     # replace with your update channel ID
    USE_CAPTION = True

# ---------------- /start Handler ----------------
@StreamBot.on_message(filters.command('start') & filters.private)
async def start(bot: Client, message: Message):
    LOGGER.info(f"Received command: {message.text}")

    if " " not in message.text:
        # Plain /start → welcome
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
    parts = usr_cmd.split("_")

    try:
        if len(parts) == 2:
            tmdb_id, quality = parts
            tmdb_id = int(tmdb_id)
            quality_details = await db.get_quality_details(tmdb_id, quality)

        elif len(parts) == 3:
            tmdb_id, season, quality = parts
            tmdb_id = int(tmdb_id)
            season = int(season)
            quality_details = await db.get_quality_details(tmdb_id, quality, season)

        elif len(parts) == 4:
            tmdb_id, season, episode, quality = parts
            tmdb_id = int(tmdb_id)
            season = int(season)
            episode = int(episode)
            quality_details = await db.get_quality_details(tmdb_id, quality, season, episode)

        else:
            await message.reply_text("Invalid command format.")
            return
    except ValueError:
        await message.reply_text("Invalid command format.")
        return

    sent_messages = []
    for detail in quality_details:
        decoded_data = await decode_string(detail['id'])
        channel = f"-100{decoded_data['chat_id']}"
        msg_id = decoded_data['msg_id']
        name = detail['name']
        if "\\n" in name and name.endswith(".mkv"):
            name = name.rsplit(".mkv", 1)[0].replace("\\n", "\n")
        try:
            file = await bot.get_messages(int(channel), int(msg_id))
            media = file.document or file.video
            if media:
                sent_msg = await message.reply_cached_media(
                    file_id=media.file_id,
                    caption=f'{name}'
                )
                sent_messages.append(sent_msg)
                await asleep(1)
        except FloodWait as e:
            LOGGER.info(f"Sleeping for {e.value}s")
            await asleep(e.value)
            await message.reply_text(f"Got Floodwait of {e.value}s")
        except Exception as e:
            LOGGER.error(f"Error retrieving/sending media: {e}")
            await message.reply_text("Error retrieving media.")

    if sent_messages:
        warning_msg = await message.reply_text(
            "Forward these files to your saved messages. These files will be deleted from the bot within 5 minutes."
        )
        sent_messages.append(warning_msg)
        create_task(delete_messages_after_delay(sent_messages))


# ---------------- AUTH_CHANNEL Listener ----------------
@StreamBot.on_message(filters.channel & filters.chat(Telegram.AUTH_CHANNEL))
async def file_receive_handler(bot: Client, message: Message):
    try:
        if message.video or message.document:
            file = message.video or message.document
            if Telegram.USE_CAPTION and message.caption:
                title = message.caption.replace("\n", "\\n")
            else:
                title = file.file_name or file.file_id

            msg_id = message.id
            hash = file.file_unique_id[:6]
            size = get_readable_file_size(file.file_size)
            channel = str(message.chat.id).replace("-100","")

            metadata_info = await metadata(clean_filename(title), file)
            if metadata_info is None:
                return

            # Queue file
            title = remove_urls(title)
            if not title.endswith('.mkv'):
                title += '.mkv'
            await file_queue.put((metadata_info, hash, int(channel), msg_id, size, title))

            # 🔔 Announce in UPDATE_CHANNEL
            tmdb_id = metadata_info.get("id")
            media_type = metadata_info.get("media_type", "movie")

            if media_type == "tv":
                post_url = f"https://hari-moviez.vercel.app/ser/{tmdb_id}"
            else:
                post_url = f"https://hari-moviez.vercel.app/mov/{tmdb_id}"

            caption = (
                f"🎬 **New Upload:** {metadata_info.get('title', title)}\n"
                f"📦 Size: {size}\n\n"
                f"🔗 [View Post]({post_url})"
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
        LOGGER.info(f"Sleeping for {str(e.value)}s")
        await asleep(e.value)
        await message.reply_text(
            text=f"Got Floodwait of {str(e.value)}s",
            disable_web_page_preview=True,
            parse_mode="markdown"
        )
