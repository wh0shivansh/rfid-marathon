FROM python:3.10-slim

WORKDIR /app

# Install minimal runtime dependencies used by the proxy
RUN pip install --no-cache-dir fastapi uvicorn httpx python-dotenv

# Copy proxy source
COPY proxy/ /app/

ENV PYTHONUNBUFFERED=1
EXPOSE 9090

CMD ["uvicorn", "rfid_listener:app", "--host", "0.0.0.0", "--port", "9090", "--proxy-headers"]
