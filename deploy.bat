@echo off
REM Скрипт автоматического развертывания Telegram бота "Строй Форум Белгород" на Windows-сервере
REM Используется Docker и docker-compose

echo === Автоматическое развертывание Telegram бота ===
echo.

REM Проверка наличия необходимых программ
echo Проверка необходимых зависимостей...

where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git не установлен. Установите Git для продолжения.
    pause
    exit /b 1
) else (
    echo [OK] Git установлен
)

where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker не установлен. Установите Docker для продолжения.
    pause
    exit /b 1
) else (
    echo [OK] Docker установлен
)

where docker-compose >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker Compose не установлен. Установите Docker Compose для продолжения.
    pause
    exit /b 1
) else (
    echo [OK] Docker Compose установлен
)
echo.

REM Создание файла конфигурации .env, если его нет
echo Настройка конфигурационного файла .env...
if exist .env (
    echo [OK] Файл .env уже существует
) else (
    echo Создание файла .env...
    (
        echo # Токен Telegram бота ^(получить у @BotFather^)
        echo TG_BOT_TOKEN=
        echo.
        echo # Токен VK API
        echo VK_TOKEN=
        echo.
        echo # ID группы VK ^(число^)
        echo VK_GROUP_ID=
        echo.
        echo # ID администраторов ^(через запятую^)
        echo ADMIN_IDS=
        echo.
        echo # Дополнительные настройки
        echo DEBUG=False
    ) > .env
    
    echo [OK] Файл .env создан. Пожалуйста, заполните его необходимыми данными
    echo Для продолжения необходимо заполнить файл .env.
    echo Откройте файл в любом текстовом редакторе (например, Блокнот)
    pause
)
echo.

REM Основная функция развертывания
echo Начинаем развертывание бота...

REM Создаем директорию для логов, если ее нет
if not exist logs mkdir logs
echo [OK] Директория для логов создана
echo.

REM Создаем скрипт для запуска бота
echo Создание скриптов управления...
(
    echo @echo off
    echo echo Запуск бота...
    echo docker-compose up -d
    echo echo Бот запущен в фоновом режиме!
    echo pause
) > start_bot.bat
echo [OK] Скрипт запуска создан

REM Создаем скрипт для остановки бота
(
    echo @echo off
    echo echo Остановка бота...
    echo docker-compose down
    echo echo Бот остановлен!
    echo pause
) > stop_bot.bat
echo [OK] Скрипт остановки создан

REM Создаем скрипт для обновления бота через git pull
(
    echo @echo off
    echo echo Обновление бота через git pull...
    echo git pull
    echo docker-compose build
    echo docker-compose up -d
    echo echo Бот обновлен и перезапущен!
    echo pause
) > update_bot.bat
echo [OK] Скрипт обновления через git pull создан

REM Создаем скрипт для просмотра логов
(
    echo @echo off
    echo echo Вывод логов бота ^(Ctrl+C для выхода^)...
    echo docker-compose logs -f
    echo pause
) > logs.bat
echo [OK] Скрипт для просмотра логов создан

REM Создаем скрипт для обновления через клонирование репозитория
(
    echo @echo off
    echo REM Скрипт для обновления бота через клонирование репозитория
    echo REM Вместо git pull полностью клонирует свежую версию репозитория
    echo.
    echo echo === Обновление бота через клонирование репозитория ===
    echo echo.
    echo.
    echo REM URL репозитория
    echo set REPO_URL=https://github.com/punk03/SFB_tg_bot.git
    echo REM Директория для временного клонирования
    echo set TEMP_DIR=%%TEMP%%\sfb_bot_temp
    echo REM Текущая директория бота
    echo set CURRENT_DIR=%%CD%%
    echo.
    echo REM Проверка наличия необходимых программ
    echo where git ^>nul 2^>nul
    echo if %%ERRORLEVEL%% neq 0 ^(
    echo     echo [ERROR] Git не установлен. Установите Git для продолжения.
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo where docker-compose ^>nul 2^>nul
    echo if %%ERRORLEVEL%% neq 0 ^(
    echo     echo [ERROR] Docker Compose не установлен. Установите Docker Compose для продолжения.
    echo     pause
    echo     exit /b 1
    echo ^)
    echo.
    echo REM Остановка бота
    echo echo 1. Останавливаем бота...
    echo docker-compose down
    echo echo Бот остановлен
    echo echo.
    echo.
    echo REM Сохранение файла .env
    echo echo 2. Сохранение конфигурации...
    echo if exist .env ^(
    echo     copy .env .env.backup /Y
    echo     echo Файл .env сохранен
    echo ^) else ^(
    echo     echo [WARN] Файл .env не найден, продолжаем без сохранения конфигурации
    echo ^)
    echo echo.
    echo.
    echo REM Сохранение директории logs, если она существует
    echo if exist logs ^(
    echo     echo Сохранение логов...
    echo     if not exist logs.backup mkdir logs.backup
    echo     xcopy logs\* logs.backup\ /E /Y /Q
    echo     echo Логи сохранены
    echo ^)
    echo echo.
    echo.
    echo REM Клонирование свежей версии репозитория
    echo echo 3. Клонирование свежей версии репозитория...
    echo if exist %%TEMP_DIR%% rmdir /S /Q %%TEMP_DIR%%
    echo git clone %%REPO_URL%% %%TEMP_DIR%%
    echo if %%ERRORLEVEL%% neq 0 ^(
    echo     echo [ERROR] Ошибка клонирования репозитория.
    echo     echo [INFO] Восстанавливаем предыдущее состояние и запускаем бота...
    echo     docker-compose up -d
    echo     pause
    echo     exit /b 1
    echo ^)
    echo echo Репозиторий склонирован
    echo echo.
    echo.
    echo REM Копирование всех файлов из временной директории
    echo echo 4. Обновление файлов...
    echo.
    echo REM Создаем список файлов и папок для сохранения
    echo set "PRESERVED=.env .env.backup logs logs.backup .git"
    echo.
    echo REM Удаляем все файлы и папки кроме исключений
    echo for /f "delims=" %%%%i in ^('dir /b /a'^) do ^(
    echo     set "DELETE=true"
    echo     for %%%%p in ^(%%PRESERVED%%^) do ^(
    echo         if "%%%%i"=="%%%%p" set "DELETE="
    echo     ^)
    echo     if defined DELETE ^(
    echo         if exist "%%%%i\*" ^(
    echo             rmdir /S /Q "%%%%i"
    echo         ^) else ^(
    echo             del /F /Q "%%%%i"
    echo         ^)
    echo     ^)
    echo ^)
    echo.
    echo REM Копируем все файлы из временной директории
    echo xcopy %%TEMP_DIR%%\* %%CURRENT_DIR%%\ /E /Y /Q
    echo echo Файлы обновлены
    echo echo.
    echo.
    echo REM Восстановление файла .env
    echo if exist .env.backup ^(
    echo     echo 5. Восстановление конфигурации...
    echo     copy .env.backup .env /Y
    echo     echo Файл .env восстановлен
    echo     echo.
    echo ^)
    echo.
    echo REM Восстановление директории logs
    echo if exist logs.backup ^(
    echo     echo Восстановление логов...
    echo     if not exist logs mkdir logs
    echo     xcopy logs.backup\* logs\ /E /Y /Q
    echo     rmdir /S /Q logs.backup
    echo     echo Логи восстановлены
    echo     echo.
    echo ^)
    echo.
    echo REM Очистка временной директории
    echo echo 6. Очистка временных файлов...
    echo rmdir /S /Q %%TEMP_DIR%%
    echo if exist .env.backup del /F /Q .env.backup
    echo echo Временные файлы удалены
    echo echo.
    echo.
    echo REM Сборка и запуск обновленного бота
    echo echo 7. Сборка и запуск обновленного бота...
    echo docker-compose build
    echo docker-compose up -d
    echo echo Бот собран и запущен
    echo echo.
    echo.
    echo REM Проверка статуса
    echo echo 8. Проверка статуса бота...
    echo timeout /t 5 /nobreak ^> nul
    echo docker ps ^| findstr "sfb" ^> nul
    echo if %%ERRORLEVEL%% equ 0 ^(
    echo     echo Бот успешно обновлен и запущен
    echo     echo Последние логи бота:
    echo     docker logs --tail 10 sfb
    echo ^) else ^(
    echo     echo [ERROR] Возникла проблема при запуске бота.
    echo     echo Проверьте логи:
    echo     docker-compose logs -t --tail 20
    echo ^)
    echo echo.
    echo.
    echo echo === Обновление через клонирование репозитория завершено! ===
    echo echo.
    echo pause
) > update_bot_clone.bat
echo [OK] Скрипт полного обновления через клонирование репозитория создан
echo.

REM Запускаем бота
echo Сборка и запуск Docker-контейнера...
docker-compose build
docker-compose up -d
echo [OK] Бот успешно запущен!
echo.

REM Проверка работоспособности
echo Проверка статуса бота...
timeout /t 5 /nobreak > nul
docker ps | findstr "sfb" > nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Контейнер запущен
    echo Логи бота (последние 10 строк):
    docker logs --tail 10 sfb
) else (
    echo [ERROR] Контейнер не запущен. Проверьте логи: logs.bat
    docker-compose logs -t --tail 20
)
echo.

echo === Развертывание завершено! ===
echo Доступные команды:
echo   start_bot.bat        - Запуск бота
echo   stop_bot.bat         - Остановка бота
echo   update_bot.bat       - Обновление бота через git pull
echo   update_bot_clone.bat - Полное обновление через клонирование репозитория
echo   logs.bat             - Просмотр логов бота
echo.
pause 