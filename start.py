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
