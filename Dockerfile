FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    TZ=Asia/Shanghai \
    CHROME_PATH=/usr/bin/chromium \
    PROJECTS_ROOT=/app/work

RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY service/requirements.txt /app/service-requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/service-requirements.txt

COPY . /app

RUN mkdir -p /app/work

EXPOSE 8000

CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
