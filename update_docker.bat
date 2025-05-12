@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

:: Скрипт для переустановки Docker-контейнера с последними обновлениями из GitHub
:: и правильной конфигурацией файла .env

echo [33mЗапуск скрипта обновления бота СФБ в Docker...[0m

:: Переменные
set "REPO_URL=https://github.com/punk03/SFB_tg_bot.git"
set "PROJECT_DIR=C:\sfb_bot"
set "CONTAINER_NAME=sfb_bot"
set "ENV_FILE=%PROJECT_DIR%\.env"
set "ADMIN_IDS=771824107"

:: Функция для создания файла .env
:create_env_file
echo [33mСоздание файла .env...[0m
    
if exist "%ENV_FILE%" (
    echo [33mОбнаружен существующий файл .env. Сохраняем токены...[0m
    for /f "tokens=2 delims==" %%a in ('findstr "TG_BOT_TOKEN" "%ENV_FILE%"') do set "TG_BOT_TOKEN=%%a"
    for /f "tokens=2 delims==" %%a in ('findstr "VK_TOKEN" "%ENV_FILE%"') do set "VK_TOKEN=%%a"
    for /f "tokens=2 delims==" %%a in ('findstr "TG_GROUP_ID" "%ENV_FILE%"') do set "TG_GROUP_ID=%%a"
    for /f "tokens=2 delims==" %%a in ('findstr "VK_GROUP_ID" "%ENV_FILE%"') do set "VK_GROUP_ID=%%a"
) else (
    echo [33mФайл .env не найден. Пожалуйста, введите токены:[0m
    set /p TG_BOT_TOKEN="Введите TG_BOT_TOKEN: "
    set /p VK_TOKEN="Введите VK_TOKEN: "
    set /p TG_GROUP_ID="Введите TG_GROUP_ID: "
    set /p VK_GROUP_ID="Введите VK_GROUP_ID: "
)

:: Создаем файл .env с правильной кодировкой (UTF-8)
> "%ENV_FILE%" (
    echo # Конфигурация для бота СФБ
    echo # Файл создан автоматически скриптом update_docker.bat
    echo.
    echo # Токены и ID
    echo TG_BOT_TOKEN=!TG_BOT_TOKEN!
    echo VK_TOKEN=!VK_TOKEN!
    echo TG_GROUP_ID=!TG_GROUP_ID!
    echo VK_GROUP_ID=!VK_GROUP_ID!
    echo.
    echo # Администраторы
    echo ADMIN_IDS=%ADMIN_IDS%
    echo.
    echo # Настройки бота
    echo CACHE_TIME=3600
    echo PHOTO_DELAY=0.5
    echo DEBUG=False
)
echo [32mФайл .env успешно создан с правильной кодировкой![0m
goto :eof

:: Шаг 1: Убедиться, что Docker установлен
echo [33mПроверка наличия установленного Docker...[0m
docker --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [31mDocker не установлен! Пожалуйста, установите Docker и запустите скрипт снова.[0m
    goto :end
) else (
    echo [32mDocker установлен![0m
)

:: Шаг 2: Создать директорию проекта, если она не существует
echo [33mПроверка директории проекта...[0m
if not exist "%PROJECT_DIR%" (
    echo [33mДиректория проекта не существует. Создаём...[0m
    mkdir "%PROJECT_DIR%"
    echo [32mДиректория создана: %PROJECT_DIR%[0m
) else (
    echo [32mДиректория проекта уже существует: %PROJECT_DIR%[0m
)

:: Шаг 3: Перейти в директорию проекта
cd /d "%PROJECT_DIR%"
echo [32mТекущая директория: %cd%[0m

:: Шаг 4: Клонировать или обновить репозиторий
if exist ".git" (
    echo [33mОбновляем репозиторий...[0m
    git reset --hard
    git pull
    echo [32mРепозиторий обновлен![0m
) else (
    echo [33mКлонируем репозиторий...[0m
    :: Если директория не пуста, удалить все файлы (кроме .env, если он существует)
    dir /a /b | findstr /v .env > nul
    if not errorlevel 1 (
        for /f "delims=" %%f in ('dir /a /b ^| findstr /v .env') do (
            if "%%f" neq ".git" rd /s /q "%%f" 2>nul || del /q "%%f" 2>nul
        )
    )
    git clone "%REPO_URL%" .
    echo [32mРепозиторий успешно клонирован![0m
)

:: Шаг 5: Создать файл .env с правильными кодировками
call :create_env_file

:: Шаг 6: Остановить и удалить существующий контейнер, если он есть
echo [33mПроверяем, запущен ли контейнер...[0m
docker ps -a --format "{{.Names}}" | findstr /b /c:"%CONTAINER_NAME%" > nul
if not errorlevel 1 (
    echo [33mОстанавливаем и удаляем существующий контейнер...[0m
    docker stop "%CONTAINER_NAME%"
    docker rm "%CONTAINER_NAME%"
    echo [32mСуществующий контейнер удален![0m
) else (
    echo [32mКонтейнер не найден. Продолжаем установку...[0m
)

:: Шаг 7: Удаление старого образа (опционально)
echo [33mУдаляем старый образ, если он существует...[0m
docker images --format "{{.Repository}}:{{.Tag}}" | findstr /b /c:"%CONTAINER_NAME%:latest" > nul
if not errorlevel 1 (
    docker rmi "%CONTAINER_NAME%:latest"
    echo [32mСтарый образ удален![0m
) else (
    echo [32mСтарый образ не найден. Продолжаем...[0m
)

:: Шаг 8: Сборка и запуск Docker-контейнера
echo [33mСобираем и запускаем новый Docker-контейнер...[0m
docker-compose up --build -d

:: Шаг 9: Проверка, что контейнер запущен
echo [33mПроверяем, запущен ли новый контейнер...[0m
docker ps --format "{{.Names}}" | findstr /b /c:"%CONTAINER_NAME%" > nul
if not errorlevel 1 (
    echo [32mКонтейнер успешно запущен![0m
    echo [32mБот СФБ успешно обновлен и запущен в Docker![0m
) else (
    echo [31mОшибка! Контейнер не запущен. Проверьте журналы Docker:[0m
    echo [33mdocker logs %CONTAINER_NAME%[0m
    goto :end
)

:: Шаг 10: Вывод журналов контейнера (опционально)
set /p show_logs="[33mХотите посмотреть логи бота? (y/n)[0m "
if /i "%show_logs%"=="y" (
    docker logs -f "%CONTAINER_NAME%"
)

:end
echo [32mСкрипт завершен успешно![0m
pause 