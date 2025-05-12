@echo off
echo Запуск бота "Строй Форум Белгород" в Docker

:: Проверка наличия файла .env
if not exist .env (
    echo Файл .env не найден. Создаю из шаблона...
    if exist .env.example (
        copy .env.example .env
        echo Файл .env создан. Пожалуйста, отредактируйте его, указав правильные токены и ID.
        echo После редактирования запустите скрипт снова.
        pause
        exit /b 1
    ) else (
        echo Ошибка: Файл .env.example не найден!
        pause
        exit /b 1
    )
)

:: Создание директории для логов
if not exist logs mkdir logs
echo Директория для логов создана.

:: Проверка наличия Docker
docker --version > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Docker не установлен. Пожалуйста, установите Docker Desktop и попробуйте снова.
    pause
    exit /b 1
)

:: Проверка наличия docker-compose
docker-compose --version > nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Запуск бота через docker-compose...
    docker-compose up -d
    
    if %ERRORLEVEL% equ 0 (
        echo Бот успешно запущен!
        echo Для просмотра логов введите: docker-compose logs -f
    ) else (
        echo Ошибка при запуске бота. Проверьте логи: docker-compose logs
    )
) else (
    echo Docker Compose не установлен или не доступен. Попытка запуска через Docker...
    
    echo Сборка Docker образа...
    docker build -t stroy-forum-bot .
    
    echo Запуск контейнера...
    docker run -d --name stroy-forum-bot^
     -v "%cd%\logs:/app/logs"^
     -v "%cd%\.env:/app/.env"^
     --restart always^
     stroy-forum-bot
    
    if %ERRORLEVEL% equ 0 (
        echo Бот успешно запущен!
        echo Для просмотра логов введите: docker logs -f stroy-forum-bot
    ) else (
        echo Ошибка при запуске бота. Проверьте логи: docker logs stroy-forum-bot
    )
)

echo.
echo Нажмите любую клавишу для выхода...
pause > nul 