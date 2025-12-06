
# https://hub.docker.com/_/python/tags
FROM python:3-slim
RUN apt update
RUN apt install -y --no-install-recommends ffmpeg

WORKDIR /dss/
COPY dss.py requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt install -y --no-install-recommends curl
RUN curl https://zyedidia.github.io/eget.sh | sh
RUN mv eget /bin/eget
RUN eget --asset=deno- denoland/deno
RUN mv deno /bin/deno
RUN deno --version

RUN apt clean
RUN rm -rf /var/lib/apt/lists/*

EXPOSE 80
CMD ["python", "dss.py"]

