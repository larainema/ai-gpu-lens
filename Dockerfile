FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

COPY LICENSE README.md pyproject.toml ./
COPY src ./src
COPY examples ./examples

ENTRYPOINT ["python", "-m", "ai_gpu_lens"]
