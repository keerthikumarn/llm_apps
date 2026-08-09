# Python 3.11+ is required (mem0/schemas use X | None union syntax, PEP 604).
FROM python:3.11-slim

WORKDIR /app

# Install deps first so this layer is cached unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]