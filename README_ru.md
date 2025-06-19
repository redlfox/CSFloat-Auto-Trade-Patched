
## Шаг 1: Клонирование репозитория

Сначала склонируйте репозиторий с GitHub на ваш локальный компьютер.

1.  **Откройте терминал (Командную строку или PowerShell на Windows).**
    
2.  **Выполните команду:**
       
    `git clone https://github.com/gradinazz/CSFloat-Auto-Trade.git` 
            
3.  **Перейдите в директорию проекта:**
           
    `cd CSFloat-Auto-Trade` 
      

## Шаг 2: Установка зависимостей

Установите необходимые пакеты, перечисленные в файле `requirements.txt`.

1.  **Убедитесь, что находитесь в директории проекта и активировано виртуальное окружение.**
    
2.  **Выполните команду:**
      
    `pip install -r requirements.txt` 
      

## Шаг 3: Конфигурация скрипта

Перед запуском скрипта необходимо настроить конфигурационный файл `steam.json`.

 -  **Отредактируйте файл `steam.json` в корне проекта.**
    
 -  **Добавьте в него следующие параметры:**
            
    -   `csfloat_api_key`: Ваш API-ключ от CSFloat.
    -   `steam_api_key`: Ваш Steam API-ключ.
    -   `steam_id64`: Ваш Steam ID64 (например, `76561198034388123`).
    -   `steam_login`: Ваш логин от Steam.
    -   `steam_password`: Ваш пароль от Steam.
    -   `shared_secret` и `identity_secret`: Секреты, необходимые для подтверждения торговых предложений. Их можно получить из maFile.
    -   `client_proxy`: Необязательно: Установите прокси (например, `http://127.0.0.1:7890`).
    -   `steam_use_proxy`: Необязательно: Применить прокси для Steam cilent, если true.
    -   `check_interval_seconds`: Optional: Set the interval in seconds bewteen checks.
    -   `check_interval_seconds_random`: Optional: Enable randomizing the interval bewteen checks if setted to "true".
    -   `check_interval_seconds_random_min`: Optional: Set the minimum randomized interval in seconds bewteen checks.
    -   `check_interval_seconds_random_max`: Optional: Set the maximum randomized interval in seconds bewteen checks.
    
    **Важно:** Никогда не делитесь этими ключами и секретами. Храните их в безопасном месте.
    

## Шаг 4: Запуск скрипта

Теперь вы готовы запустить скрипт.
    
1.  **Выполните команду:**
      
    `python CSFloat-Auto-Trade.py` 
      
2.  **Скрипт начнёт выполнение и будет проверять наличие новых торговых предложений каждые 10 минут (по умолчанию).**
    
