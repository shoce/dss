#
# python3 -m py_compile dss.py
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


    def do_HEAD(self, filename):

        perr(f"DEBUG HEAD filename [{filename}]")
        if "/" in filename:
            self.send_response_err(f"HAHA nice try", status=404)
            return

        filepath = os.path.join(DOWNLOAD_DIR, filename)
        perr(f"DEBUG filepath [{filepath}]")

        if not os.path.isfile(filepath):
            perr(f"DEBUG path [{filepath}] file not found")
            self.send_response_err(f"ERROR file not found", status=404)
            return

        try:
            clength = os.path.getsize(filepath)
        except Exception as err:
            self.send_response_err(f"ERROR get file size {err}", status=500)
            return

        if filename.endswith(".m4a"):
            ctype = "audio/mp4"
        elif filename.endswith(".mp4"):
            ctype = "video/mp4"
        else:
            self.send_response_err(f"ERROR invalid file suffix", status=400)
            return

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", clength)
        self.end_headers()


    def do_GET(self):

        path = urllib.parse.urlparse(self.path).path
        perr(f"DEBUG GET path [{path}]")

        if path.startswith("/audio/"):
            self.do_GET_audio(path.removeprefix("/audio/"))
        elif path.startswith("/video/"):
            self.do_GET_video(path.removeprefix("/video/"))
        elif path.startswith("/thumb/"):
            self.do_GET_thumb(path.removeprefix("/thumb/"))
        elif path.startswith("/file/"):
            self.do_GET_file(path.removeprefix("/file/"))
        else:
            self.send_response_err(f"ERROR invalid path prefix", status=400)


    def do_GET_audio(self, url):

        if not url:
           self.send_response_err(f"ERROR missing url", status=400)
           return
        url = "https://" + url
        perr(f"DEBUG @url [{url}]")

        try:
            vinfo = yt_dlp.YoutubeDL(YtdlOpts).extract_info(url, download=False)

            vid = vinfo.get("id", "nil-id")
            vdate = vinfo.get("upload_date", "nil-date")
            perr(f"DEBUG @vid [{vid}] @vdate [{vdate}]")

            filename = f"{vid}..{vdate}.."

            vtitle = vinfo.get("title", "nil-title").strip()
            if vtitle:
                vtitle = ".".join(vtitle.split()[:TitleWordsN])
                filename = filename + f"{vtitle}.."

            vservice = vinfo.get("extractor_key", "nil-service")
            if vservice != "Youtube":
                filename = f"{vservice}.." + filename

            filename = sanitize_filename(filename) + "m4a"
            perr(f"DEBUG @filename [{filename}]")
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            perr(f"DEBUG @filepath [{filepath}]")

            if os.path.isfile(filepath):
                self.send_response_redirect(f"/file/{filename}")
                return

            #yt_dlp.YoutubeDL({"listformats": True}).download([url])

            download_err = download_audio(url, filename)
            if download_err:
                perr(f"ERROR {download_err}")
                self.send_response_err(f"{download_err}", status=500)
                return

            if os.path.isfile(filepath):
                self.send_response_redirect(f"/file/{filename}")
            else:
                self.send_response_err(f"ERROR file [{filename}] not found", status=500)

        except Exception as err:
            self.send_response_err(f"{err}", status=500)
            return


    def do_GET_video(self, url):

        if not url:
           self.send_response_err(f"ERROR missing url", status=400)
           return
        url = "https://" + url
        perr(f"DEBUG @url [{url}]")

        try:
            vinfo = yt_dlp.YoutubeDL(YtdlOpts).extract_info(url, download=False)

            vid = vinfo.get("id", "nil-id")
            vdate = vinfo.get("upload_date", "nil-date")
            perr(f"DEBUG @vid [{vid}] @vdate [{vdate}]")

            filename = f"{vid}..{vdate}.."

            vtitle = vinfo.get("title", "nil-title").strip()
            if vtitle:
                vtitle = ".".join(vtitle.split()[:TitleWordsN])
                filename = filename + f"{vtitle}.."

            vservice = vinfo.get("extractor_key", "nil-service")
            if vservice != "Youtube":
                filename = f"{vservice}.." + filename

            filename = sanitize_filename(filename) + "mp4"
            perr(f"DEBUG @filename [{filename}]")
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            perr(f"DEBUG @filepath [{filepath}]")

            if os.path.isfile(filepath):
                self.send_response_redirect(f"/file/{filename}")
                return

            #yt_dlp.YoutubeDL({"listformats": True}).download([url])

            download_err = download_video(url, filename)
            if download_err:
                perr(f"ERROR {download_err}")
                self.send_response_err(f"{download_err}", status=500)
                return

            if os.path.isfile(filepath):
                self.send_response_redirect(f"/file/{filename}")
            else:
                self.send_response_err(f"ERROR file [{filename}] not found", status=500)

        except Exception as err:
            self.send_response_err(f"{err}", status=500)
            return


    def do_GET_thumb(self, url):

        if not url:
           self.send_response_err(f"ERROR missing url", status=400)
           return
        url = "https://" + url
        perr(f"DEBUG @url [{url}]")

        try:
            vinfo = yt_dlp.YoutubeDL(YtdlOpts).extract_info(url, download=False)

            vthumburl = ""
            vthumbwidth = 0
            for vt in vinfo.get("thumbnails", []):
                vtu = vt.get("url", "")
                if not vtu.endswith(".jpg"):
                    continue
                vtw = vt.get("width", 0)
                if vtw > vthumbwidth:
                    vthumburl = vtu
                    vthumbwidth = vtw
            perr(f"DEBUG @vthumburl [{vthumburl}] @vthumbwidth <{vthumbwidth}>")

            if not vthumburl:
                self.send_response_err(f"ERROR vthumburl empty", status=500)
                return

            self.send_response_redirect(vthumburl)

        except Exception as err:
            self.send_response_err(f"{err}", status=500)
            return


    def send_response_redirect(self, location, status=302):
        self.send_response(status)
        self.send_header("Location", location)
        self.end_headers()


    def do_GET_file(self, filename):

        if "/" in filename:
            self.send_response_err(f"HAHA nice try", status=404)
            return

        if filename.endswith(".m4a"):
            ctype = "audio/mp4"
        elif filename.endswith(".mp4"):
            ctype = "video/mp4"
        else:
            self.send_response_err(f"ERROR invalid file suffix", status=400)
            return

        filepath = os.path.join(DOWNLOAD_DIR, filename)
        perr(f"DEBUG path [{filepath}]")

        if not os.path.isfile(filepath):
            self.send_response_err(f"ERROR file not found", status=404)
            return

        try:
            clength = os.path.getsize(filepath)
        except Exception as err:
            self.send_response_err(f"ERROR get file size {err}", status=500)
            return

        try:
            with open(path, "rb") as f:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", clength)
                self.end_headers()
                self.wfile.write(f.read())
        except Exception as err:
            self.send_response_err(f"ERROR read file {err}", status=500)
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


def download_audio(url, filename):
    opts = YtdlOpts | {
        "quiet": False,
        "format": "bestaudio[ext=m4a]",
        "outtmpl": os.path.join(DOWNLOAD_DIR, filename),
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


def download_video(url, filename):
    opts = YtdlOpts | {
        "quiet": False,
        "format": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]",
        "outtmpl": os.path.join(DOWNLOAD_DIR, filename),
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


