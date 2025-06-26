# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import asyncio 
import time
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
from typing import List, Dict, Optional, Tuple

# Constants
MAX_PARALLEL_DOWNLOADS = 20
DOWNLOAD_TIMEOUT = 100
STATUS_UPDATE_INTERVAL = 10
MAX_BATCH_SIZE = 5000
FLOOD_WAIT_THRESHOLD = 10
DOWNLOADS_DIR = "downloads"

# Create downloads directory if it doesn't exist
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

class BatchStatus:
    def __init__(self):
        self.active_batches: Dict[int, bool] = {}
        self.download_tasks: Dict[int, List[asyncio.Task]] = {}
        self.status_messages: Dict[int, Message] = {}
        self.progress: Dict[int, Dict[str, Tuple[float, str]]] = {}
        self.last_flood_wait: Dict[int, float] = {}
        self.active_downloads: Dict[int, int] = {}
        self.completed_batches: Dict[int, bool] = {}

    def is_batch_active(self, user_id: int) -> bool:
        return not self.active_batches.get(user_id, True)
    
    def set_batch_status(self, user_id: int, status: bool):
        self.active_batches[user_id] = not status
        if status:  # If marking as complete
            self.completed_batches[user_id] = True
        else:
            self.completed_batches.pop(user_id, None)
        
    def add_download_task(self, user_id: int, task: asyncio.Task):
        if user_id not in self.download_tasks:
            self.download_tasks[user_id] = []
        self.download_tasks[user_id].append(task)
        
    def cancel_all_tasks(self, user_id: int):
        if user_id in self.download_tasks:
            for task in self.download_tasks[user_id]:
                if not task.done():
                    task.cancel()
            self.download_tasks[user_id] = []
            
    def update_progress(self, user_id: int, msg_id: int, progress: float, status: str = "Downloading"):
        if user_id not in self.progress:
            self.progress[user_id] = {}
        self.progress[user_id][msg_id] = (progress, status)
        
    def get_progress(self, user_id: int) -> Dict[int, Tuple[float, str]]:
        return self.progress.get(user_id, {})
    
    def record_flood_wait(self, user_id: int, wait_time: float):
        self.last_flood_wait[user_id] = wait_time
        
    def increment_active_downloads(self, user_id: int):
        self.active_downloads[user_id] = self.active_downloads.get(user_id, 0) + 1
        
    def decrement_active_downloads(self, user_id: int):
        self.active_downloads[user_id] = max(0, self.active_downloads.get(user_id, 0) - 1)
        
    def get_active_downloads(self, user_id: int) -> int:
        return self.active_downloads.get(user_id, 0)
    
    def is_batch_completed(self, user_id: int) -> bool:
        return self.completed_batches.get(user_id, False)

batch_status = BatchStatus()

async def download_status_updater(client: Client, user_id: int, chat_id: int, start_msg: Message):
    last_update = 0
    flood_wait_warning_sent = False
    
    while not batch_status.is_batch_active(user_id) and user_id in batch_status.status_messages:
        current_time = time.time()
        progress = batch_status.get_progress(user_id)
        
        last_flood = batch_status.last_flood_wait.get(user_id, 0)
        if last_flood >= FLOOD_WAIT_THRESHOLD and not flood_wait_warning_sent:
            await client.send_message(
                chat_id,
                f"⚠️ **Slowing down downloads due to Telegram rate limits**\n\n"
                f"The bot is automatically adjusting download speed to avoid restrictions.",
                reply_to_message_id=start_msg.id
            )
            flood_wait_warning_sent = True
        
        if progress:
            status_text = "**Download Progress**\n\n"
            completed = 0
            total = len(progress)
            
            for msg_id, (percent, status) in progress.items():
                if percent >= 100:
                    completed += 1
                status_text += f"• {msg_id}: {status} ({percent:.1f}%)\n"
            
            status_text += (
                f"\n**Completed:** {completed}/{total}\n"
                f"**Active Downloads:** {batch_status.get_active_downloads(user_id)}/{MAX_PARALLEL_DOWNLOADS}"
            )
            
            try:
                await batch_status.status_messages[user_id].edit_text(status_text)
            except:
                pass
        
        await asyncio.sleep(STATUS_UPDATE_INTERVAL)
    
    # Final update when batch completes
    if user_id in batch_status.status_messages and batch_status.is_batch_completed(user_id):
        try:
            await batch_status.status_messages[user_id].edit_text("✅ **Batch download completed successfully!**")
            await asyncio.sleep(3)
            await batch_status.status_messages[user_id].delete()
        except:
            pass

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
            batch_status.update_progress(user_id, msg_id, 0, "Message not found")
            return None

        msg_type = get_message_type(msg)
        if not msg_type or msg_type == "Unknown":
            batch_status.update_progress(user_id, msg_id, 0, "Unsupported type")
            return None

        if msg_type == "Text":
            text_filename = f"text_message_{msg_id}.txt"
            text_filepath = os.path.join(DOWNLOADS_DIR, text_filename)
            with open(text_filepath, 'w', encoding='utf-8') as f:
                f.write(msg.text or msg.caption or "")
            batch_status.update_progress(user_id, msg_id, 100, "Completed")
            return {
                "type": "text",
                "path": text_filepath,
                "original": text_filename,
                "size": os.path.getsize(text_filepath),
                "caption": ""
            }

        file_info = get_file_info(msg, msg_id)
        file_path = os.path.join(DOWNLOADS_DIR, file_info["name"])
        
        counter = 1
        base_name, ext = os.path.splitext(file_info["name"])
        while os.path.exists(file_path):
            file_path = os.path.join(DOWNLOADS_DIR, f"{base_name}_{counter}{ext}")
            counter += 1

        def progress(current, total):
            percent = current * 100 / total
            batch_status.update_progress(user_id, msg_id, percent, "Downloading")

        batch_status.update_progress(user_id, msg_id, 0, "Starting download")
        batch_status.increment_active_downloads(user_id)
        
        try:
            dl_path = await asyncio.wait_for(
                acc.download_media(
                    msg,
                    file_name=file_path,
                    progress=progress
                ),
                timeout=DOWNLOAD_TIMEOUT
            )
        except FloodWait as e:
            batch_status.record_flood_wait(user_id, e.value)
            batch_status.update_progress(user_id, msg_id, 0, f"Waiting {e.value}s")
            await asyncio.sleep(e.value)
            return await download_file(client, acc, message, chat_id, msg_id, user_id)
        except asyncio.TimeoutError:
            batch_status.update_progress(user_id, msg_id, 0, "Timeout")
            if ERROR_MESSAGE:
                await client.send_message(
                    message.chat.id,
                    f"⚠️ **Download Timeout**\n\nMessage ID: {msg_id}",
                    reply_to_message_id=message.id
                )
            return None
        except Exception as e:
            batch_status.update_progress(user_id, msg_id, 0, f"Error: {str(e)}")
            if ERROR_MESSAGE:
                await client.send_message(
                    message.chat.id,
                    f"⚠️ **Download Failed**\n\nMessage ID: {msg_id}\nError: `{e}`",
                    reply_to_message_id=message.id
                )
            return None
        finally:
            batch_status.decrement_active_downloads(user_id)

        if not dl_path or not os.path.exists(dl_path):
            batch_status.update_progress(user_id, msg_id, 0, "Download failed")
            raise Exception("Download failed - file not created")

        file_size = os.path.getsize(dl_path)
        batch_status.update_progress(user_id, msg_id, 100, "Completed")
        
        caption_path = None
        if msg.caption:
            caption_filename = f"{os.path.splitext(file_info['name'])[0]}_caption.txt"
            caption_path = os.path.join(DOWNLOADS_DIR, caption_filename)
            with open(caption_path, 'w', encoding='utf-8') as f:
                f.write(msg.caption)
        
        return {
            "type": msg_type.lower(),
            "path": dl_path,
            "original": file_info["original"],
            "size": file_size,
            "caption": msg.caption or "",
            "caption_path": caption_path
        }

    except Exception as e:
        batch_status.update_progress(user_id, msg_id, 0, f"Error: {str(e)}")
        if ERROR_MESSAGE:
            await client.send_message(
                message.chat.id,
                f"⚠️ **Error Processing Message**\n\nID: {msg_id}\nError: `{e}`",
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
    
    if not batch_status.is_batch_active(user_id) and not batch_status.is_batch_completed(user_id):
        return await message.reply("Another batch is already in progress. Wait or use /cancel.")

    # Reset completion status when starting new batch
    batch_status.completed_batches.pop(user_id, None)
    batch_status.set_batch_status(user_id, False)
    batch_status.cancel_all_tasks(user_id)
    
    try:
        acc = Client("saverestricted", session_string=user_data, api_hash=API_HASH, api_id=API_ID)
        await acc.start()
    except Exception as e:
        batch_status.set_batch_status(user_id, True)
        return await message.reply(f"**Session Error:** `{e}`\n\n/logout and /login again.")

    status_msg = await client.send_message(
        message.chat.id,
        "🔄 **Starting parallel downloads...**\n\n"
        f"• Total Messages: {len(msg_ids)}\n"
        f"• Parallel Downloads: {MAX_PARALLEL_DOWNLOADS}\n"
        "• Preparing to download...",
        reply_to_message_id=message.id
    )
    batch_status.status_messages[user_id] = status_msg
    
    status_task = asyncio.create_task(
        download_status_updater(client, user_id, message.chat.id, message)
    )
    
    semaphore = asyncio.BoundedSemaphore(MAX_PARALLEL_DOWNLOADS)
    tasks = []
    results = []
    failed = 0
    
    async def process_single_message(msg_id: int):
        nonlocal failed, results
        async with semaphore:
            if batch_status.is_batch_active(user_id):
                return None
                
            try:
                result = await download_file(client, acc, message, chat_id, msg_id, user_id)
                if result:
                    results.append(result)
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                if ERROR_MESSAGE:
                    await client.send_message(
                        message.chat.id,
                        f"⚠️ **Error Processing Message**\n\nID: {msg_id}\nError: `{e}`",
                        reply_to_message_id=message.id
                    )

    for msg_id in msg_ids:
        if batch_status.is_batch_active(user_id):
            break
        task = asyncio.create_task(process_single_message(msg_id))
        tasks.append(task)
        batch_status.add_download_task(user_id, task)
        await asyncio.sleep(0.1)
    
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        if ERROR_MESSAGE:
            await client.send_message(
                message.chat.id,
                f"⚠️ **Batch Error:** `{e}`",
                reply_to_message_id=message.id
            )
    
    try:
        await acc.stop()
    except:
        pass
    
    status_task.cancel()
    try:
        await status_task
    except:
        pass
    
    # Mark batch as completed
    batch_status.set_batch_status(user_id, True)
    
    if user_id in batch_status.status_messages:
        try:
            await batch_status.status_messages[user_id].delete()
        except:
            pass
        del batch_status.status_messages[user_id]
    
    # Send summary
    success_count = len(results)
    total_count = len(msg_ids)
    
    summary = f"✅ **Batch Download Complete**\n\n"
    summary += f"• Total Messages: {total_count}\n"
    summary += f"• Successfully Downloaded: {success_count}\n"
    summary += f"• Failed: {failed}\n\n"
    
    if success_count > 0:
        total_size = sum(r['size'] for r in results)
        size_str = f"{total_size/1024/1024:.2f} MB" if total_size > 1024*1024 else f"{total_size/1024:.2f} KB"
        summary += f"• Total Size: {size_str}\n"
        
        if success_count <= 5:
            summary += "\n**Downloaded Files:**\n"
            for result in results:
                file_size = f"{result['size']/1024/1024:.2f} MB" if result['size'] > 1024*1024 else f"{result['size']/1024:.2f} KB"
                summary += f"- {result['original']} ({file_size})\n"
    
    await message.reply(summary)

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
        try:
            await batch_status.status_messages[user_id].delete()
        except:
            pass
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
    if not batch_status.is_batch_active(user_id) and not batch_status.is_batch_completed(user_id):
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
    if len(msg_ids) > MAX_BATCH_SIZE:
        return await message.reply(f"**Batch size too large. Maximum {MAX_BATCH_SIZE} messages per batch.**")

    if "https://t.me/c/" in message.text:
        chat_id = int("-100" + datas[4])
    elif "https://t.me/b/" in message.text:
        chat_id = datas[4]
    else:
        chat_id = datas[3]

    await process_message_batch(client, message, chat_id, msg_ids, user_data)
