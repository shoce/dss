#
# python3 -m py_compile dss.py
# python3 -m compileall dss.py
# pylint dss.py
#


import asyncio
import os
import re
import time
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote
import threading

import yt_dlp



SP = " "
TAB = "\t"
NL = "\n"
N = ""

DOWNLOAD_DIR = os.path.abspath("downloads/")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

download_tasks = {}
download_start_times = {}
download_locks = defaultdict(asyncio.Lock)


class DSSHandler(BaseHTTPRequestHandler):
    server_version = "dss/1.0"

    def do_POST(self):
        if self.path != "/":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            reqtext = self.rfile.read(content_length).decode('utf-8')
        except Exception as err:
            self.send_response_text(f"reading request body {err}", status=400)
            return

        reqwords = reqtext.split()
        if not reqwords:
            self.send_response_text("empty request body", status=400)
            return
        if len(reqwords) > 6:
            self.send_response_text("request body has more than three pairs (six words)", status=400)
            return
        if len(reqwords) % 2 != 0:
            self.send_response_text("request body has odd number of words", status=400)
            return

        url = None
        aq = None
        vq = None

        for i in range(0, len(reqwords), 2):
            k, v = reqwords[i], reqwords[i+1]
            if not k.startswith("@"):
                self.send_response_text(f"key [{k}] must start with @", status=400)
                return
            if len(k) < 2:
                self.send_response_text(f"key word number {i} name is empty", status=400)
                return
            k = k[1:]
            if k == "url":
                url = v
            elif k == "aq":
                aq = v
            elif k == "vq":
                vq = v
            else:
                self.send_response_text(f"invalid key name @{k}", status=400)
                return

        if not url:
            self.send_response_text("missing @url", status=400)
            return

        if not aq and not vq:
            aq = "max"
        if not vq:
            vq = ""

        if not aq and not vq:
            self.send_response_data(url=url, err="missing both @aq and @vq", status=400)
            return

        url = url.removeprefix("http://").removeprefix("https://")
        url = "https://" + url

        print(
            f"{NL}"
            f"request {{ {NL}"
            f"{TAB}@url [{url}] {NL}"
            f"{TAB}@aq [{aq}] {NL}"
            f"{TAB}@vq [{vq}] {NL}"
            f"}} {NL}"
        )

        try:
            service, video_id = extract_video_info(url)
            base = sanitize_filename(f"{service}..{video_id}..")
            afile = base + f"{aq}..m4a" if aq else None
            vfile = base + f"{vq}..mp4" if vq else None

            now = time.time()
            download_key = f"service {service} video_id {video_id} aq {aq} vq {vq}"

            age = None
            if download_key in download_start_times:
                age = now - download_start_times[download_key]

            if download_key not in download_tasks:
                download_start_times[download_key] = now
                yt_dlp.YoutubeDL({"listformats": True}).download([url])

                future = asyncio.run_coroutine_threadsafe(
                    do_download(download_key, url, afile, aq, vfile, vq),
                    loop
                )
                download_tasks[download_key] = {
                    "task": future,
                    "err": None,
                }
                age = 0

            audio_path = os.path.join(DOWNLOAD_DIR, afile) if afile else None
            audio_ready = os.path.isfile(audio_path) if audio_path else False

            video_path = os.path.join(DOWNLOAD_DIR, vfile) if vfile else None
            video_ready = os.path.isfile(video_path) if video_path else False

            download_err = download_tasks[download_key]["err"]

            self.send_response_data(
                err=str(download_err) if download_err else None,
                url=url,
                age=format_duration(age) if age is not None else None,
                afile=afile if audio_ready else None,
                vfile=vfile if video_ready else None,
            )

        except Exception as err:
            self.send_response_data(url=url, err=f"{err}", status=500)

    def do_GET(self):
        filename = unquote(self.path.lstrip('/'))
        print(f"DEBUG filename=={filename}")

        if filename.endswith(".m4a"):
            ctype = "audio/mp4"
        elif filename.endswith(".mp4"):
            ctype = "video/mp4"
        else:
            ctype = "application/octet-stream"

        path = os.path.join(DOWNLOAD_DIR, filename)
        print(f"DEBUG path=={path}")

        if not os.path.isfile(path):
            print(f"DEBUG path=={path} file does not exist")
            self.send_error(404, "file not found")
            return

        try:
            with open(path, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', os.path.getsize(path))
                self.end_headers()
                self.wfile.write(f.read())
        except Exception as e:
            self.send_error(500, f"error reading file {e}")

    def send_response_text(self, err, status=400):
        self.send_response_data(err=err, status=status)

    def send_response_data(self, url=None, err=None, age=None, afile=None, vfile=None, status=200):
        if url is None:
            url = ""
        if err is None:
            err = ""
        if age is None:
            age = ""
        if afile is None:
            afile = ""
        if vfile is None:
            vfile = ""

        body = (
            f"@url [{url}] {N}"
            f"@age [{age}] {N}"
            f"@afile [{afile}] {N}"
            f"@vfile [{vfile}] {N}"
            f"@err [{err}] {N}"
            f"{NL}"
        )

        self.send_response(status)
        self.send_header('Content-Type', 'application/aton')
        self.send_header('Content-Length', len(body.encode()))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, format, *args):
        pass


def extract_video_info(url):
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
            await asyncio.to_thread(download_audio, key, url, afile, aq)
        if vq:
            await asyncio.to_thread(download_video, key, url, vfile, vq)


def download_audio(key, url, afile, aq):
    if aq == "min":
        format_str = "worstaudio[ext=m4a]"
    else:
        format_str = "bestaudio[ext=m4a]"
    opts = {
        "quiet": False,
        "format": format_str,
        "outtmpl": os.path.join(DOWNLOAD_DIR, afile),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "0",
        }],
    }
    try:
        yt_dlp.YoutubeDL(opts).download([url])
    except Exception as download_err:
        print(f"download err: {download_err}")
        download_tasks[key]["err"] = download_err


def download_video(key, url, vfile, vq):
    if vq == "min":
        format_str = "worstvideo[vcodec^=avc1]"
    elif vq == "avg":
        format_str = "bestvideo[vcodec^=avc1][height<=720][fps<=30]"
    else:
        format_str = "bestvideo[vcodec^=avc1]"
    format_str += "+bestaudio[ext=m4a]"
    print(f"DEBUG download_video format_str=={format_str}")
    opts = {
        "quiet": False,
        "format": format_str,
        "outtmpl": os.path.join(DOWNLOAD_DIR, vfile),
        "merge_output_format": "mp4",
    }
    try:
        yt_dlp.YoutubeDL(opts).download([url])
    except Exception as download_err:
        print(f"download err: {download_err}")
        download_tasks[key]["err"] = download_err


def sanitize_filename(name):
    name = re.sub(r"[^a-zA-Z0-9_.-]", ".", name)
    #name = re.sub(r"\.+", ".", name)
    return name


def format_duration(seconds):
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}m{secs}s"


def run_async_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()


loop = asyncio.new_event_loop()


def main():
    async_thread = threading.Thread(target=run_async_loop, daemon=True)
    async_thread.start()

    server = HTTPServer(('', 80), DSSHandler)
    print("server running on port 80")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"{NL}shutting down")
        server.shutdown()
        loop.stop()


if __name__ == "__main__":
    main()


