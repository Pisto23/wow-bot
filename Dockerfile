# python:3.13-slim — von discord.py getestete Laufzeit (3.14 ist noch nicht deklariert)
FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# config.yaml / texts.yaml werden per Volume gemountet (siehe compose.yaml)
ENV WOWHELPER_ROOT=/app
CMD ["python", "-m", "wowhelper"]
