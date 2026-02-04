FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies
# In the build context `./backend` the requirements file is at the repository root of the context
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend source (copy the whole build context into the image)
COPY . /app/

ENV PYTHONUNBUFFERED=1
EXPOSE 8001

# Run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]
