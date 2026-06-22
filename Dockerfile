FROM python:3.11.2-slim AS builder
WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
	PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install -r requirements.txt

FROM python:3.11.2-slim
WORKDIR /home/frlbot

ENV PATH="/opt/venv/bin:$PATH" \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv
COPY frlbot.py ./

CMD ["python", "./frlbot.py"]