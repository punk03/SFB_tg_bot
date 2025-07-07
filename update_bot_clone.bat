@echo off
REM Скрипт для обновления бота через клонирование репозитория
REM Вместо git pull полностью клонирует свежую версию репозитория

echo === Обновление бота через клонирование репозитория ===
echo.

REM URL репозитория
set REPO_URL=https://github.com/punk03/SFB_tg_bot.git
REM Директория для временного клонирования
set TEMP_DIR=%TEMP%\sfb_bot_temp
REM Текущая директория бота
set CURRENT_DIR=%CD%

REM Проверка наличия необходимых программ
where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git не установлен. Установите Git для продолжения.
    pause
    exit /b 1
)

where docker-compose >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker Compose не установлен. Установите Docker Compose для продолжения.
    pause
    exit /b 1
)

REM Остановка бота
echo 1. Останавливаем бота...
docker-compose down
echo Бот остановлен
echo.

REM Сохранение файла .env
echo 2. Сохранение конфигурации...
if exist .env (
    copy .env .env.backup /Y
    echo Файл .env сохранен
) else (
    echo [WARN] Файл .env не найден, продолжаем без сохранения конфигурации
)
echo.

REM Сохранение директории logs, если она существует
if exist logs (
    echo Сохранение логов...
    if not exist logs.backup mkdir logs.backup
    xcopy logs\* logs.backup\ /E /Y /Q
    echo Логи сохранены
)
echo.

REM Клонирование свежей версии репозитория
echo 3. Клонирование свежей версии репозитория...
if exist %TEMP_DIR% rmdir /S /Q %TEMP_DIR%
git clone %REPO_URL% %TEMP_DIR%
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Ошибка клонирования репозитория.
    echo [INFO] Восстанавливаем предыдущее состояние и запускаем бота...
    docker-compose up -d
    pause
    exit /b 1
)
echo Репозиторий склонирован
echo.

REM Копирование всех файлов из временной директории
echo 4. Обновление файлов...

REM Создаем список файлов и папок для сохранения
set "PRESERVED=.env .env.backup logs logs.backup .git"

REM Удаляем все файлы и папки кроме исключений
for /f "delims=" %%i in ('dir /b /a') do (
    set "DELETE=true"
    for %%p in (%PRESERVED%) do (
        if "%%i"=="%%p" set "DELETE="
    )
    if defined DELETE (
        if exist "%%i\*" (
            rmdir /S /Q "%%i"
        ) else (
            del /F /Q "%%i"
        )
    )
)

REM Копируем все файлы из временной директории
xcopy %TEMP_DIR%\* %CURRENT_DIR%\ /E /Y /Q
echo Файлы обновлены
echo.

REM Восстановление файла .env
if exist .env.backup (
    echo 5. Восстановление конфигурации...
    copy .env.backup .env /Y
    echo Файл .env восстановлен
    echo.
)

REM Восстановление директории logs
if exist logs.backup (
    echo Восстановление логов...
    if not exist logs mkdir logs
    xcopy logs.backup\* logs\ /E /Y /Q
    rmdir /S /Q logs.backup
    echo Логи восстановлены
    echo.
)

REM Очистка временной директории
echo 6. Очистка временных файлов...
rmdir /S /Q %TEMP_DIR%
if exist .env.backup del /F /Q .env.backup
echo Временные файлы удалены
echo.

REM Сборка и запуск обновленного бота
echo 7. Сборка и запуск обновленного бота...
docker-compose build
docker-compose up -d
echo Бот собран и запущен
echo.

REM Проверка статуса
echo 8. Проверка статуса бота...
timeout /t 5 /nobreak > nul
docker ps | findstr "sfb" > nul
if %ERRORLEVEL% equ 0 (
    echo Бот успешно обновлен и запущен
    echo Последние логи бота:
    docker logs --tail 10 sfb
) else (
    echo [ERROR] Возникла проблема при запуске бота.
    echo Проверьте логи:
    docker-compose logs -t --tail 20
)
echo.

echo === Обновление через клонирование репозитория завершено! ===
echo.
pause 