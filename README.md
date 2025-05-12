# СФБ Телеграм-бот

Бот для сообщества "Строй Форум Белгород".

## Возможности бота

- Отображение категорий мастеров из ВК
- Просмотр информации о мастерах
- Отображение категорий магазинов-партнеров из ВК
- Просмотр информации о магазинах
- Удобная навигация через кнопки

## Структура проекта

```
.
├── main.py                 # Основной файл приложения
├── config.py               # Настройки и конфигурация
├── loader.py               # Загрузчик токенов и переменных среды
├── vk.py                   # Модуль для работы с API ВКонтакте
├── requirements.txt        # Зависимости проекта
├── tg_bot/                 # Модули Telegram-бота
│   ├── __init__.py         # Инициализационный файл
│   ├── buttons.py          # Кнопки и клавиатуры
│   ├── handlers.py         # Обработчики сообщений
│   ├── states.py           # Состояния для FSM
│   └── tg_bot.py           # Основной модуль бота
├── Dockerfile              # Конфигурация Docker-образа
├── docker-compose.yml      # Конфигурация Docker Compose
├── .dockerignore           # Файлы, исключаемые из Docker-образа
├── .gitignore              # Файлы, исключаемые из Git
├── update_docker.sh        # Скрипт обновления для Linux
├── update_docker.bat       # Скрипт обновления для Windows
├── start_bot.sh            # Скрипт запуска для Linux
├── start_bot.bat           # Скрипт запуска для Windows
└── stop_bot.bat            # Скрипт остановки для Windows
```

## Требования

- Python 3.8+
- aiogram 2.25.1 (не 3.x)
- aiohttp
- requests
- python-dotenv
- или использование Docker

## Установка и запуск

### Установка с использованием Docker (рекомендуется)

Для установки и запуска бота в Docker-контейнере:

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/punk03/SFB_tg_bot.git
   cd SFB_tg_bot
   ```

2. Запустите скрипт обновления:
   - Linux/macOS: `./update_docker.sh`
   - Windows: `update_docker.bat`

Скрипт запросит необходимые токены и настроит контейнер автоматически.

### Ручная установка

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/punk03/SFB_tg_bot.git
   cd SFB_tg_bot
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Создайте файл `.env` со следующим содержимым:
   ```
   TG_BOT_TOKEN=ваш_токен_бота
   VK_TOKEN=ваш_токен_вк
   TG_GROUP_ID=ид_группы_телеграм
   VK_GROUP_ID=ид_группы_вк
   ADMIN_IDS=ид_администратора
   ```

4. Запустите бота:
   - Linux/macOS: `./start_bot.sh`
   - Windows: `start_bot.bat`

## Конфигурация

Бот использует следующие переменные окружения:

- `TG_BOT_TOKEN` - Токен Telegram-бота от BotFather
- `VK_TOKEN` - Токен ВКонтакте для доступа к API
- `TG_GROUP_ID` - ID группы в Telegram
- `VK_GROUP_ID` - ID группы ВКонтакте
- `ADMIN_IDS` - ID администраторов бота

## Обновление бота

Для обновления бота из GitHub-репозитория запустите:
- Linux/macOS: `./update_docker.sh`
- Windows: `update_docker.bat`

## Документация

Подробная документация доступна в файле [bot_documentation.md](bot_documentation.md).
Информация о работе с Docker доступна в файле [README_DOCKER.md](README_DOCKER.md).
Руководство по обновлению в Docker доступно в файле [README_DOCKER_UPDATE.md](README_DOCKER_UPDATE.md).
