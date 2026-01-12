# Dockerfile для Python приложения
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Порт, который будет слушать приложение
EXPOSE 8000

# Команда для запуска приложения

# ИЛИ если используете FastAPI/Uvicorn:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]