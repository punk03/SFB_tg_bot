# СФБ Телеграм-бот

Бот для сообщества "Строй Форум Белгород", интегрирующий информацию из группы ВКонтакте в Telegram.

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
│   └── states.py           # Состояния для FSM
├── Dockerfile              # Конфигурация Docker-образа
├── docker-compose.yml      # Конфигурация Docker Compose
├── .dockerignore           # Файлы, исключаемые из Docker-образа
├── .gitignore              # Файлы, исключаемые из Git
├── check_bot.sh            # Скрипт для проверки работоспособности бота
├── deploy_sfb_bot.sh       # Скрипт для полной установки бота на Ubuntu
├── bot_documentation.md    # Подробная документация бота
├── README_DOCKER.md        # Информация о работе с Docker
└── README_DOCKER_UPDATE.md # Руководство по обновлению в Docker
```

## Требования

- Python 3.8+
- aiogram 2.25.1 (не 3.x)
- aiohttp
- requests
- python-dotenv
- psutil
- или использование Docker

## Установка и запуск

### Автоматическая установка на Ubuntu

Для автоматической установки на Ubuntu используйте скрипт `deploy_sfb_bot.sh`:

1. Скачайте скрипт:
   ```bash
   wget https://raw.githubusercontent.com/punk03/SFB_tg_bot/main/deploy_sfb_bot.sh
   chmod +x deploy_sfb_bot.sh
   ```

2. Запустите скрипт с правами root:
   ```bash
   sudo ./deploy_sfb_bot.sh
   ```

Скрипт выполнит следующие действия:
- Установит Docker и Docker Compose (если они не установлены)
- Удалит старый контейнер и образ (если они существуют)
- Клонирует репозиторий в каталог `/opt/sfb_bot`
- Запросит необходимые токены и настроит файл `.env`
- Соберет и запустит Docker-контейнер
- Создаст команды для удобного управления ботом: `sfb-logs`, `sfb-restart`, `sfb-update`

### Ручная установка с Docker

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/punk03/SFB_tg_bot.git
   cd SFB_tg_bot
   ```

2. Создайте файл `.env` со следующим содержимым:
   ```
   TG_BOT_TOKEN=ваш_токен_бота
   VK_TOKEN=ваш_токен_вк
   TG_GROUP_ID=ид_группы_телеграм
   VK_GROUP_ID=ид_группы_вк
   ADMIN_IDS=ид_администратора
   CACHE_TIME=3600
   PHOTO_DELAY=0.5
   DEBUG=False
   ```

3. Соберите и запустите Docker-контейнер:
   ```bash
   docker-compose up --build -d
   ```

### Ручная установка без Docker

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/punk03/SFB_tg_bot.git
   cd SFB_tg_bot
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Создайте файл `.env` с необходимыми переменными окружения.

4. Запустите бота:
   ```bash
   python main.py
   ```

## Конфигурация

Бот использует следующие переменные окружения:

- `TG_BOT_TOKEN` - Токен Telegram-бота от BotFather
- `VK_TOKEN` - Токен ВКонтакте для доступа к API
- `TG_GROUP_ID` - ID группы в Telegram
- `VK_GROUP_ID` - ID группы ВКонтакте (по умолчанию 95855103)
- `ADMIN_IDS` - ID администраторов бота (через запятую)
- `CACHE_TIME` - Время жизни кэша в секундах (по умолчанию 3600)
- `PHOTO_DELAY` - Задержка между отправкой фотографий (по умолчанию 0.5)
- `DEBUG` - Режим отладки (по умолчанию False)

## Управление ботом на Ubuntu

После установки через `deploy_sfb_bot.sh` доступны следующие команды:

- `sfb-logs` - просмотр логов бота
- `sfb-restart` - перезапуск бота
- `sfb-update` - обновление бота из репозитория

## Обновление бота

### На Ubuntu
Если бот был установлен через `deploy_sfb_bot.sh`, используйте:
```bash
sfb-update
```

### Ручное обновление
1. Перейдите в каталог с ботом
2. Выполните:
   ```bash
   git pull
   docker-compose up --build -d
   ```

## Документация

Подробная документация доступна в файле [bot_documentation.md](bot_documentation.md).
Информация о работе с Docker доступна в файле [README_DOCKER.md](README_DOCKER.md).
Руководство по обновлению в Docker доступно в файле [README_DOCKER_UPDATE.md](README_DOCKER_UPDATE.md).
