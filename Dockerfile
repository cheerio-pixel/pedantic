FROM python:3.11-alpine AS builder

# First install all dependencies
RUN apk update \
    && apk add --no-cache python3-dev build-base pkgconfig
    # && rm -rf /var/lib/apt/lists/*

# Then copy the requirements
COPY requirements.txt /app/

WORKDIR /app/


RUN pip install --require-hashes --no-deps --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]


