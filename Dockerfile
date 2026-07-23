# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    binutils \
    libproj-dev \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Django GIS loads libgdal via ctypes
ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so \
    GEOS_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgeos_c.so

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/staticfiles /app/media \
    && chmod +x /app/deploy/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
# Render sets $PORT; local/docker default 8000
CMD ["sh", "-c", "gunicorn tanzania_gis.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120"]
