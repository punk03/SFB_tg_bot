@echo off
echo Обновление бота "Строй Форум Белгород" в Docker

:: Проверка наличия docker-compose
docker-compose --version > nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Остановка предыдущей версии бота...
    docker-compose down
    
    echo Запуск сборки новой версии бота...
    docker-compose up -d --build
    
    if %ERRORLEVEL% equ 0 (
        echo Бот успешно обновлен и запущен!
        echo Для просмотра логов введите: docker-compose logs -f
    ) else (
        echo Ошибка при обновлении бота. Проверьте логи: docker-compose logs
    )
) else (
    echo Docker Compose не установлен или не доступен. Попытка обновления через Docker...
    
    :: Проверка, запущен ли контейнер
    docker ps -q --filter "name=stroy-forum-bot" > nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo Остановка и удаление контейнера...
        docker stop stroy-forum-bot
        docker rm stroy-forum-bot
    )
    
    echo Удаление старого образа...
    docker rmi stroy-forum-bot
    
    echo Сборка нового образа...
    docker build -t stroy-forum-bot .
    
    echo Запуск нового контейнера...
    docker run -d --name stroy-forum-bot^
     -v "%cd%\logs:/app/logs"^
     -v "%cd%\.env:/app/.env"^
     --restart always^
     stroy-forum-bot
    
    if %ERRORLEVEL% equ 0 (
        echo Бот успешно обновлен и запущен!
        echo Для просмотра логов введите: docker logs -f stroy-forum-bot
    ) else (
        echo Ошибка при обновлении бота. Проверьте логи: docker logs stroy-forum-bot
    )
)

echo.
echo Нажмите любую клавишу для выхода...
pause > nul 