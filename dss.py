import os
import re
import json
from aiohttp import web

import yt_dlp

DOWNLOAD_DIR = os.path.abspath("downloads/")

async def handle_post(request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return response_json("Invalid JSON", None, None)

    url = data.get("url")
    audio_q = data.get("audio_quality")
    video_q = data.get("video_quality")

    if not url:
        return response_json('Missing "url"', None, None)

    try:
        service = extract_service_name(url)
        video_id = extract_video_id(url)
        base = sanitize_filename(f"{service}..{video_id}.")
        audio_file = base+".m4a" if audio_q else None
        video_file = base+".mp4" if video_q else None

        if audio_q and not os.path.isfile(os.path.join(DOWNLOAD_DIR, audio_file)):
            download_audio(url, base, audio_q)

        if video_q and not os.path.isfile(os.path.join(DOWNLOAD_DIR, video_file)):
            download_video(url, base, video_q)

        return response_json("", audio_file, video_file)

    except Exception as e:
        return response_json(str(e), None, None)

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
    ctype = "audio/mp4" if filename.endswith(".m4a") else "video/mp4"
    return web.FileResponse(path=path, headers={"Content-Type": ctype})

def extract_service_name(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("extractor_key", "unknown")

def extract_video_id(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        video_id = info.get("id")
        if not video_id:
            raise Exception("Unable to extract video ID")
        return video_id

def download_audio(url, base, quality):
    format_str = "worstaudio[ext=m4a]/worstaudio" if quality == "min" else "bestaudio[ext=m4a]/bestaudio"
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
    format_str = "worstvideo[ext=mp4]+worstaudio/worst" if quality == "min" else "bestvideo[ext=mp4]+bestaudio/best"
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
    name = re.sub(r"\\.+", ".", name)
    return name

def response_json(err, audio_file, video_file):
    return web.Response(
        text=json.dumps(
            {
            "error": err,
            "audio": audio_file,
            "video": video_file
            },
            ensure_ascii=False
            ) + "\n",
        content_type="application/json"
    )

def main():
    app = web.Application()
    app.router.add_post("/", handle_post)
    app.router.add_get("/{filename:.+}", handle_file)
    web.run_app(app, port=80)

if __name__ == "__main__":
    main()


