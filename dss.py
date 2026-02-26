# python3 -m py_compile dss.py
# TODO separate golang server for thumbs, downloads and cleaning
# https://github.com/yt-dlp/yt-dlp
import sys, os, string, time, http.server, urllib.parse, json
sys.path.insert(0, "./vendor")
import unidecode, yt_dlp

SP = " "
TAB = "\t"
NL = "\n"
TitleAllowedChars = set(string.ascii_letters + string.digits + ".")
TitleWordsN = 6
YtdlOpts = {
    "quiet": False,
    "js_runtimes": { "deno": { "path": "./deno" } },
}

def perr(msg): print(f"{msg}", file=sys.stderr, flush=True)
def fmtsize(n): return f"{n:,}"
def fmttime(t): return time.strftime('%Y:%m%d:%H%M%S', time.localtime(t))
def sanitize_filename(name):
    name2 = unidecode.unidecode(name)
    name2 = "".join(c if c in TitleAllowedChars else "." for c in name2)
    name2 = ".".join(filter(None, name2.split("."))).strip(".")
    #perr(f"DEBUG sanitize_filename @name [{name2}]")
    return name2

DownloadsDir = os.path.abspath(os.getenv("DownloadsDir", "downloads/"))
os.makedirs(DownloadsDir, exist_ok=True)
DownloadsDirMaxSize = int(os.getenv("DownloadsDirMaxSize", "4123123123"))
perr(f"DEBUG @DownloadsDir [{DownloadsDir}] @DownloadsDirMaxSize <{fmtsize(DownloadsDirMaxSize)}>")

class DSSHandler(http.server.BaseHTTPRequestHandler):
    server_version = "dss/1.0"
    sys_version = ""

    def do_GET(self):

        path = urllib.parse.urlparse(self.path).path
        perr(f"DEBUG GET path [{path}]")

        if path.startswith(("/info/", "/audio/", "/video/", "/thumb/")):

            vurl = path.removeprefix("/info/").removeprefix("/audio/").removeprefix("/video/").removeprefix("/thumb/")
            if not vurl: return self.send_response_err(f"ERROR video url missing", status=400)
            vurl = "https://" + vurl
            perr(f"DEBUG @vurl [{vurl}]")

            try: vinfo = yt_dlp.YoutubeDL(YtdlOpts).extract_info(vurl, download=False)
            except Exception as err: return self.send_response_err(f"ERROR {err}", status=500)

            vid = vinfo.get("id", "nil-id")
            vdate = vinfo.get("upload_date", "nil-date")
            perr(f"DEBUG @vid [{vid}] @vdate [{vdate}]")

        if path.startswith(("/audio/", "/video/", "/thumb/")):

            filename = f"{vid}..{vdate}.."
            vtitle = vinfo.get("title", "nil-title").strip()
            vtitle = ".".join(vtitle.split()[:TitleWordsN])
            filename = filename + sanitize_filename(vtitle) + ".."
            vservice = vinfo.get("extractor_key", "nil-service")
            if vservice != "Youtube": filename = f"{vservice}.." + filename

            if path.startswith("/audio/"): filename = filename + "m4a"
            elif path.startswith("/video/"): filename = filename + "mp4"
            elif path.startswith("/thumb/"): filename = filename + "jpg"
            filepath = os.path.join(DownloadsDir, filename)
            perr(f"DEBUG @filename [{filename}] @filepath [{filepath}]")
            if os.path.isfile(filepath): return self.send_response_redirect(f"/downloads/{filename}")


        if path.startswith("/info/"):
            perr(f"DEBUG GET /info/")
            respbody = json.dumps(vinfo, indent=4, ensure_ascii=False) + NL
            respbody = respbody.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(respbody))
            self.end_headers()
            self.wfile.write(respbody)


        elif path.startswith("/infoaton/"):
            perr(f"DEBUG GET /info/")
            vinfo2 = { k: vinfo.get(k) for k in (
                "id", "title", "thumbnail", "description", "channel_id", "channel_url", "duration", "channel", "uploader", "upload_date", "timestamp", "fulltitle", "epoch", "height", "width", "ext", "vcodec", "acodec", "video_ext", "audio_ext", "resolution", "format", "format_id", "format_note"
            ) }
            respbody = ""
            for k, v in vinfo2.items():
                if isinstance(v, (str)):
                    v = v.replace("]", "\\]").replace(NL, "\\n")
                    respbody += f"@{k} [{v}]" + NL
                if isinstance(v, (int, float, bool)):
                    respbody += f"@{k} <{v}>" + NL
                if isinstance(v, (list)):
                    respbody += f"@{k} (" + SP
                    for lv in v:
                        if isinstance(lv, (str)):
                            lv = lv.replace("]", "\\]").replace(NL, "\\n")
                            respbody += f"[{lv}]" + SP
                        if isinstance(lv, (int, float, bool)):
                            respbody += f"<{lv}>" + SP
                        if isinstance(lv, (list)):
                            respbody += f"( )" + SP
                        if isinstance(lv, (dict)):
                            respbody += f"{{ }}" + SP
                    respbody += ")" + NL
                if isinstance(v, (dict)):
                    respbody += f"@{k} {{" + SP
                    for dk, dv in v.items():
                        if isinstance(dv, (str)):
                            dv = dv.replace("]", "\\]").replace(NL, "\\n")
                            respbody += f"@{dk} [{dv}]" + SP
                        if isinstance(dv, (int, float, bool)):
                            respbody += f"@{dk} <{dv}>" + SP
                        if isinstance(dv, (list)):
                            respbody += f"@{dk} ( )" + SP
                        if isinstance(dv, (dict)):
                            respbody += f"@{dk} {{ }}" + SP
                    respbody += f"}}" + NL
            respbody = respbody.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/aton")
            self.send_header("Content-Length", len(respbody))
            self.end_headers()
            self.wfile.write(respbody)


        elif path.startswith("/audio/"):

            ytdlopts = YtdlOpts | {
                "format": "bestaudio[ext=m4a]",
                "outtmpl": os.path.join(DownloadsDir, filename),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "0",
                }],
            }
            try: yt_dlp.YoutubeDL(ytdlopts).download([vurl])
            except Exception as download_err: return self.send_response_err(f"ERROR {download_err}", status=500)

            if os.path.isfile(filepath): self.send_response_redirect(f"/downloads/{filename}")
            else: self.send_response_err(f"ERROR file [{filename}] not found", status=500)

        elif path.startswith("/video/"):

            ytdlopts = YtdlOpts | {
                "format": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]",
                "outtmpl": os.path.join(DownloadsDir, filename),
                "merge_output_format": "mp4",
            }
            try: yt_dlp.YoutubeDL(ytdlopts).download([vurl])
            except Exception as download_err: return self.send_response_err(f"ERROR {download_err}", status=500)

            if os.path.isfile(filepath): self.send_response_redirect(f"/downloads/{filename}")
            else: self.send_response_err(f"ERROR file [{filename}] not found", status=500)

        elif path.startswith("/thumb/"):

            vthumburl = ""
            vthumbwidth = 0
            for vt in vinfo.get("thumbnails", []):
                vtu = vt.get("url", "")
                if not vtu.endswith(".jpg"): continue
                vtw = vt.get("width", 0)
                if vtw > vthumbwidth:
                    vthumburl = vtu
                    vthumbwidth = vtw
            perr(f"DEBUG @vthumburl [{vthumburl}] @vthumbwidth <{vthumbwidth}>")

            if vthumburl: self.send_response_redirect(vthumburl)
            else: self.send_response_err(f"ERROR vthumburl empty", status=500)

        elif path.startswith("/downloads/"):

            filename = path.removeprefix("/downloads/")
            if "/" in filename: return self.send_response_err(f"HAHA nice try", status=404)

            if not filename:
                ff = []; ffsize = 0
                for f in os.scandir(DownloadsDir):
                    if not f.is_file(): continue
                    fstat = f.stat()
                    ff.append((f.name, fstat.st_size, fstat.st_mtime))
                    ffsize += fstat.st_size
                ff.sort(key=lambda x: x[2])
                perr(f"DEBUG @DownloadsDir [{DownloadsDir}] @size <{fmtsize(ffsize)}> @DownloadsDirMaxSize <{fmtsize(DownloadsDirMaxSize)}>")
                if ffsize > DownloadsDirMaxSize:
                    for f in ff:
                        fpath = os.path.join(DownloadsDir, f[0])
                        perr(f"DEBUG delete @path [{fpath}] @size <{fmtsize(f[1])}> @mtime <{fmttime(f[2])}>")
                        try: os.remove(fpath)
                        except OSError as err: perr(f"ERROR delete @path [{fpath}] {err}")
                        ffsize -= f[1]
                        if ffsize < DownloadsDirMaxSize: break
                self.send_response(200)
                self.send_header("Content-Type", "text/tab-separated-values")
                self.end_headers()
                self.wfile.write(f"@url{TAB}{TAB}@size{TAB}@mtime{NL}".encode("utf-8"))
                for f in ff: self.wfile.write(f"http://{self.headers.get('Host')}/downloads/{f[0]}{TAB}{TAB}<{fmtsize(f[1])}>{TAB}<{fmttime(f[2])}>{NL}".encode("utf-8"))
                self.wfile.write(f"http://{self.headers.get('Host')}/downloads/{TAB}{TAB}<{fmtsize(ffsize)}>{TAB}<>{NL}".encode("utf-8"))
                return

            if filename.endswith(".m4a"): ctype = "audio/mp4"
            elif filename.endswith(".mp4"): ctype = "video/mp4"
            else: return self.send_response_err(f"ERROR invalid file suffix", status=400)

            filepath = os.path.join(DownloadsDir, filename)
            perr(f"DEBUG path [{filepath}]")

            if not os.path.isfile(filepath): return self.send_response_err(f"ERROR file not found", status=404)

            try: clength = os.path.getsize(filepath)
            except Exception as err: return self.send_response_err(f"ERROR get file size {err}", status=500)

            try:
                with open(filepath, "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", clength)
                    self.end_headers()
                    while True:
                        fchunk = f.read(128 * 1024)
                        if not fchunk: break
                        self.wfile.write(fchunk)
            except Exception as err: return self.send_response_err(f"ERROR serve file {err}", status=500)

        else: self.send_response_err(f"ERROR invalid path prefix", status=400)


    def send_response_redirect(self, location, status=302):
        self.send_response(status)
        self.send_header("Location", location)
        self.end_headers()

    def send_response_err(self, err, add_headers={}, status=400):
        perr(f"DEBUG send_response_err @status <{status}> @err [{err}]")
        respbody = f"{err}{NL}".encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", len(respbody))
        for hkey, hval in add_headers.items(): self.send_header(hkey, hval)
        self.end_headers()
        self.wfile.write(respbody)

    def log_message(self, format, *args): pass

    def do_HEAD(self): self.send_response_err(f"GET method only", add_headers=dict(Allow="GET"), status=405)
    def do_POST(self): self.send_response_err(f"GET method only", add_headers=dict(Allow="GET"), status=405)


def main():
    server = http.server.ThreadingHTTPServer(("", 80), DSSHandler)
    perr(f"server listening on :80")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        perr(f"shutting down")
        server.shutdown()

if __name__ == "__main__": main()

