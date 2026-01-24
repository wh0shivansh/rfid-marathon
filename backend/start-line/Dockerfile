FROM python:3.11-slim

WORKDIR /app

# Copy shared module
COPY ../shared /app/shared

# Copy requirements
COPY ../shared/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "app.py"]
