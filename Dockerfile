
# https://hub.docker.com/_/python/tags
FROM python:3-slim
RUN apt update
RUN apt install -y ffmpeg

WORKDIR /dss/
COPY dss.py requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt install -y curl
RUN curl https://zyedidia.github.io/eget.sh | sh
RUN mv eget /bin/eget
RUN eget --asset=deno-aarch64-unknown-linux-gnu denoland/deno
RUN mv deno /bin/deno
RUN deno --version

EXPOSE 80
CMD ["python", "dss.py"]

