import asyncio
import glob
import json
import os
import random
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from googleapiclient.discovery import build 
from googleapiclient.errors import HttpError

import config
from AnonMusic import LOGGER
from AnonMusic.utils.formatters import time_to_seconds

logger = LOGGER(__name__)

# --- API KEY ROTATION LOGIC ---
API_KEYS = [k.strip() for k in config.API_KEY.split(",")] if config.API_KEY else []
current_key_index = 0

def get_youtube_client():
    global current_key_index
    if not API_KEYS or current_key_index >= len(API_KEYS):
        return None
    return build("youtube", "v3", developerKey=API_KEYS[current_key_index], static_discovery=False)

def switch_key():
    global current_key_index
    current_key_index += 1
    if current_key_index < len(API_KEYS):
        logger.warning(f"YouTube Quota Finished. Switching to Key #{current_key_index + 1}")
        return True
    logger.error("All YouTube API Keys are exhausted!")
    return False

# --- COOKIE LOGIC ---
def get_cookie_file():
    try:
        folder_path = os.path.join(os.getcwd(), "cookies")
        if not os.path.exists(folder_path):
            return None
        txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
        if not txt_files:
            return None
        return random.choice(txt_files)
    except Exception:
        return None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|youtube\.com\/shorts)"
        self.listbase = "https://youtube.com/playlist?list="

    def parse_duration(self, duration):
        if not duration:
            return "00:00", 0
        match = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        total_seconds = hours * 3600 + minutes * 60 + seconds
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
        return duration_str, total_seconds

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: 
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)
        for msg in messages:
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        return (msg.text or msg.caption)[entity.offset : entity.offset + entity.length]
            if msg.caption_entities:
                for entity in msg.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: 
            vidid = link
        else:
            match = re.search(r"(?:v=|\/|shorts\/)([0-9A-Za-z_-]{11})", link)
            vidid = match.group(1) if match else None

        # --- Method 1: Try using YouTube API (Fastest) ---
        youtube = get_youtube_client()
        if youtube:
            try:
                if not vidid:
                    search = await asyncio.to_thread(youtube.search().list(q=link, part="id", maxResults=1, type="video").execute)
                    if search.get("items"):
                        vidid = search["items"][0]["id"]["videoId"]
                
                if vidid:
                    video_data = await asyncio.to_thread(youtube.videos().list(part="snippet,contentDetails", id=vidid).execute)
                    if video_data.get("items"):
                        item = video_data["items"][0]
                        title = item["snippet"]["title"]
                        thumb = item["snippet"]["thumbnails"]["high"]["url"]
                        d_min, d_sec = self.parse_duration(item["contentDetails"]["duration"])
                        return title, d_min, d_sec, thumb, vidid
            except HttpError as e:
                if e.resp.status == 403:
                    switch_key()
                logger.error(f"YouTube API Error: {e}")

        # --- Method 2: Fallback to yt-dlp (Reliable if API Fails) ---
        try:
            cookie = get_cookie_file()
            ydl_opts = {"quiet": True, "cookiefile": cookie} if cookie else {"quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # If not a link, search it
                search_query = f"ytsearch1:{link}" if not vidid else self.base + vidid
                info = await asyncio.to_thread(ydl.extract_info, search_query, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                
                title = info.get("title")
                vidid = info.get("id")
                duration_sec = info.get("duration", 0)
                thumb = info.get("thumbnail")
                
                # Format duration
                m, s = divmod(duration_sec, 60)
                h, m = divmod(m, 60)
                d_min = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
                
                return title, d_min, duration_sec, thumb, vidid
        except Exception as e:
            logger.error(f"yt-dlp extraction error: {e}")
            return None

    async def track(self, link: str, videoid: Union[bool, str] = None):
        res = await self.details(link, videoid)
        if not res: 
            return None, None
        title, d_min, d_sec, thumb, vidid = res
        track_details = {
            "title": title, 
            "link": self.base + vidid, 
            "vidid": vidid, 
            "duration_min": d_min, 
            "thumb": thumb
        }
        return track_details, vidid

    async def download(self, link: str, mystic, video=None, videoid=None, songaudio=None, songvideo=None, format_id=None, title=None) -> str:
        if videoid: 
            link = self.base + link
        
        loop = asyncio.get_running_loop()
        cookie = get_cookie_file()
        
        if not os.path.exists("downloads"):
            os.mkdir("downloads")

        common_opts = {
            "quiet": True, 
            "no_warnings": True, 
            "geo_bypass": True, 
            "nocheckcertificate": True,
            "outtmpl": "downloads/%(title)s.%(ext)s"
        }
        if cookie: 
            common_opts["cookiefile"] = cookie

        def ytdl_run(opts):
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                return ydl.prepare_filename(info)

        try:
            if songvideo:
                opts = {**common_opts, "format": f"{format_id}+140/bestvideo+bestaudio", "merge_output_format": "mp4"}
            elif songaudio:
                opts = {**common_opts, "format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]}
            else:
                opts = {**common_opts, "format": "bestaudio/best"}

            downloaded_file = await loop.run_in_executor(None, lambda: ytdl_run(opts))
            return downloaded_file
        except Exception as e:
            logger.error(f"Download Error: {e}")
            return None
