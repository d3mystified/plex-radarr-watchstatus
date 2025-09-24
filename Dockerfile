FROM python:3.13-slim-bookworm AS builder
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.13-slim-bookworm
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY main.py .
ENV PATH="/opt/venv/bin:$PATH"
CMD ["python", "main.py"]