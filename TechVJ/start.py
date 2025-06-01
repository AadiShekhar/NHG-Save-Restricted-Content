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

# Create downloads directory
DOWNLOADS_DIR = "downloads"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

class batch_temp(object):
    IS_BATCH = {}

async def downstatus(client, statusfile, message, chat):
    while True:
        if os.path.exists(statusfile):
            break

        await asyncio.sleep(3)
      
    while os.path.exists(statusfile):
        with open(statusfile, "r") as downread:
            txt = downread.read()
        try:
            await client.edit_message_text(chat, message.id, f"**Downloaded:** **{txt}**")
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(5)


# progress writer
def progress(current, total, message, type):
    with open(f'{message.id}{type}status.txt', "w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")


# File info helper function
def get_file_info(msg: pyrogram.types.Message, msgid: int):
    # Clean filename helper
    def clean_filename(text):
        return re.sub(r'[\\/*?:"<>|]', "", text).strip()
    
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
    
    # Fallback for unknown types
    if not file_info["ext"]:
        file_info["ext"] = ".bin"
        file_info["original"] = f"file_{msgid}.bin"
        file_info["name"] = f"{msgid}_file.bin"
    
    return file_info


# start command
@Client.on_message(filters.command(["start"]))
async def send_start(client: Client, message: Message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
    buttons = [[
        InlineKeyboardButton("❣️ Developer", url = "https://t.me/kingvj01")
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
    return


# help command
@Client.on_message(filters.command(["help"]))
async def send_help(client: Client, message: Message):
    await client.send_message(
        chat_id=message.chat.id, 
        text=f"{HELP_TXT}"
    )

# cancel command
@Client.on_message(filters.command(["cancel"]))
async def send_cancel(client: Client, message: Message):
    batch_temp.IS_BATCH[message.from_user.id] = True
    await client.send_message(
        chat_id=message.chat.id, 
        text="**Batch Successfully Cancelled.**"
    )

@Client.on_message(filters.text & filters.private)
async def save(client: Client, message: Message):
    if "https://t.me/" in message.text:
        if batch_temp.IS_BATCH.get(message.from_user.id) == False:
            return await message.reply_text("**One Task Is Already Processing. Wait For Complete It. If You Want To Cancel This Task Then Use - /cancel**")
        datas = message.text.split("/")
        temp = datas[-1].replace("?single","").split("-")
        fromID = int(temp[0].strip())
        try:
            toID = int(temp[1].strip())
        except:
            toID = fromID
        batch_temp.IS_BATCH[message.from_user.id] = False
        
        for msgid in range(fromID, toID+1):
            if batch_temp.IS_BATCH.get(message.from_user.id): break
            user_data = await db.get_session(message.from_user.id)
            if user_data is None:
                await message.reply("**For Downloading Restricted Content You Have To /login First.**")
                batch_temp.IS_BATCH[message.from_user.id] = True
                return
            try:
                acc = Client("saverestricted", session_string=user_data, api_hash=API_HASH, api_id=API_ID)
                await acc.connect()
            except:
                batch_temp.IS_BATCH[message.from_user.id] = True
                return await message.reply("**Your Login Session Expired. So /logout First Then Login Again By - /login**")
            
            # private
            if "https://t.me/c/" in message.text:
                chatid = int("-100" + datas[4])
                try:
                    await handle_private(client, acc, message, chatid, msgid)
                except Exception as e:
                    if ERROR_MESSAGE == True:
                        await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)
    
            # bot
            elif "https://t.me/b/" in message.text:
                username = datas[4]
                try:
                    await handle_private(client, acc, message, username, msgid)
                except Exception as e:
                    if ERROR_MESSAGE == True:
                        await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)
            
            # public
            else:
                username = datas[3]

                try:
                    msg = await client.get_messages(username, msgid)
                except UsernameNotOccupied: 
                    await client.send_message(message.chat.id, "The username is not occupied by anyone", reply_to_message_id=message.id)
                    return
                try:
                    await handle_private(client, acc, message, username, msgid)
                except Exception as e:
                    if ERROR_MESSAGE == True:
                        await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)

            # wait time
            await asyncio.sleep(3)
        batch_temp.IS_BATCH[message.from_user.id] = True


# Enhanced handle_private function with proper filename handling
async def handle_private(client: Client, acc, message: Message, chatid: int, msgid: int):
    msg: Message = await acc.get_messages(chatid, msgid)
    if msg.empty: return 
    msg_type = get_message_type(msg)
    if not msg_type: return 
    chat = message.chat.id
    if batch_temp.IS_BATCH.get(message.from_user.id): return 
    
    if "Text" == msg_type:
        try:
            text_filename = f"text_message_{msgid}.txt"
            text_filepath = os.path.join(DOWNLOADS_DIR, text_filename)
            with open(text_filepath, 'w', encoding='utf-8') as f:
                f.write(msg.text or msg.caption or "")
            await client.send_message(chat, f"**Text saved to:** `{text_filepath}`", reply_to_message_id=message.id)
            return 
        except Exception as e:
            if ERROR_MESSAGE:
                await client.send_message(chat, f"Error: {e}", reply_to_message_id=message.id)
            return 

    smsg = await client.send_message(chat, '**Downloading...**', reply_to_message_id=message.id)
    asyncio.create_task(downstatus(client, f'{message.id}downstatus.txt', smsg, chat))
    
    try:
        # Get proper file information
        file_info = get_file_info(msg, msgid)
        
        # Create safe filename
        file_path = os.path.join(DOWNLOADS_DIR, file_info["name"])
        
        # Ensure unique filename
        counter = 1
        base_name, ext = os.path.splitext(file_info["name"])
        while os.path.exists(file_path):
            file_path = os.path.join(DOWNLOADS_DIR, f"{base_name}_{counter}{ext}")
            counter += 1
        
        # Download with progress
        dl_path = await acc.download_media(
            msg, 
            file_name=file_path,
            progress=progress,
            progress_args=[message, "down"]
        )
        
        if not dl_path or not os.path.exists(dl_path):
            raise Exception("Download failed - file not created")
            
        if os.path.exists(f'{message.id}downstatus.txt'):
            os.remove(f'{message.id}downstatus.txt')
            
    except Exception as e:
        if os.path.exists(f'{message.id}downstatus.txt'):
            os.remove(f'{message.id}downstatus.txt')
        if ERROR_MESSAGE:
            await client.send_message(chat, f"⚠️ **Download Failed**\n\nError: `{e}`", reply_to_message_id=message.id) 
        return await smsg.delete()
    
    if batch_temp.IS_BATCH.get(message.from_user.id): 
        return

    # Handle caption saving
    caption_text = msg.caption or ""
    if caption_text:
        try:
            base_name = os.path.splitext(file_info["name"])[0]
            caption_filename = f"{base_name}_caption.txt"
            caption_filepath = os.path.join(DOWNLOADS_DIR, caption_filename)
            
            # Ensure unique caption filename
            cap_counter = 1
            while os.path.exists(caption_filepath):
                caption_filepath = os.path.join(DOWNLOADS_DIR, f"{base_name}_caption_{cap_counter}.txt")
                cap_counter += 1
            
            with open(caption_filepath, 'w', encoding='utf-8') as f:
                f.write(caption_text)
        except Exception as e:
            if ERROR_MESSAGE:
                await client.send_message(chat, f"⚠️ **Caption Save Failed**\n\nError: `{e}`", reply_to_message_id=message.id)

    # Send success message
    file_size = os.path.getsize(dl_path)
    size_str = f"{file_size/1024:.1f} KB" if file_size < 1024*1024 else f"{file_size/(1024*1024):.1f} MB"
    
    await client.send_message(
        chat, 
        f"✅ **Saved Successfully!**\n\n"
        f"• **Original Name:** `{file_info['original']}`\n"
        f"• **Saved As:** `{os.path.basename(dl_path)}`\n"
        f"• **Type:** `{msg_type}`\n"
        f"• **Size:** {size_str}\n"
        f"• **Saved Path:** `{dl_path}`",
        reply_to_message_id=message.id
    )
    await client.delete_messages(chat, [smsg.id])


# get the type of message
def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
    try:
        msg.document.file_id
        return "Document"
    except:
        pass

    try:
        msg.video.file_id
        return "Video"
    except:
        pass

    try:
        msg.animation.file_id
        return "Animation"
    except:
        pass

    try:
        msg.sticker.file_id
        return "Sticker"
    except:
        pass

    try:
        msg.voice.file_id
        return "Voice"
    except:
        pass

    try:
        msg.audio.file_id
        return "Audio"
    except:
        pass

    try:
        msg.photo.file_id
        return "Photo"
    except:
        pass

    try:
        msg.video_note.file_id
        return "Video Note"
    except:
        pass

    try:
        if msg.text:
            return "Text"
    except:
        pass
    
    return "Unknown"
