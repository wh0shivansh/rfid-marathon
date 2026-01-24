FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY ../requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY proxy.py .

# Expose port
EXPOSE 9090

# Run application
CMD ["python", "proxy.py"]
