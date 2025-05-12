#!/bin/bash

# Скрипт для очистки репозитория от ненужных файлов

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Очистка репозитория от ненужных файлов ===${NC}"

# Список файлов, которые необходимо сохранить
ESSENTIAL_FILES=(
    # Основные файлы бота
    "main.py"
    "config.py"
    "loader.py"
    "vk.py"
    "requirements.txt"
    ".gitignore"
    ".dockerignore"
    "README.md"
    
    # Docker-файлы
    "Dockerfile"
    "docker-compose.yml"
    
    # Скрипты для обновления и запуска в Docker
    "update_docker.sh"
    "update_docker.bat"
    "README_DOCKER_UPDATE.md"
    
    # Директории и их содержимое
    "tg_bot/"
    
    # Скрипты запуска
    "start_bot.sh"
    "start_bot.bat"
    "stop_bot.bat"
)

# Дополнительные полезные файлы
USEFUL_FILES=(
    "bot_documentation.md"
    "README_DOCKER.md"
    "check_bot.sh"
)

# Создаем временную директорию для сохранения нужных файлов
TEMP_DIR=$(mktemp -d)
echo -e "${YELLOW}Создана временная директория: ${TEMP_DIR}${NC}"

# Копируем необходимые файлы во временную директорию
echo -e "${YELLOW}Копирование необходимых файлов...${NC}"
for file in "${ESSENTIAL_FILES[@]}" "${USEFUL_FILES[@]}"; do
    if [ -e "$file" ]; then
        # Если это директория, копируем рекурсивно
        if [ -d "$file" ]; then
            mkdir -p "${TEMP_DIR}/$(dirname "$file")"
            cp -r "$file" "${TEMP_DIR}/$(dirname "$file")/"
            echo -e "${GREEN}Скопирована директория: $file${NC}"
        else
            # Создаем директорию для файла, если нужно
            mkdir -p "${TEMP_DIR}/$(dirname "$file")"
            cp "$file" "${TEMP_DIR}/$(dirname "$file")/"
            echo -e "${GREEN}Скопирован файл: $file${NC}"
        fi
    else
        echo -e "${RED}Файл/директория не найден(а): $file${NC}"
    fi
done

# Спрашиваем подтверждение перед удалением
echo -e "${YELLOW}Все необходимые файлы сохранены во временной директории.${NC}"
read -p "Вы уверены, что хотите удалить все остальные файлы? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo -e "${RED}Операция отменена.${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Удаляем все файлы, кроме .git
echo -e "${YELLOW}Удаление ненужных файлов...${NC}"
find . -mindepth 1 -maxdepth 1 -not -path "./.git" -exec rm -rf {} \;

# Копируем необходимые файлы обратно
echo -e "${YELLOW}Копирование необходимых файлов обратно...${NC}"
cp -r "${TEMP_DIR}"/* .

# Удаляем временную директорию
echo -e "${YELLOW}Удаление временной директории...${NC}"
rm -rf "$TEMP_DIR"

# Добавляем изменения в Git
echo -e "${YELLOW}Добавление изменений в Git...${NC}"
git add -A
git commit -m "Удаление ненужных файлов для оптимизации репозитория"

echo -e "${GREEN}Очистка репозитория завершена!${NC}"
echo -e "${GREEN}Используйте 'git push', чтобы отправить изменения на GitHub.${NC}" 