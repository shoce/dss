
# https://hub.docker.com/_/python/tags
FROM python:3-alpine

RUN apk add --no-cache ffmpeg

WORKDIR /opt/dss/

COPY dss.py requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

CMD ["python", "dss.py"]

