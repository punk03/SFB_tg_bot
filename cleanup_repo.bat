@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: Скрипт для очистки репозитория от ненужных файлов в Windows

echo [33m=== Очистка репозитория от ненужных файлов ===[0m

:: Создаем временную директорию для сохранения нужных файлов
set "TEMP_DIR=%TEMP%\sfb_bot_temp"
if exist "%TEMP_DIR%" rd /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"
echo [33mСоздана временная директория: %TEMP_DIR%[0m

:: Копируем необходимые файлы во временную директорию
echo [33mКопирование необходимых файлов...[0m

:: Основные файлы бота
robocopy . "%TEMP_DIR%" main.py /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" config.py /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" loader.py /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" vk.py /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" requirements.txt /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" .gitignore /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" .dockerignore /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" README.md /NFL /NDL /NJH /NJS /nc /ns /np

:: Docker-файлы
robocopy . "%TEMP_DIR%" Dockerfile /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" docker-compose.yml /NFL /NDL /NJH /NJS /nc /ns /np

:: Скрипты для обновления и запуска в Docker
robocopy . "%TEMP_DIR%" update_docker.sh /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" update_docker.bat /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" README_DOCKER_UPDATE.md /NFL /NDL /NJH /NJS /nc /ns /np

:: Директории и их содержимое
robocopy "tg_bot" "%TEMP_DIR%\tg_bot" /E /NFL /NDL /NJH /NJS /nc /ns /np

:: Скрипты запуска
robocopy . "%TEMP_DIR%" start_bot.sh /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" start_bot.bat /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" stop_bot.bat /NFL /NDL /NJH /NJS /nc /ns /np

:: Дополнительные полезные файлы
robocopy . "%TEMP_DIR%" bot_documentation.md /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" README_DOCKER.md /NFL /NDL /NJH /NJS /nc /ns /np
robocopy . "%TEMP_DIR%" check_bot.sh /NFL /NDL /NJH /NJS /nc /ns /np

echo [32mФайлы скопированы во временную директорию.[0m

:: Спрашиваем подтверждение перед удалением
echo [33mВсе необходимые файлы сохранены во временной директории.[0m
set /p "confirm=Вы уверены, что хотите удалить все остальные файлы? (y/n): "
if /i "%confirm%" neq "y" (
    echo [31mОперация отменена.[0m
    rd /s /q "%TEMP_DIR%"
    exit /b 1
)

:: Удаляем все файлы, кроме .git
echo [33mУдаление ненужных файлов...[0m
for /d %%d in (*) do (
    if /i "%%d" neq ".git" rd /s /q "%%d"
)
for %%f in (*) do (
    del /q "%%f"
)

:: Копируем необходимые файлы обратно
echo [33mКопирование необходимых файлов обратно...[0m
robocopy "%TEMP_DIR%" . /E /NFL /NDL /NJH /NJS /nc /ns /np

:: Удаляем временную директорию
echo [33mУдаление временной директории...[0m
rd /s /q "%TEMP_DIR%"

:: Добавляем изменения в Git
echo [33mДобавление изменений в Git...[0m
git add -A
git commit -m "Удаление ненужных файлов для оптимизации репозитория"

echo [32mОчистка репозитория завершена![0m
echo [32mИспользуйте 'git push', чтобы отправить изменения на GitHub.[0m

pause 