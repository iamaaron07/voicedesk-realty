FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh","-c","python -m alembic -c alembic.ini upgrade head && python seed_database.py && uvicorn app:app --host 0.0.0.0 --port 8000"]
