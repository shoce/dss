#
# python3 -m py_compile dss.py
# python3 -m compileall dss.py
# pylint dss.py
#

import asyncio
import os
import re
import yaml
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
        data = await request.post()
    except Exception as err:
        return response(err=f"invalid form data: {err}", status=400)

    url = data.get("url")
    if url:
        url = url.removeprefix("http://").removeprefix("https://")
    aq = data.get("aq")
    vq = data.get("vq")

    if not url:
        return response(err='missing "url"', status=400)

    if not aq and not vq:
        return response(url=url, err='missing both "aq" and "vq"', status=400)

    try:
        service, video_id = await extract_video_info(url)
        base = sanitize_filename(f"{service}..{video_id}..")
        afile = base + "m4a" if aq else None
        vfile = base + "mp4" if vq else None

        now = time.time()
        download_key = f"base={base} aq={aq} vq={vq}"
        age = None

        if download_key in download_start_times:
            age = now - download_start_times[download_key]

        # Launch background task if not running
        if download_key not in download_tasks:
            download_start_times[download_key] = now
            download_tasks[download_key] = asyncio.create_task(
                do_download(download_key, url, afile, aq, vfile, vq)
            )
            age = 0

        audio_path = os.path.join(DOWNLOAD_DIR, afile) if afile else None
        audio_ready = os.path.isfile(audio_path) if audio_path else False

        video_path = os.path.join(DOWNLOAD_DIR, vfile) if vfile else None
        video_ready = os.path.isfile(video_path) if video_path else False

        return response(
            url = url,
            age = format_duration(age) if age is not None else None,
            afile = afile if audio_ready else None,
            vfile = vfile if video_ready else None,
        )

    except Exception as err:
        return response(url=url, err=f"{err}", status=500)

async def extract_video_info(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        service = info.get("extractor_key", "unknown")
        video_id = info.get("id")
        if not video_id:
            raise Exception("Unable to extract video ID")
        return service, video_id

async def do_download(key, url, afile, aq, vfile, vq):
    async with download_locks[key]:
        if aq:
            await asyncio.to_thread(download_audio, url, afile, aq)
        if vq:
            await asyncio.to_thread(download_video, url, vfile, vq)
        del download_tasks[key]

async def handle_file(request):
    filename = request.match_info["filename"]
    print(f"DEBUG filename=={filename}")
    if not re.match(r"^[a-zA-Z0-9.]+$", filename):
        print(f"DEBUG filename=={filename} not matching regexp")
        return web.Response(status=400, text="invalid filename")
    if filename.endswith(".m4a"):
        ctype = "audio/mp4"
    elif filename.endswith(".mp4"):
        ctype = "video/mp4"
    else:
        ctype = "video/mp4"
    path = os.path.join(DOWNLOAD_DIR, filename)
    print(f"DEBUG path=={path}")
    if not os.path.isfile(path):
        print(f"DEBUG path=={path} file does not exist")
        return web.Response(status=404, text="file not found")
    return web.FileResponse(path=path, headers={"Content-Type": ctype})

def download_audio(url, afile, aq):
    if aq == "min":
        format_str = "worstaudio[ext=m4a]/worstaudio"
    else:
        format_str = "bestaudio[ext=m4a]/bestaudio"
    opts = {
        "format": format_str,
        "outtmpl": os.path.join(DOWNLOAD_DIR, afile),
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "0",
        }],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

def download_video(url, vfile, vq):
    if vq == "min":
        format_str = "worstvideo[ext=mp4]+worstaudio/worst"
    elif vq == "avg":
        format_str = "best[height<=720][fps<=30][ext=mp4]+bestaudio/best"
    else:
        format_str = "bestvideo[ext=mp4]+bestaudio/best"
    opts = {
        "format": format_str,
        "outtmpl": os.path.join(DOWNLOAD_DIR, vfile),
        "quiet": True,
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

def sanitize_filename(name):
    name = re.sub(r"[^a-zA-Z0-9.]", ".", name)
    name = re.sub(r"\.+", ".", name)
    return name

def response(url=None, err=None, age=None, afile=None, vfile=None, status=200):
    return web.Response(
        status = status,
        text = yaml.dump(
            data = {
                "url": url,
                "err": err,
                "age": age,
                "a": afile,
                "v": vfile,
            },
            sort_keys = False,
            explicit_start = True,
            allow_unicode = True,
        ),
        content_type = "application/x-yaml"
    )

def main():
    app = web.Application()
    app.router.add_post("/", handle_post)
    app.router.add_get("/{filename:.+}", handle_file)
    web.run_app(app, port=80)

if __name__ == "__main__":
    main()


