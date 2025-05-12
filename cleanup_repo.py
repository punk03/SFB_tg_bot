#!/usr/bin/env python3
"""
Скрипт для очистки репозитория от ненужных файлов
"""

import os
import shutil
import glob

# Файлы, необходимые для работы бота
ESSENTIAL_FILES = [
    # Основные файлы бота
    "main.py",
    "config.py",
    "loader.py",
    "vk.py",
    "requirements.txt",
    ".gitignore",
    ".dockerignore",
    "README.md",
    
    # Docker-файлы
    "Dockerfile",
    "docker-compose.yml",
    
    # Скрипты для обновления и запуска в Docker
    "update_docker.sh",
    "update_docker.bat",
    "README_DOCKER_UPDATE.md",
    
    # Директории
    "tg_bot/",
    "tg_bot/buttons.py",
    "tg_bot/states.py",
    "tg_bot/handlers.py",
    "tg_bot/tg_bot.py",
    "tg_bot/__init__.py",
    
    # Скрипты запуска
    "start_bot.sh",
    "start_bot.bat",
    "stop_bot.bat",
]

# Файлы, которые могут быть полезны, но не обязательны для работы бота
USEFUL_BUT_NOT_ESSENTIAL = [
    "bot_documentation.md",
    "README_DOCKER.md",
    "check_bot.sh",
]

def cleanup_repo():
    """Очистка репозитория от ненужных файлов"""
    print("Анализ файлов репозитория...")
    
    # Получаем список всех файлов и директорий, исключая .git и __pycache__
    all_files = []
    for root, dirs, files in os.walk('.', topdown=True):
        # Исключаем скрытые директории и __pycache__
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for file in files:
            if not file.startswith('.git'):
                file_path = os.path.join(root, file)
                # Преобразуем путь к формату с прямыми слешами
                file_path = file_path.replace('\\', '/').lstrip('./')
                all_files.append(file_path)
    
    # Файлы для удаления
    files_to_remove = []
    for file_path in all_files:
        # Проверяем, является ли файл обязательным
        is_essential = False
        for essential_path in ESSENTIAL_FILES:
            if file_path == essential_path or file_path.startswith(essential_path.rstrip('/') + '/'):
                is_essential = True
                break
        
        # Проверяем, является ли файл полезным
        is_useful = False
        for useful_path in USEFUL_BUT_NOT_ESSENTIAL:
            if file_path == useful_path or file_path.startswith(useful_path.rstrip('/') + '/'):
                is_useful = True
                break
        
        # Если файл не обязательный и не полезный, добавляем его в список для удаления
        if not is_essential and not is_useful:
            files_to_remove.append(file_path)
    
    # Выводим список файлов для удаления
    print(f"Найдено {len(files_to_remove)} файлов для удаления:")
    for file_path in sorted(files_to_remove):
        print(f"- {file_path}")
    
    # Спрашиваем подтверждение перед удалением
    confirm = input("\nВы уверены, что хотите удалить эти файлы? (y/n): ")
    if confirm.lower() != 'y':
        print("Операция отменена.")
        return
    
    # Удаляем файлы
    for file_path in files_to_remove:
        try:
            os.remove(file_path)
            print(f"Удален файл: {file_path}")
        except (FileNotFoundError, PermissionError) as e:
            print(f"Ошибка при удалении {file_path}: {e}")
    
    # Удаляем пустые директории
    for root, dirs, files in os.walk('.', topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                # Проверяем, пуста ли директория
                if not os.listdir(dir_path) and dir_name != '.git' and dir_name != '__pycache__':
                    os.rmdir(dir_path)
                    print(f"Удалена пустая директория: {dir_path}")
            except (OSError, PermissionError) as e:
                print(f"Ошибка при удалении директории {dir_path}: {e}")
    
    print("\nОчистка завершена!")
    print("\nДобавление изменений в Git...")
    
    # Добавляем изменения в Git
    os.system('git add -A')
    os.system('git commit -m "Удаление ненужных файлов для оптимизации репозитория"')
    
    print("\nИзменения добавлены в Git. Используйте 'git push', чтобы отправить изменения на GitHub.")

if __name__ == "__main__":
    print("=== Очистка репозитория от ненужных файлов ===")
    cleanup_repo() 