# https://hub.docker.com/_/python/tags
FROM python:3-slim

WORKDIR /opt/dss

RUN apt-get update
RUN apt-get install -y ffmpeg
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY dss.py .

EXPOSE 80

CMD ["python", "dss.py"]

