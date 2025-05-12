@echo off
echo Остановка бота "Строй Форум Белгород" в Docker

:: Проверка наличия docker-compose
docker-compose --version > nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Остановка бота через docker-compose...
    docker-compose down
    
    if %ERRORLEVEL% equ 0 (
        echo Бот успешно остановлен!
    ) else (
        echo Ошибка при остановке бота.
    )
) else (
    echo Docker Compose не установлен или не доступен. Попытка остановки через Docker...
    
    :: Проверка, запущен ли контейнер
    docker ps -q --filter "name=stroy-forum-bot" > nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo Остановка и удаление контейнера...
        docker stop stroy-forum-bot
        docker rm stroy-forum-bot
        
        if %ERRORLEVEL% equ 0 (
            echo Бот успешно остановлен!
        ) else (
            echo Ошибка при остановке бота.
        )
    ) else (
        echo Контейнер бота не запущен или уже остановлен.
    )
)

echo.
echo Нажмите любую клавишу для выхода...
pause > nul 