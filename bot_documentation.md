# Документация Telegram-бота "Строй Форум Белгород"

## Описание проекта

Telegram-бот "Строй Форум Белгород" предназначен для представления информации из одноименной группы ВКонтакте в Telegram. Он предоставляет пользователям доступ к базе мастеров и спецтехники, магазинам-партнерам и другим полезным ресурсам для строительства и ремонта.

## Технологии и зависимости

- **Python 3.7+** - основной язык программирования
- **aiogram** - асинхронная библиотека для создания Telegram-ботов
- **vk_api** - библиотека для работы с API ВКонтакте
- **asyncio** - библиотека для асинхронного программирования
- **ThreadPoolExecutor** - исполнитель для выполнения блокирующих операций в отдельных потоках
- **dotenv** - для загрузки переменных окружения
- **logging** - для логирования работы приложения

## Архитектура проекта

Проект имеет следующую структуру:

```
├── main.py           - главный файл с обработчиками сообщений и запуском бота
├── vk.py             - модуль для работы с API ВКонтакте
├── vk_fixed.py       - исправленная версия модуля vk.py
├── config.py         - файл с конфигурацией и настройками бота
├── tg_bot/
│   ├── __init__.py
│   ├── buttons.py    - модуль для создания клавиатур и кнопок
│   └── states.py     - модуль с определением состояний FSM
```

## Основной функционал

### 1. Интеграция с ВКонтакте

Бот интегрирован с группой ВКонтакте "Строй Форум Белгород" и получает оттуда следующие данные:

- **База мастеров и спецтехники** - фотографии из альбомов группы
- **Магазины-партнеры** - товары из маркета ВКонтакте, представленные как магазины-партнеры
- **Приветственное сообщение** - описание группы ВКонтакте

### 2. Навигационное меню

Бот предоставляет следующие разделы в главном меню:

- **Магазины-партнеры СФБ** - просмотр магазинов-партнеров по категориям
- **База мастеров СФБ** - просмотр информации о мастерах и спецтехнике 
- **Стать магазином-партнером** - возможность подать заявку на участие в партнерской программе
- **Попасть в базу мастеров** - возможность добавить информацию в базу мастеров
- **Стена сообщества** - переход на канал Telegram с новостями
- **Предложить запись** - возможность предложить запись в сообщество

### 3. Система навигации и просмотра данных

#### Магазины-партнеры:
1. Отображение категорий магазинов
2. Выбор категории и просмотр списка магазинов
3. Детальный просмотр информации о магазине
4. Возврат к списку магазинов или категорий через соответствующие кнопки

#### База мастеров:
1. Отображение категорий мастеров
2. Выбор категории и просмотр фотографий с описаниями
3. Возврат к категориям или главному меню

### 4. Административные функции

- Команда `/cache_status` - проверка состояния кэша и времени его жизни
- Команда `/update_cache` - принудительное обновление кэша
- Проверка доступа на основе ID администраторов из конфигурации

## Логика работы

### Взаимодействие с API ВКонтакте

Взаимодействие с API ВКонтакте осуществляется через модуль `vk_api`. Все запросы к API выполняются в отдельных потоках через `ThreadPoolExecutor`, чтобы не блокировать основной цикл событий `asyncio`.

#### Основные функции для работы с API ВКонтакте:

1. `get_vk_session()` - создание авторизованной сессии ВКонтакте
2. `get_album_names()` - получение списка альбомов группы
3. `get_album_photos()` - получение фотографий из выбранного альбома
4. `get_market_items()` - получение категорий товаров из маркета группы
5. `get_market_item_info()` - получение товаров из выбранной категории
6. `get_shop_list()` - получение структурированного списка магазинов-партнеров
7. `get_group_description()` - получение и форматирование описания группы

### Управление состояниями (FSM)

Бот использует конечный автомат состояний для отслеживания диалога пользователя. 
Основные состояния:

- `User.get_master` - состояние выбора категории мастеров
- `User.get_shop_category` - состояние выбора категории магазинов
- `User.get_shop_info` - состояние просмотра информации о магазине
- `User.get_shop` - состояние просмотра товаров магазина (не используется в текущей версии)

### Система кэширования

Для оптимизации запросов к API ВКонтакте реализована система кэширования:

1. Декоратор `@cached` оборачивает все функции, которые делают запросы к API
2. Результаты запросов сохраняются в словаре `cache`
3. Если данные в кэше не устарели, они возвращаются без обращения к API
4. Время жизни кэша настраивается через `CACHE_TIME` в файле `config.py` (12 часов)
5. При запуске бота данные предварительно загружаются в кэш
6. Администраторы могут принудительно обновить кэш через команду `/update_cache`

### Асинхронные обертки

Для каждой блокирующей функции из модуля `vk.py` созданы асинхронные обертки, которые выполняют блокирующие вызовы в отдельных потоках:

- `get_album_names_async()`
- `get_album_photos_async()`
- `get_market_items_async()`
- `get_shop_list_async()`
- `get_group_description_async()`

### Генерация клавиатур

Клавиатуры для навигации генерируются динамически на основе данных из ВКонтакте:

1. `buttons.generator()` - создает клавиатуру с кнопками и кнопкой "Назад" вверху и внизу
2. `buttons.generator_with_categories_button()` - создает клавиатуру с кнопками магазинов и кнопкой "Вернуться к категориям" сверху и снизу
3. `buttons.go_back()` - создает клавиатуру с одной кнопкой "Назад в главное меню"

### Обработка ошибок

Реализована многоуровневая система обработки ошибок:

1. Все запросы к API ВКонтакте обернуты в блоки `try-except`
2. При ошибках в запросах возвращаются пустые списки или словари
3. Все исключения логируются с уровнем ERROR
4. Пользователю выводятся информативные сообщения о проблемах с получением данных

## Автоматическое обновление данных

1. Описание группы ВКонтакте используется как приветственное сообщение бота
2. Все данные (магазины, альбомы, описание группы) обновляются каждые 12 часов или при перезапуске бота
3. Предусмотрена возможность ручного обновления кэша администраторами

## Работа с пользовательскими запросами

1. Пользователь взаимодействует с ботом через кнопки в Telegram
2. Обработчики сообщений реагируют на нажатия кнопок и текстовые команды
3. FSM отслеживает текущее состояние диалога с пользователем
4. Данные пользовательской сессии сохраняются в `FSMContext`
5. При выборе категорий и магазинов данные запрашиваются из кэша или API ВКонтакте 