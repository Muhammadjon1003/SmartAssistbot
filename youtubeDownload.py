from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import yt_dlp
import os
import re

def extract_video_id(url):
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&\s]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^\?\s]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^\?\s]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def validate_youtube_url(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=False)
        return True
    except Exception as e:
        print(f"Validation error: {str(e)}")
        return False

def get_video_info(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best'  # This ensures we get all formats
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            # Get available qualities
            available_qualities = set()
            for f in formats:
                # Check for formats that have both video and audio
                if (f.get('vcodec') != 'none' and 
                    f.get('acodec') != 'none' and 
                    f.get('height') is not None):
                    available_qualities.add(f'{f["height"]}p')
                # Also check for formats that are video only but in MP4
                elif (f.get('ext') == 'mp4' and 
                      f.get('vcodec') != 'none' and 
                      f.get('height') is not None):
                    available_qualities.add(f'{f["height"]}p')
            
            # Add common qualities if they're available in any format
            all_heights = set(f.get('height', 0) for f in formats if f.get('height') is not None)
            common_qualities = {'144p', '240p', '360p', '480p', '720p', '1080p'}
            for height in all_heights:
                quality = f'{height}p'
                if quality in common_qualities:
                    available_qualities.add(quality)
            
            # Sort qualities
            available_qualities = sorted(list(available_qualities), 
                                      key=lambda x: int(x[:-1]), 
                                      reverse=True)
            
            if not available_qualities:
                # Fallback to common qualities if none were found
                available_qualities = ['360p', '720p']
            
            return available_qualities, info.get('title')
    except Exception as e:
        print(f"Error getting video info: {str(e)}")
        return None, None

def create_quality_keyboard(url, is_audio=False):
    keyboard = []
    # Get available qualities for this video
    qualities, _ = get_video_info(url)
    if qualities:
        row = []
        for quality in qualities:
            row.append(InlineKeyboardButton(
                quality, 
                callback_data=f"dl_video_{url}_{quality}"
            ))
            if len(row) == 2:  # Create rows with 2 buttons each
                keyboard.append(row)
                row = []
        if row:  # Add any remaining buttons
            keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)

def create_format_keyboard(url):
    # Get video qualities directly instead of showing format selection
    return create_quality_keyboard(url)

async def download_youtube(url, format_id, is_audio=False):
    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')
        
        output_template = 'downloads/%(title)s.%(ext)s'
        
        try:
            # Clean the format_id string and extract just the numbers
            target_height = int(''.join(filter(str.isdigit, format_id)))
        except (ValueError, TypeError):
            # If conversion fails, use default quality
            target_height = 720
            print(f"Invalid format_id: {format_id}, using default: {target_height}p")
        
        # Default fallback
        selected_format_id = None

        # Get available formats
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

            # Look for exact quality match with size limit
            max_size = 45 * 1024 * 1024  # 45MB to be safe
            for f in formats:
                if (f.get('height') == target_height and 
                    f.get('ext') == 'mp4' and 
                    f.get('acodec') != 'none' and 
                    f.get('vcodec') != 'none' and 
                    f.get('filesize', float('inf')) < max_size):
                    selected_format_id = f['format_id']
                    break

        # Update ydl_opts with the selected format ID and ffmpeg settings
        ydl_opts = {
            'format': selected_format_id if selected_format_id else f'bestvideo[height<={target_height}][ext=mp4][filesize<{max_size}]+bestaudio[ext=m4a]/best[height<={target_height}][ext=mp4][filesize<{max_size}]',
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'prefer_ffmpeg': True,
            'ffmpeg_location': r'C:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base = os.path.splitext(filename)[0]
            filename = f"{base}.mp4"
            
            if os.path.exists(filename):
                return filename, info.get('title', 'Video')
            else:
                print(f"File not found: {filename}")
                return None, None
                
    except Exception as e:
        print(f"Error downloading: {str(e)}")
        return None, None

async def handle_youtube_url(update, context):
    url = update.message.text.strip()
    
    # Send loading message
    loading_message = await update.message.reply_text("🔄 Analyzing video URL, please wait...")
    
    if not validate_youtube_url(url):
        await loading_message.edit_text("❌ Invalid YouTube URL. Please send a valid YouTube video link.")
        return
    
    formats, title = get_video_info(url)
    if not formats:
        await loading_message.edit_text("❌ Error fetching video information. Please try again with a different video.")
        return
    
    await loading_message.edit_text(
        f"🎥 *Video Title:* {title}\n\nPlease select the format:",
        parse_mode='Markdown',
        reply_markup=create_format_keyboard(url)
    )