import asyncio
import os
import re
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta

from aiohttp import web
import yt_dlp

DOWNLOAD_DIR = os.path.abspath("downloads/")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

download_tasks = {}
download_start_times = {}
download_locks = defaultdict(asyncio.Lock)

def format_duration(seconds):
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}m{secs}s"

async def handle_post(request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return response_json("Invalid JSON", None, None, None, None)

    url = data.get("url")
    audio_q = data.get("audio_quality")
    video_q = data.get("video_quality")

    if not url:
        return response_json('Missing "url"', None, None, None, None)

    if not audio_q and not video_q:
        return response_json('Either "audio_quality" or "video_quality" must be specified', None, None, None, url)

    try:
        service, video_id = await extract_video_info(url)
        base = sanitize_filename(f"{service}..{video_id}..")
        audio_file = base + "m4a" if audio_q else None
        video_file = base + "mp4" if video_q else None

        now = time.time()
        download_key = f"{base} a={audio_q} v={video_q}"
        age = None

        if download_key in download_start_times:
            age = now - download_start_times[download_key]

        # Launch background task if not running
        if download_key not in download_tasks:
            download_start_times[download_key] = now
            download_tasks[download_key] = asyncio.create_task(
                do_download(download_key, url, base, audio_q, video_q)
            )
            age = 0

        audio_path = os.path.join(DOWNLOAD_DIR, audio_file) if audio_file else None
        audio_ready = os.path.isfile(audio_path) if audio_path else False

        video_path = os.path.join(DOWNLOAD_DIR, video_file) if video_file else None
        video_ready = os.path.isfile(video_path) if video_path else False

        return response_json(
            "",
            audio_file if audio_ready else None,
            video_file if video_ready else None,
            format_duration(age) if age is not None else None,
            url
        )

    except Exception as e:
        return response_json(str(e), None, None, None, url)

async def extract_video_info(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        service = info.get("extractor_key", "unknown")
        video_id = info.get("id")
        if not video_id:
            raise Exception("Unable to extract video ID")
        return service, video_id

async def do_download(key, url, base, audio_q, video_q):
    async with download_locks[key]:
        if audio_q:
            await asyncio.to_thread(download_audio, url, base, audio_q)
        if video_q:
            await asyncio.to_thread(download_video, url, base, video_q)
        del download_tasks[key]

async def handle_file(request):
    filename = request.match_info["filename"]
    print(f"DEBUG filename=={filename}")
    if not re.match(r"^[a-zA-Z0-9.]+$", filename):
        print(f"DEBUG filename=={filename} not matching regexp")
        return web.Response(status=400, text="Invalid filename")
    path = os.path.join(DOWNLOAD_DIR, filename)
    print(f"DEBUG path=={path}")
    if not os.path.isfile(path):
        print(f"DEBUG path=={path} file does not exist")
        return web.Response(status=404, text="File not found")
    if filename.endswith(".m4a"):
        ctype = "audio/mp4"
    else:
        ctype = "video/mp4"
    return web.FileResponse(path=path, headers={"Content-Type": ctype})

def download_audio(url, base, quality):
    if quality == "min":
        format_str = "worstaudio[ext=m4a]/worstaudio"
    else:
        format_str = "bestaudio[ext=m4a]/bestaudio"
    opts = {
        "format": format_str,
        "outtmpl": os.path.join(DOWNLOAD_DIR, base),
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "0",
        }],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

def download_video(url, base, quality):
    if quality == "min":
        format_str = "worstvideo[ext=mp4]+worstaudio/worst"
    else:
        format_str = "bestvideo[ext=mp4]+bestaudio/best"
    opts = {
        "format": format_str,
        "outtmpl": os.path.join(DOWNLOAD_DIR, base),
        "quiet": True,
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

def sanitize_filename(name):
    name = re.sub(r"[^a-zA-Z0-9.]", ".", name)
    name = re.sub(r"\.+", ".", name)
    return name

def response_json(err, audio_file, video_file, age, url):
    return web.Response(
        text=json.dumps({
            "error": err,
            "audio": audio_file,
            "video": video_file,
            "age": age,
            "url": url
        }) + "\n",
        content_type="application/json"
    )

def main():
    app = web.Application()
    app.router.add_post("/", handle_post)
    app.router.add_get("/{filename:.+}", handle_file)
    web.run_app(app, port=80)

if __name__ == "__main__":
    main()


