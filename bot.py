from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from youtubeDownload import handle_youtube_url, create_quality_keyboard, download_youtube
import os
import asyncio
from moviepy.editor import VideoFileClip
import math

# Your bot token
TOKEN = '7011058660:AAF9TuTSpgvmjypMXEBVbkZNKx5b9HxdxLQ'

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command"""
    await update.message.reply_text('Hi! This is bot made by Cursor AI')
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu"""
    keyboard = [
        [KeyboardButton("Menu 1")],
        [KeyboardButton("Menu 2")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        text="Please choose a menu:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu selections"""
    text = update.message.text

    if text == "Menu 1":
        keyboard = [
            [KeyboardButton("YouTube Video Downloader")],
            [KeyboardButton("Option 2")],
            [KeyboardButton("Back to Main Menu")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            text="Menu 1 Options:",
            reply_markup=reply_markup
        )

    elif text == "Menu 2":
        keyboard = [
            [KeyboardButton("Option A")],
            [KeyboardButton("Option B")],
            [KeyboardButton("Back to Main Menu")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            text="Menu 2 Options:",
            reply_markup=reply_markup
        )

    elif text == "YouTube Video Downloader":
        await update.message.reply_text("Please send the YouTube video URL:")
        return "WAITING_FOR_YOUTUBE_URL"

    elif text in ["Option 2", "Option A", "Option B"]:
        await update.message.reply_text(f"You selected {text}!")
        await show_main_menu(update, context)

    elif text == "Back to Main Menu":
        await show_main_menu(update, context)

async def handle_callback_query(update, context):
    query = update.callback_query
    data = query.data
    
    if data.startswith("dl_video_"):
        loading_msg = await query.edit_message_text("⏳ Downloading... Please wait.")
        
        parts = data.split("_")
        url = parts[2]
        quality = parts[3]
        
        # Show progress updates
        await loading_msg.edit_text("⏳ Downloading... (This might take a few minutes)")
        
        file_path, title = await download_youtube(url, quality, is_audio=False)
        
        if file_path:
            await loading_msg.edit_text("📤 Processing video...")
            
            try:
                # Check file size
                file_size = os.path.getsize(file_path)
                max_size = 50 * 1024 * 1024  # 50MB limit for Telegram
                
                if file_size > max_size:
                    # Split video into parts
                    video = VideoFileClip(file_path)
                    duration = video.duration
                    
                    # Calculate how many parts we need
                    num_parts = math.ceil(file_size / max_size)
                    part_duration = duration / num_parts
                    
                    await loading_msg.edit_text(f"Video is too large, splitting into {num_parts} parts...")
                    
                    for i in range(num_parts):
                        start_time = i * part_duration
                        end_time = min((i + 1) * part_duration, duration)
                        
                        # Extract part of the video
                        part = video.subclip(start_time, end_time)
                        part_filename = f"downloads/part_{i+1}_{os.path.basename(file_path)}"
                        part.write_videofile(part_filename, codec='libx264')
                        
                        # Send part
                        await loading_msg.edit_text(f"📤 Uploading part {i+1} of {num_parts}...")
                        
                        # Try to send as video first, if fails then send as document
                        success = False
                        try:
                            with open(part_filename, 'rb') as video_file:
                                await query.message.reply_video(
                                    video=video_file,
                                    caption=f"✅ {title} (Part {i+1}/{num_parts})",
                                    supports_streaming=True
                                )
                                success = True
                        except Exception as e:
                            print(f"Error sending video part: {e}")
                            
                        # Only try document if video send failed
                        if not success:
                            try:
                                with open(part_filename, 'rb') as doc_file:
                                    await query.message.reply_document(
                                        document=doc_file,
                                        caption=f"✅ {title} (Part {i+1}/{num_parts})"
                                    )
                            except Exception as e:
                                print(f"Error sending document part: {e}")
                                await loading_msg.edit_text(f"❌ Error uploading part {i+1}")
                        
                        # Clean up part file
                        try:
                            os.remove(part_filename)
                        except Exception as e:
                            print(f"Error removing part file: {e}")
                    
                    # Clean up and close video
                    video.close()
                    await loading_msg.delete()
                    
                else:
                    # Original code for small videos
                    await loading_msg.edit_text("📤 Upload in progress...")
                    success = False
                    try:
                        with open(file_path, 'rb') as video_file:
                            await query.message.reply_video(
                                video=video_file,
                                caption=f"✅ {title}",
                                supports_streaming=True
                            )
                            success = True
                        await loading_msg.delete()
                    except Exception as e:
                        print(f"Error sending as video: {e}")
                        if not success:
                            with open(file_path, 'rb') as doc_file:
                                await query.message.reply_document(
                                    document=doc_file,
                                    caption="✅ Here's your file!"
                                )
                            await loading_msg.delete()
                
            except Exception as e:
                print(f"Error handling file: {e}")
                await loading_msg.edit_text("❌ Sorry, there was an error processing the file.")
            
            finally:
                # Clean up
                await asyncio.sleep(1)
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file: {e}")
        else:
            await loading_msg.edit_text("❌ Sorry, there was an error downloading the file.")

def run_bot():
    """Run the bot"""
    # Create the Application instance
    app = Application.builder().token(TOKEN).build()

    # Create conversation handler
    from telegram.ext import ConversationHandler
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            "WAITING_FOR_YOUTUBE_URL": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_url)]
        },
        fallbacks=[CommandHandler('start', start_command)]
    )

    # Add handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Start the bot
    print('Bot is running...')
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    try:
        run_bot()
    except Exception as e:
        print(f"Error occurred: {e}")