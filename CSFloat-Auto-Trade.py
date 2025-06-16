import asyncio
import json
import aiohttp
import sys, time,os
from pathlib import Path
from aiohttp_socks.connector import ProxyConnector
from aiosteampy import SteamClient, AppContext
from aiosteampy.utils import get_jsonable_cookies
from aiosteampy.helpers import restore_from_cookies
from aiosteampy.mixins.guard import SteamGuardMixin  # Импортируем SteamGuard для подтверждения трейдов
from aiosteampy.mixins.web_api import SteamWebApiMixin  # Импортируем WebApiMixin для работы с Web API

# Продолжительность ожидания между проверками (в минутах)
CHECK_INTERVAL_MINUTES = 5

# Constants for API endpoints
API_USER_INFO = "https://csfloat.com/api/v1/me"
API_TRADES = "https://csfloat.com/api/v1/me/trades?state=queued,pending&limit=500"
API_ACCEPT_TRADE = "https://csfloat.com/api/v1/trades/{trade_id}/accept"  # Define the accept trade endpoint

# Path to a file to save cookies, will be created at end of a script run if do not exist
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
COOKIE_FILE = Path(rf"{SCRIPT_DIR}/cookies.json")
# print(str(COOKIE_FILE))
# print(COOKIE_FILE)
if COOKIE_FILE.is_file():
	print("cookie file true")
# time.sleep(10)
# sys.exit()
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"

# Path to store processed trade IDs
PROCESSED_TRADES_FILE = Path(rf"{SCRIPT_DIR}/processed_trades.json")

def load_steam_config(config_path=rf"{SCRIPT_DIR}/steam.json"):
    with open(config_path, 'r') as file:
        return json.load(file)

def load_processed_trades():
    if PROCESSED_TRADES_FILE.is_file():
        with PROCESSED_TRADES_FILE.open("r") as f:
            try:
                return set(json.load(f))  # trade_id остаются строками
            except json.JSONDecodeError:

                return set()
    return set()

def save_processed_trades(processed_trades):
    with PROCESSED_TRADES_FILE.open("w") as f:
        json.dump(list(processed_trades), f, indent=2)

async def get_user_info(session, csfloat_api_key):
    headers = {'Authorization': csfloat_api_key}
    try:
        async with session.get(API_USER_INFO, headers=headers) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientResponseError as http_err:
        print(f"HTTP error occurred while fetching user info: {http_err}")
    except Exception as err:
        print(f"Other error occurred while fetching user info: {err}")
    return None

async def get_trades(session, csfloat_api_key):
    headers = {'Authorization': csfloat_api_key}
    try:
        async with session.get(API_TRADES, headers=headers) as response:
            response.raise_for_status()
            trades_data = await response.json()
            return trades_data
    except aiohttp.ClientResponseError as http_err:
        print(f"HTTP error occurred while fetching trades: {http_err}")
    except Exception as err:
        print(f"Other error occurred while fetching trades: {err}")
    return None

async def accept_trade(session, csfloat_api_key, trade_id, trade_token):
    url = API_ACCEPT_TRADE.format(trade_id=trade_id)
    headers = {
        'Authorization': csfloat_api_key,
        'Content-Type': 'application/json'
    }
    payload = {
        'trade_token': trade_token  # Передача trade_token в тело запроса, если требуется API
    }
    try:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                # Логирование подробностей ошибки
                error_detail = await response.text()
                print(f"Failed to accept trade {trade_id}. Status: {response.status}, Detail: {error_detail}")
                return False
            result = await response.json()

            return True
    except aiohttp.ClientResponseError as http_err:
        print(f"HTTP error occurred while accepting trade {trade_id}: {http_err}")
    except Exception as err:
        print(f"Other error occurred while accepting trade {trade_id}: {err}")
    return False

async def send_steam_trade(client: SteamClient, trade_id, buyer_steam_id=None, trade_url=None, asset_id=None, trade_token=None):
    try:

        # Определение контекста игры, например, CS2
        game_context = AppContext.CS2  # Убедитесь, что это правильный контекст для вашего предмета

        # Получение вашего инвентаря
        my_inv, _, _ = await client.get_inventory(game_context)

        # Проверка структуры предметов в инвентаре
        if not my_inv:
            print("Your inventory is empty or could not be loaded.")
            return False

        # Попытка найти предмет по asset_id
        try:
            asset_id_int = int(asset_id)
            item_to_give = next((item for item in my_inv if item.asset_id == asset_id_int), None)
        except ValueError:
            item_to_give = next((item for item in my_inv if item.asset_id == asset_id), None)

        if not item_to_give:
            print(f"Item with asset_id {asset_id} not found in inventory.")
            # print(f"Предмет с asset_id {asset_id} не найден в инвентаре.")
            return False

        # Вызов make_trade_offer с использованием Steam ID или Trade URL
        if trade_url:
            # Отправка через трейд-ссылку
            offer_id = await client.make_trade_offer(
                trade_url,                     # Трейд-ссылка как первый позиционный аргумент
                to_give=[item_to_give],
                to_receive=[],
                message=""
            )
        elif buyer_steam_id:
            # Отправка через Steam ID партнёра
            if trade_token:
                offer_id = await client.make_trade_offer(
                    buyer_steam_id,              # Steam ID партнёра как первый позиционный аргумент
                    to_give=[item_to_give],
                    to_receive=[],
                    message="",
                    token=trade_token             # Передача trade_token, если требуется
                )
            else:
                offer_id = await client.make_trade_offer(
                    buyer_steam_id,              # Steam ID партнёра как первый позиционный аргумент
                    to_give=[item_to_give],
                    to_receive=[],
                    message=""
                )
        else:
            print("Необходимо указать либо buyer_steam_id, либо trade_url.")
            return False

        if offer_id:
            print(f"Торговое предложение {trade_id} отправлено!")
            return offer_id  # Возвращаем offer_id для дальнейшей обработки
        else:
            print("Не удалось отправить торговое предложение.")
            return False

    except aiohttp.ClientResponseError as http_err:
        print(f"HTTP error occurred while sending trade offer: {http_err}")
    except Exception as e:
        print(f"An error occurred while sending trade offer: {e}")
    return False

# Функция подтверждения трейдов, если требуется
async def confirm_trade(client: SteamGuardMixin):
    try:
        confirmations = await client.get_confirmations()

        if not confirmations:
            print("No pending confirmations.")
            return

        for confirmation in confirmations:
            confirmation_key, timestamp = await client._gen_confirmation_key(tag="conf")

            # Подтверждение трейда
            result = await client.confirm_confirmation(confirmation, confirmation_key, timestamp)
            if result:
                print(f"Successfully confirmed trade offer {confirmation.offer_id}")
            else:
                print(f"Failed to confirm trade offer {confirmation.offer_id}")

    except Exception as e:
        print(f"An error occurred while confirming trades: {e}")

async def check_actionable_trades(session, csfloat_api_key, client: SteamGuardMixin, shared_secret, identity_secret, processed_trades, check_interval_minutes):
    user_info = await get_user_info(session, csfloat_api_key)

    if user_info and user_info.get('actionable_trades', 0) > 0:
        print("Actionable trades found, fetching trade details...")
        trades_info = await get_trades(session, csfloat_api_key)
        # print("asfasf.")#debug
        # sys.exit()#debug
        if isinstance(trades_info, dict):
            trades_list = trades_info.get('trades', [])

            if isinstance(trades_list, list):
                for trade in trades_list:
                    if isinstance(trade, dict):
                        trade_id = trade.get('id')

                        # Проверка, был ли уже обработан этот trade_id
                        if str(trade_id) in processed_trades:
                            print(f"Trade {trade_id} has already been processed. Skipping.")
                            continue  # Пропустить уже обработанные трейды

                        seller_id = trade.get('seller_id')  # ID отправителя
                        buyer_id = trade.get('buyer_id')    # ID получателя
                        asset_id = trade.get('contract', {}).get('item', {}).get('asset_id')
                        trade_token = trade.get('trade_token')  # Получаем trade_token
                        trade_url = trade.get('trade_url')      # Получаем trade_url
                        accepted_at = trade.get('accepted_at')  # Получаем время принятия, если есть
                        trade_state = trade.get('state')        # Получаем состояние трейда


                        if trade_state == "verified":
                            # Если трейд уже подтвержден, добавляем его в обработанные и пропускаем
                            processed_trades.add(str(trade_id))

                            continue

                        if trade_id and seller_id and buyer_id and asset_id:
                            if accepted_at:
                                # Предложение уже принято, отправляем торговое предложение
                                print(f"Trade {trade_id} уже принято. Переходим к отправке торгового предложения.")
                                offer_id = await send_steam_trade(
                                    client,
                                    trade_id=str(trade_id),        # Передаём trade_id как строку
                                    buyer_steam_id=int(buyer_id),  # Передаём buyer_id как целое число
                                    asset_id=int(asset_id),
                                    trade_token=trade_token,
                                    trade_url=trade_url
                                )

                                if offer_id:
                                    # Автоматически подтверждаем трейды
                                    await confirm_trade(client)
                                else:
                                    print(f"Failed to send trade for {trade_id}")
                            else:
                                # Предложение ещё не принято, принимаем его
                                print(f"Accepting trade {trade_id}...")
                                accept_result = await accept_trade(session, csfloat_api_key, trade_id=str(trade_id), trade_token=trade_token)

                                if accept_result:
                                    print(f"Sending item to buyer for trade {trade_id}...")
                                    offer_id = await send_steam_trade(
                                        client,
                                        trade_id=str(trade_id),        # Передаём trade_id как строку
                                        buyer_steam_id=int(buyer_id),  # Передаём buyer_id как целое число
                                        asset_id=int(asset_id),
                                        trade_token=trade_token,
                                        trade_url=trade_url
                                    )

                                    if offer_id:
                                        # Автоматически подтверждаем трейды
                                        await confirm_trade(client)
                                    else:
                                        print(f"Failed to send trade for {trade_id}")
                                else:
                                    print(f"Failed to accept trade {trade_id}")

                        # Добавляем trade_id в processed_trades независимо от результата
                        processed_trades.add(str(trade_id))
                        
            else:
                print(f"Unexpected trades list format: {type(trades_list)}")
        else:
            print(f"Unexpected trades data format: {type(trades_info)}")
    else:
        print(f"No actionable trades at the moment. Waiting for {check_interval_minutes} minutes before next check.")
def any2bool(v):
  return str(v).lower() in ("yes", "true", "t", "1")
def readConfigValue(configJson,jsonKey):
    try:
        jsonValue= configJson[jsonKey]
    except Exception as err:
        print(f"Couldn't load value from config file: {jsonKey}")
    else:
        return jsonValue
async def main():
    config = load_steam_config()  # Загрузка конфигурации

    csfloat_api_key = config['csfloat_api_key']
    steam_api_key = config['steam_api_key']
    steam_id = int(config['steam_id64'])  # Убедитесь, что это целое число
    steam_login = config['steam_login']
    steam_password = config['steam_password']
    shared_secret = config['shared_secret']
    identity_secret = config['identity_secret']
    cilent_proxy = readConfigValue(config,'cilent_proxy')
    steam_use_proxy = any2bool(readConfigValue(config,'steam_use_proxy')) # Acceptable true value: "yes", "true", "t", "y", "1"
    if cilent_proxy:
        print(f"proxy true: {cilent_proxy}")
    # Определение продолжительности ожидания (в минутах)
    CHECK_INTERVAL_MINUTES = 5  # Вы можете легко изменить это значение

    # Инициализация SteamClient с необходимыми аргументами
    class MySteamClient(SteamClient, SteamWebApiMixin, SteamGuardMixin):
        pass
    # print(steam_use_proxy)
    client = MySteamClient(
        steam_id=steam_id,              # Steam ID64 как целое число
        username=steam_login,
        password=steam_password,
        shared_secret=shared_secret,
        identity_secret=identity_secret,
        api_key=steam_api_key,          # Передача API ключа
        user_agent=USER_AGENT,
    )
    if cilent_proxy and steam_use_proxy==True:
        MySteamClient.proxy=cilent_proxy
        print("steam proxy true")
        # print(client.proxy)
    else:
        print(f"steam proxy false")
    # sys.exit()
    # Восстановление cookies, если они существуют

    if COOKIE_FILE.is_file():
        try:
            with COOKIE_FILE.open("r") as f:
                cookies = json.load(f)
            await restore_from_cookies(cookies, client)
        except Exception as err:
            print(f"{err}")
            await client.login()
    else:
        await client.login()

    # Загрузка обработанных трейдов
    processed_trades = load_processed_trades()

    sessionConnector = ProxyConnector.from_url(cilent_proxy, ttl_dns_cache=300) if cilent_proxy else aiohttp.TCPConnector(
        resolver=aiohttp.resolver.AsyncResolver(),
        limit_per_host=50
    )
    
    async with aiohttp.ClientSession(connector=sessionConnector) as session:
        try:
            while True:
                await check_actionable_trades(
                    session,
                    csfloat_api_key,
                    client,
                    shared_secret,
                    identity_secret,
                    processed_trades,           # Передача набора обработанных трейдов
                    CHECK_INTERVAL_MINUTES      # Передача продолжительности ожидания
                )
                save_processed_trades(processed_trades)  # Сохранение после каждой проверки
                await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)  # Ожидание заданное количество минут
        finally:
            # Сохранение cookies
            with COOKIE_FILE.open("w") as f:
                json.dump(get_jsonable_cookies(client.session), f, indent=2)

            await client.session.close()

if __name__ == "__main__":
    asyncio.run(main())
