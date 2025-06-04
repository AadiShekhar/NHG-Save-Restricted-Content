# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import asyncio 
import pyrogram
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message 
from config import API_ID, API_HASH, ERROR_MESSAGE
from database.db import db
from TechVJ.strings import HELP_TXT
import shutil
from datetime import datetime
import re
from typing import List, Dict, Optional

# Constants
MAX_PARALLEL_DOWNLOADS = 5  # Number of simultaneous downloads
DOWNLOAD_TIMEOUT = 300  # 5 minutes timeout per download
STATUS_UPDATE_INTERVAL = 5  # Seconds between status updates

# Create downloads directory
DOWNLOADS_DIR = "downloads"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

class BatchStatus:
    def __init__(self):
        self.active_batches: Dict[int, bool] = {}
        self.download_tasks: Dict[int, List[asyncio.Task]] = {}
        self.status_messages: Dict[int, Message] = {}
        self.progress: Dict[int, Dict[str, float]] = {}

    def is_batch_active(self, user_id: int) -> bool:
        return self.active_batches.get(user_id, True)
    
    def set_batch_status(self, user_id: int, status: bool):
        self.active_batches[user_id] = status
        
    def add_download_task(self, user_id: int, task: asyncio.Task):
        if user_id not in self.download_tasks:
            self.download_tasks[user_id] = []
        self.download_tasks[user_id].append(task)
        
    def cancel_all_tasks(self, user_id: int):
        if user_id in self.download_tasks:
            for task in self.download_tasks[user_id]:
                task.cancel()
            self.download_tasks[user_id] = []
            
    def update_progress(self, user_id: int, msg_id: int, progress: float):
        if user_id not in self.progress:
            self.progress[user_id] = {}
        self.progress[user_id][msg_id] = progress
        
    def get_progress(self, user_id: int) -> Dict[int, float]:
        return self.progress.get(user_id, {})

batch_status = BatchStatus()

async def download_status_updater(client: Client, user_id: int, chat_id: int):
    while not batch_status.is_batch_active(user_id) and user_id in batch_status.status_messages:
        progress = batch_status.get_progress(user_id)
        if progress:
            status_text = "**Download Progress:**\n\n"
            for msg_id, percent in progress.items():
                status_text += f"• Message {msg_id}: {percent:.1f}%\n"
            
            try:
                await batch_status.status_messages[user_id].edit_text(status_text)
            except:
                pass
        
        await asyncio.sleep(STATUS_UPDATE_INTERVAL)

def clean_filename(text: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", text).strip()

def get_file_info(msg: pyrogram.types.Message, msgid: int) -> Dict[str, str]:
    file_info = {"ext": "", "name": "", "original": ""}
    
    if msg.document:
        file_info["ext"] = os.path.splitext(msg.document.file_name or "")[1] or ".bin"
        file_info["original"] = msg.document.file_name or f"document_{msgid}{file_info['ext']}"
        file_info["name"] = clean_filename(f"{msgid}_{file_info['original']}")
    elif msg.video:
        file_info["ext"] = ".mp4"
        file_info["original"] = msg.video.file_name or f"video_{msgid}.mp4"
        file_info["name"] = clean_filename(f"{msgid}_{file_info['original']}")
    elif msg.audio:
        file_info["ext"] = ".mp3"
        if msg.audio.title and msg.audio.performer:
            title = clean_filename(msg.audio.title)
            artist = clean_filename(msg.audio.performer)
            file_info["original"] = f"{artist} - {title}.mp3"
        else:
            file_info["original"] = msg.audio.file_name or f"audio_{msgid}.mp3"
        file_info["name"] = clean_filename(f"{msgid}_{file_info['original']}")
    elif msg.voice:
        file_info["ext"] = ".ogg"
        file_info["original"] = f"voice_message_{msgid}.ogg"
        file_info["name"] = f"{msgid}_voice.ogg"
    elif msg.photo:
        file_info["ext"] = ".jpg"
        file_info["original"] = f"photo_{msgid}.jpg"
        file_info["name"] = f"{msgid}_photo.jpg"
    elif msg.sticker:
        file_info["ext"] = ".webp" if not msg.sticker.is_animated else ".tgs"
        file_info["original"] = f"sticker_{msgid}{file_info['ext']}"
        file_info["name"] = f"{msgid}_sticker{file_info['ext']}"
    elif msg.animation:
        file_info["ext"] = ".gif"
        file_info["original"] = msg.animation.file_name or f"animation_{msgid}.gif"
        file_info["name"] = clean_filename(f"{msgid}_{file_info['original']}")
    elif msg.video_note:
        file_info["ext"] = ".mp4"
        file_info["original"] = f"video_note_{msgid}.mp4"
        file_info["name"] = f"{msgid}_video_note.mp4"
    
    if not file_info["ext"]:
        file_info["ext"] = ".bin"
        file_info["original"] = f"file_{msgid}.bin"
        file_info["name"] = f"{msgid}_file.bin"
    
    return file_info

def get_message_type(msg: pyrogram.types.Message) -> str:
    if msg.document: return "Document"
    if msg.video: return "Video"
    if msg.animation: return "Animation"
    if msg.sticker: return "Sticker"
    if msg.voice: return "Voice"
    if msg.audio: return "Audio"
    if msg.photo: return "Photo"
    if msg.video_note: return "Video Note"
    if msg.text: return "Text"
    return "Unknown"

async def download_file(
    client: Client,
    acc: Client,
    message: Message,
    chat_id: int,
    msg_id: int,
    user_id: int
) -> Optional[Dict[str, str]]:
    try:
        msg = await acc.get_messages(chat_id, msg_id)
        if msg.empty:
            return None

        msg_type = get_message_type(msg)
        if not msg_type or msg_type == "Unknown":
            return None

        if msg_type == "Text":
            text_filename = f"text_message_{msg_id}.txt"
            text_filepath = os.path.join(DOWNLOADS_DIR, text_filename)
            with open(text_filepath, 'w', encoding='utf-8') as f:
                f.write(msg.text or msg.caption or "")
            return {
                "type": "text",
                "path": text_filepath,
                "original": text_filename,
                "size": os.path.getsize(text_filepath),
                "caption": ""
            }

        file_info = get_file_info(msg, msg_id)
        file_path = os.path.join(DOWNLOADS_DIR, file_info["name"])
        
        # Ensure unique filename
        counter = 1
        base_name, ext = os.path.splitext(file_info["name"])
        while os.path.exists(file_path):
            file_path = os.path.join(DOWNLOADS_DIR, f"{base_name}_{counter}{ext}")
            counter += 1

        # Download with progress
        def progress(current, total):
            percent = current * 100 / total
            batch_status.update_progress(user_id, msg_id, percent)

        dl_path = await asyncio.wait_for(
            acc.download_media(
                msg,
                file_name=file_path,
                progress=progress
            ),
            timeout=DOWNLOAD_TIMEOUT
        )

        if not dl_path or not os.path.exists(dl_path):
            raise Exception("Download failed - file not created")

        file_size = os.path.getsize(dl_path)
        
        return {
            "type": msg_type.lower(),
            "path": dl_path,
            "original": file_info["original"],
            "size": file_size,
            "caption": msg.caption or ""
        }

    except asyncio.TimeoutError:
        if ERROR_MESSAGE:
            await client.send_message(
                message.chat.id,
                f"⚠️ **Download Timeout**\n\nMessage ID: {msg_id}",
                reply_to_message_id=message.id
            )
    except Exception as e:
        if ERROR_MESSAGE:
            await client.send_message(
                message.chat.id,
                f"⚠️ **Download Failed**\n\nMessage ID: {msg_id}\nError: `{e}`",
                reply_to_message_id=message.id
            )
    return None

async def process_message_batch(
    client: Client,
    message: Message,
    chat_id: int,
    msg_ids: List[int],
    user_data: str
):
    user_id = message.from_user.id
    batch_status.set_batch_status(user_id, False)
    
    try:
        acc = Client("saverestricted", session_string=user_data, api_hash=API_HASH, api_id=API_ID)
        await acc.connect()
    except Exception as e:
        batch_status.set_batch_status(user_id, True)
        return await message.reply(f"**Session Error:** `{e}`\n\n/logout and /login again.")

    # Create status message
    status_msg = await client.send_message(
        message.chat.id,
        "🔄 **Starting batch download...**",
        reply_to_message_id=message.id
    )
    batch_status.status_messages[user_id] = status_msg
    
    # Start status updater
    asyncio.create_task(download_status_updater(client, user_id, message.chat.id))
    
    # Process downloads in parallel with semaphore
    semaphore = asyncio.Semaphore(MAX_PARALLEL_DOWNLOADS)
    tasks = []
    results = []
    
    async def process_single_message(msg_id: int):
        async with semaphore:
            if batch_status.is_batch_active(user_id):
                return None
                
            try:
                result = await download_file(client, acc, message, chat_id, msg_id, user_id)
                if result:
                    results.append(result)
            except Exception as e:
                if ERROR_MESSAGE:
                    await client.send_message(
                        message.chat.id,
                        f"⚠️ **Error Processing Message**\n\nID: {msg_id}\nError: `{e}`",
                        reply_to_message_id=message.id
                    )
            finally:
                batch_status.update_progress(user_id, msg_id, 100)

    for msg_id in msg_ids:
        if batch_status.is_batch_active(user_id):
            break
        task = asyncio.create_task(process_single_message(msg_id))
        batch_status.add_download_task(user_id, task)
        tasks.append(task)
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Clean up
    await acc.disconnect()
    batch_status.set_batch_status(user_id, True)
    
    if user_id in batch_status.status_messages:
        await batch_status.status_messages[user_id].delete()
        del batch_status.status_messages[user_id]
    
    if batch_status.is_batch_active(user_id):
        return await message.reply("**Batch download cancelled.**")
    
    # Send summary
    success_count = len(results)
    if success_count > 0:
        summary = f"✅ **Batch Download Complete**\n\n"
        summary += f"• Total Messages: {len(msg_ids)}\n"
        summary += f"• Successfully Downloaded: {success_count}\n"
        summary += f"• Failed: {len(msg_ids) - success_count}\n\n"
        
        if success_count <= 10:  # Only show details for small batches
            for result in results:
                size_str = f"{result['size']/1024:.1f} KB" if result['size'] < 1024*1024 else f"{result['size']/(1024*1024):.1f} MB"
                summary += f"📄 **{result['type'].title()}**: `{result['original']}` ({size_str})\n"
        
        await message.reply(summary)
    else:
        await message.reply("⚠️ **No files were downloaded successfully.**")

@Client.on_message(filters.command(["start"]))
async def send_start(client: Client, message: Message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
    buttons = [[
        InlineKeyboardButton("❣️ Developer", url="https://t.me/kingvj01")
    ],[
        InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url='https://t.me/vj_bot_disscussion'),
        InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url='https://t.me/vj_botz')
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await client.send_message(
        chat_id=message.chat.id, 
        text=f"<b>👋 Hi {message.from_user.mention}, I am Save Restricted Content Bot, I can download restricted content by its post link to local storage.\n\nFor downloading restricted content /login first.\n\nKnow how to use bot by - /help</b>", 
        reply_markup=reply_markup, 
        reply_to_message_id=message.id
    )

@Client.on_message(filters.command(["help"]))
async def send_help(client: Client, message: Message):
    await client.send_message(
        chat_id=message.chat.id, 
        text=HELP_TXT
    )

@Client.on_message(filters.command(["cancel"]))
async def send_cancel(client: Client, message: Message):
    user_id = message.from_user.id
    batch_status.set_batch_status(user_id, True)
    batch_status.cancel_all_tasks(user_id)
    if user_id in batch_status.status_messages:
        await batch_status.status_messages[user_id].delete()
        del batch_status.status_messages[user_id]
    await client.send_message(
        chat_id=message.chat.id, 
        text="**Batch download cancelled successfully.**"
    )

@Client.on_message(filters.text & filters.private)
async def save(client: Client, message: Message):
    if "https://t.me/" not in message.text:
        return

    user_id = message.from_user.id
    if not batch_status.is_batch_active(user_id):
        return await message.reply("**One task is already processing. Wait for it to complete or use /cancel.**")

    user_data = await db.get_session(user_id)
    if user_data is None:
        return await message.reply("**For downloading restricted content you have to /login first.**")

    datas = message.text.split("/")
    temp = datas[-1].replace("?single", "").split("-")
    from_id = int(temp[0].strip())
    try:
        to_id = int(temp[1].strip())
    except:
        to_id = from_id

    msg_ids = list(range(from_id, to_id + 1))
    if len(msg_ids) > 100:
        return await message.reply("**Batch size too large. Maximum 100 messages per batch.**")

    # Determine chat ID based on URL type
    if "https://t.me/c/" in message.text:  # Private
        chat_id = int("-100" + datas[4])
    elif "https://t.me/b/" in message.text:  # Bot
        chat_id = datas[4]  # username
    else:  # Public
        chat_id = datas[3]  # username

    await process_message_batch(client, message, chat_id, msg_ids, user_data)
