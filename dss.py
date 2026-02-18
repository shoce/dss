#
# python3 -m py_compile dss.py
# python3 -m compileall dss.py
# pylint dss.py
#

import sys
import os
import re

import http.server
import urllib.parse

sys.path.insert(0, "./vendor")

# https://github.com/yt-dlp/yt-dlp
import yt_dlp



SP = " "
TAB = "\t"
NL = "\n"
N = ""

TitleWordsN = 6

YtdlOpts = {
    "quiet": False,
    "js_runtimes": {
        "deno": {
            "path": "./deno",
        },
    },
}

DOWNLOAD_DIR = os.path.abspath("downloads/")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)



class DSSHandler(http.server.BaseHTTPRequestHandler):
    server_version = "dss/1.0"
    sys_version = ""


    def GET_method_only(self): self.send_response_err(f"GET method only", add_headers=dict(Allow="GET"), status=405)
    def do_POST(self): self.GET_method_only()
    def do_PUT(self): self.GET_method_only()
    def do_DELETE(self): self.GET_method_only()
    def do_PATCH(self): self.GET_method_only()
    def do_OPTIONS(self): self.GET_method_only()


    def do_HEAD(self):

        filename = urllib.parse.unquote(self.path.lstrip("/"))
        perr(f"DEBUG HEAD filename [{filename}]")
        if "/" in filename:
            self.send_response_err(f"ERROR haha nice try", status=404)
            return

        path = os.path.join(DOWNLOAD_DIR, filename)
        perr(f"DEBUG path [{path}]")

        if not os.path.isfile(path):
            perr(f"DEBUG path [{path}] file does not exist")
            self.send_response_err(f"ERROR file not found", status=404)
            return

        try:
            clength = os.path.getsize(path)
        except Exception as err:
            self.send_response_err(f"ERROR get file size {err}", status=500)
            return

        if filename.endswith(".m4a"):
            ctype = "audio/mp4"
        elif filename.endswith(".mp4"):
            ctype = "video/mp4"
        else:
            ctype = "application/octet-stream"

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", clength)
        self.end_headers()


    def do_GET(self):

        path = urllib.parse.urlparse(self.path).path
        perr(f"DEBUG GET path [{path}]")

        if path == "/":
            self.do_GET_url()
        else:
            self.do_GET_file()


    def do_GET_url(self):

        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        url = params.get("url", [None])[-1]
        if not url:
            self.send_response_err(f"missing @url", status=400)
            return
        url = url.removeprefix("http://").removeprefix("https://")
        url = "https://" + url

        aq = params.get("aq", [None])[-1]
        vq = params.get("vq", [None])[-1]
        if not aq and not vq:
            aq = "max"
        if not vq:
            vq = ""

        perr(f"@request {{ @url [{url}] @aq [{aq}] @vq [{vq}] }}")

        if not aq and not vq:
            self.send_response_err(f"both @aq and @vq missing", status=400)
            return

        try:
            vinfo = yt_dlp.YoutubeDL(YtdlOpts).extract_info(url, download=False)
            vid = vinfo.get("id", "nil-id")
            vdate = vinfo.get("upload_date", "nil-date")

            filename = f"{vid}..{vdate}.."
            vtitle = vinfo.get("title", "nil-title").strip()
            if vtitle:
                vtitle = ".".join(vtitle.split()[:TitleWordsN])
                filename = filename + f"{vtitle}.."
            vservice = vinfo.get("extractor_key", "nil-service")
            if vservice != "Youtube":
                filename = f"{vservice}.." + filename
            filename = sanitize_filename(filename)

            afile = filename + "m4a" if aq else None
            vfile = filename + "mp4" if vq else None
            perr(f"DEBUG @afile [{afile}] @vfile [{vfile}]")

            audio_path = os.path.join(DOWNLOAD_DIR, afile) if afile else None
            video_path = os.path.join(DOWNLOAD_DIR, vfile) if vfile else None
            perr(f"DEBUG @audio_path [{audio_path}] @video_path [{video_path}]")

            if video_path and os.path.isfile(video_path):
                self.send_response_redirect(f"/{vfile}")
                return
            if audio_path and os.path.isfile(audio_path):
                self.send_response_redirect(f"/{afile}")
                return

            yt_dlp.YoutubeDL({"listformats": True}).download([url])

            download_err = None
            if vfile:
                download_err = download_video(url, vfile, vq)
            if afile:
                download_err = download_audio(url, afile, aq)

            if download_err:
                perr(f"ERROR {download_err}")
                self.send_response_err(f"{download_err}", status=500)
                return

            if video_path and os.path.isfile(video_path):
                self.send_response_redirect(f"/{vfile}")
                return
            if audio_path and os.path.isfile(audio_path):
                self.send_response_redirect(f"/{afile}")
                return

            self.send_response_err(f"ERROR both audio and video files are missing", status=202)
            return

        except Exception as err:
            self.send_response_err(f"{err}", status=500)
            return


    def send_response_redirect(self, filepath, status=302):
        self.send_response(status)
        self.send_header("Location", filepath)
        self.end_headers()


    def do_GET_file(self):

        filename = urllib.parse.unquote(self.path.lstrip("/"))
        perr(f"DEBUG filename [{filename}]")
        if "/" in filename:
            self.send_response_err(f"ERROR haha nice try", status=404)
            return

        path = os.path.join(DOWNLOAD_DIR, filename)
        perr(f"DEBUG path [{path}]")

        if not os.path.isfile(path):
            perr(f"DEBUG path [{path}] file does not exist")
            self.send_response_err(f"ERROR file not found", status=404)
            return

        try:
            clength = os.path.getsize(path)
        except Exception as err:
            self.send_response_err(f"ERROR get file size {err}", status=500)
            return

        if filename.endswith(".m4a"):
            ctype = "audio/mp4"
        elif filename.endswith(".mp4"):
            ctype = "video/mp4"
        else:
            ctype = "application/octet-stream"

        try:
            with open(path, "rb") as f:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", clength)
                self.end_headers()
                self.wfile.write(f.read())
        except Exception as err:
            self.send_response_err(f"ERROR reading file {err}", status=500)
            return


    def send_response_err(self, err, add_headers={}, status=400):
        perr(f"DEBUG send_response_err @status <{status}> @err [{err}]")
        respbody = f"{err}{NL}".encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", len(respbody))
        for hkey, hval in add_headers.items():
            self.send_header(hkey, hval)
        self.end_headers()
        self.wfile.write(respbody)


    def log_message(self, format, *args):
        pass


def download_audio(url, afile, aq):
    if aq == "min":
        format_str = "worstaudio[ext=m4a]"
    else:
        format_str = "bestaudio[ext=m4a]"
    opts = YtdlOpts | {
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
        return download_err


def download_video(url, vfile, vq):
    if vq == "min":
        format_str = "worstvideo[vcodec^=avc1]"
    elif vq == "avg":
        format_str = "bestvideo[vcodec^=avc1][height<=720][fps<=30]"
    else:
        format_str = "bestvideo[vcodec^=avc1]"
    format_str += "+bestaudio[ext=m4a]"
    perr(f"DEBUG download_video format_str [{format_str}]")
    opts = YtdlOpts | {
        "quiet": False,
        "format": format_str,
        "outtmpl": os.path.join(DOWNLOAD_DIR, vfile),
        "merge_output_format": "mp4",
    }
    try:
        yt_dlp.YoutubeDL(opts).download([url])
    except Exception as download_err:
        return download_err


def sanitize_filename(name):
    name = re.sub(r"[^a-zA-Z0-9_.-]", ".", name)
    name = re.sub(r"\.\.+", "..", name)
    return name


def perr(msg):
    print(f"{msg}", file=sys.stderr, flush=True)


def main():
    server = http.server.HTTPServer(("", 80), DSSHandler)
    perr("server listening on :80")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        perr(f"shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()


