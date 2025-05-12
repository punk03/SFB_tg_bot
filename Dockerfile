FROM python:3.9-slim

WORKDIR /app

# Установка Git для webhook
RUN apt-get update && apt-get install -y git && apt-get clean

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта в контейнер
COPY . .

# Создаём каталог для логов
RUN mkdir -p logs

# Права на выполнение скриптов
RUN chmod +x *.sh

# Запускаем бота
CMD ["python", "main.py"] 