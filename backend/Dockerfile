FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV DOE_API_KEY=""
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.api.routes:app --host ${DOE_HOST:-0.0.0.0} --port 8000"]
