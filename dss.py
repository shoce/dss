# python3 -m py_compile dss.py
import sys
import os
import re
import http.server
import urllib.parse
sys.path.insert(0, "./vendor")
import unidecode
# https://github.com/yt-dlp/yt-dlp
import yt_dlp

NL = "\n"
TitleWordsN = 6
YtdlOpts = {
    "quiet": False,
    "js_runtimes": { "deno": { "path": "./deno" } },
}

def perr(msg):
    print(f"{msg}", file=sys.stderr, flush=True)

DOWNLOAD_DIR = os.path.abspath("downloads/")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
DOWNLOAD_DIR_MAX_SIZE = int(os.getenv("DOWNLOAD_DIR_MAX_SIZE", "4123123123"))
perr(f"DEBUG @DOWNLOAD_DIR [{DOWNLOAD_DIR}] @DOWNLOAD_DIR_MAX_SIZE <{DOWNLOAD_DIR_MAX_SIZE}>")

class DSSHandler(http.server.BaseHTTPRequestHandler):
    server_version = "dss/1.0"
    sys_version = ""

    def do_GET(self):

        path = urllib.parse.urlparse(self.path).path
        perr(f"DEBUG GET path [{path}]")

        if path.startswith(("/audio/", "/video/", "/thumb/")):

            url = path.removeprefix("/audio/").removeprefix("/video/").removeprefix("/thumb/")
            if not url:
               self.send_response_err(f"ERROR missing url", status=400)
               return
            url = "https://" + url
            perr(f"DEBUG @url [{url}]")

            try:
                vinfo = yt_dlp.YoutubeDL(YtdlOpts).extract_info(url, download=False)
            except Exception as err:
                self.send_response_err(f"ERROR {err}", status=500)
                return

            vid = vinfo.get("id", "nil-id")
            vdate = vinfo.get("upload_date", "nil-date")
            perr(f"DEBUG @vid [{vid}] @vdate [{vdate}]")
            filename = f"{vid}..{vdate}.."
            vtitle = vinfo.get("title", "nil-title").strip()
            vtitle = ".".join(vtitle.split()[:TitleWordsN])
            filename = filename + f"{vtitle}.."
            vservice = vinfo.get("extractor_key", "nil-service")
            if vservice != "Youtube":
                filename = f"{vservice}.." + filename
            filename = sanitize_filename(filename)

            if path.startswith("/audio/"):
                filename = filename + "m4a"
            elif path.startswith("/video/"):
                filename = filename + "mp4"
            elif path.startswith("/thumb/"):
                filename = filename + "jpg"
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            perr(f"DEBUG @filename [{filename}] @filepath [{filepath}]")
            if os.path.isfile(filepath):
                self.send_response_redirect(f"/file/{filename}")
                return


        if path.startswith("/audio/"):

            ytdlopts = YtdlOpts | {
                "format": "bestaudio[ext=m4a]",
                "outtmpl": os.path.join(DOWNLOAD_DIR, filename),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "0",
                }],
            }
            try:
                yt_dlp.YoutubeDL(ytdlopts).download([url])
            except Exception as download_err:
                self.send_response_err(f"ERROR {download_err}", status=500)
                return

            if os.path.isfile(filepath):
                self.send_response_redirect(f"/file/{filename}")
            else:
                self.send_response_err(f"ERROR file [{filename}] not found", status=500)

        elif path.startswith("/video/"):

            ytdlopts = YtdlOpts | {
                "format": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]",
                "outtmpl": os.path.join(DOWNLOAD_DIR, filename),
                "merge_output_format": "mp4",
            }
            try:
                yt_dlp.YoutubeDL(ytdlopts).download([url])
            except Exception as download_err:
                self.send_response_err(f"ERROR {download_err}", status=500)
                return

            if os.path.isfile(filepath):
                self.send_response_redirect(f"/file/{filename}")
            else:
                self.send_response_err(f"ERROR file [{filename}] not found", status=500)

        elif path.startswith("/thumb/"):

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

        elif path.startswith("/file/"):

            filename = path.removeprefix("/file/")
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
                with open(filepath, "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", clength)
                    self.end_headers()
                    while True:
                        fchunk = f.read(128 * 1024)
                        if not fchunk:
                            break
                        self.wfile.write(fchunk)
            except Exception as err:
                self.send_response_err(f"ERROR serve file {err}", status=500)
                return

            ff = []
            ffsize = 0
            for f in os.scandir(DOWNLOAD_DIR):
                if f.is_file():
                    fstat = f.stat()
                    ff.append((f.name, fstat.st_size, fstat.st_mtime))
                    ffsize += fstat.st_size
            perr(f"DEBUG @DOWNLOAD_DIR [{DOWNLOAD_DIR}] total files size <{ffsize}>")
            if ffsize > DOWNLOAD_DIR_MAX_SIZE:
                ff.sort(key=lambda x: x[2])
                for f in ff:
                    fpath = os.path.join(DOWNLOAD_DIR, f[0])
                    perr(f"DEBUG delete @path [{fpath}] @size <{f[1]}> @mtime <{f[2]}>")
                    try:
                        os.remove(fpath)
                    except OSError as err:
                        perr(f"ERROR delete @path [{fpath}] {err}")
                    ffsize -= f[1]
                    if ffsize < DOWNLOAD_DIR_MAX_SIZE:
                        break

        else:

            self.send_response_err(f"ERROR invalid path prefix", status=400)


    def send_response_redirect(self, location, status=302):
        self.send_response(status)
        self.send_header("Location", location)
        self.end_headers()

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

    def do_HEAD(self): self.send_response_err(f"GET method only", add_headers=dict(Allow="GET"), status=405)
    def do_POST(self): self.send_response_err(f"GET method only", add_headers=dict(Allow="GET"), status=405)


def sanitize_filename(name):
    perr(f"DEBUG sanitize_filename @name [{name}]")
    name = unidecode.unidecode(name)
    perr(f"DEBUG sanitize_filename @name [{name}]")
    name = re.sub(r"[^a-zA-Z0-9_.-]", ".", name)
    perr(f"DEBUG sanitize_filename @name [{name}]")
    name = re.sub(r"\.\.+", "..", name)
    perr(f"DEBUG sanitize_filename @name [{name}]")
    return name

def main():
    server = http.server.HTTPServer(("", 80), DSSHandler)
    perr(f"server listening on :80")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        perr(f"shutting down")
        server.shutdown()

if __name__ == "__main__":
    main()

