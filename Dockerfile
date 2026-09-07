FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV WOWHELPER_ROOT=/app
CMD ["python", "-m", "wowhelper"]
