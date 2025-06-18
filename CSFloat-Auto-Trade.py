import asyncio
import json
import aiohttp
import os,random
from pathlib import Path
from aiohttp_socks.connector import ProxyConnector
from aiosteampy import SteamClient, AppContext
from aiosteampy.utils import get_jsonable_cookies,JSONABLE_COOKIE_JAR
from aiosteampy.client import SteamClientBase
from aiosteampy.models import TradeOffer
from aiosteampy.helpers import restore_from_cookies
from aiosteampy.mixins.guard import SteamGuardMixin  # Импортируем SteamGuard для подтверждения трейдов
from aiosteampy.mixins.web_api import SteamWebApiMixin  # Импортируем WebApiMixin для работы с Web API
from aiosteampy.constants import (
    App,
    AppContext,
    STEAM_URL,
    Currency,
    Language,
    TradeOfferStatus,
    MarketListingStatus,
    EResult,
    ConfirmationType,
)
# from collections import OrderedDict

# Продолжительность ожидания между проверками (в минутах)
# CHECK_INTERVAL_MINUTES = 5

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

# Инициализация SteamClient с необходимыми аргументами
class MySteamClient(SteamClient, SteamWebApiMixin, SteamGuardMixin):
    pass

def load_steam_config(config_path=rf"{SCRIPT_DIR}/steam.json"):
    with open(config_path, 'r') as file:
        return json.load(file)
    
async def restore_from_cookies_retry(cookies: JSONABLE_COOKIE_JAR, steam_client: "SteamClientBase"):
    try_count=0
    while True:
        try:
            await restore_from_cookies(cookies, steam_client)
            print(f"Loaded Steam account: {steam_client.username}")
            return
        except aiohttp.ClientResponseError as http_err:
            print(f"HTTP error occurred while restoring the Steam session from cookies: {http_err}")
        except ConnectionError as connect_err:
            print(f"connection error occurred while restoring the Steam session from cookies: {connect_err}")
        except Exception as err:
            print(f"Other error occurred while restoring the Steam session from cookies: {err}")
        try_count+=1
        if try_count >5:
            print("Failed too many times.")
            return None
        await asyncio.sleep(50)

async def steam_client_login_retry(steam_client: "SteamClientBase"):
    try_count=0
    while True:
        try:
            await steam_client.login()
            print(f"Loaded Steam account: {steam_client.username}")
            return
        except aiohttp.ClientResponseError as http_err:
            print(f"HTTP error occurred while logging in to Steam: {http_err}")
        except ConnectionError as connect_err:
            print(f"connection error occurred while logging in to Steam: {connect_err}")
        except Exception as err:
            print(f"Other error occurred while logging in to Steam: {err}")
        try_count+=1
        if try_count >5:
            print("Failed too many times.")
            return None
        await asyncio.sleep(50)
        
async def confirm_trade_offer_retry(steam_client: "SteamClientBase", obj: int | TradeOffer):
    try_count=0
    while True:
        try:
            print(f"Confirming trade offer {obj}.")
            await steam_client.confirm_trade_offer(obj)
            return
        except aiohttp.ClientResponseError as http_err:
            print(f"HTTP error occurred while confirming the trade offer: {http_err}")
        except ConnectionError as connect_err:
            print(f"connection error occurred while confirming the trade offer: {connect_err}")
        except Exception as err:
            print(f"Other error occurred while confirming the trade offer: {err}")
        try_count+=1
        if try_count >5:
            print("Failed too many times.")
            return None
        await asyncio.sleep(50)

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
        print(f"HTTP error occurred while fetching CSFloat user info: {http_err}")
    except ConnectionError as connect_err:
        print(f"connection error occurred while fetching CSFloat user info: {connect_err}")
    except Exception as err:
        print(f"Other error occurred while fetching CSFloat user info: {err}")
    return None

async def get_trades(session, csfloat_api_key):
    headers = {'Authorization': csfloat_api_key}
    try_count=0
    while True:
        try:
            async with session.get(API_TRADES, headers=headers) as response:
                response.raise_for_status()
                trades_data = await response.json()
                # print(trades_data)#debug
                return trades_data
        except aiohttp.ClientResponseError as http_err:
            print(f"HTTP error occurred while fetching trades: {http_err}")
        except ConnectionError as connect_err:
            print(f"connection error occurred while fetching trades: {connect_err}")
        except Exception as err:
            print(f"Other error occurred while fetching trades: {err}")
        try_count+=1
        if try_count >5:
            return None
        await asyncio.sleep(50)

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
    except ConnectionError as connect_err:
        print(f"connection error occurred while accepting trade: {connect_err}")
    except Exception as err:
        print(f"Other error occurred while accepting trade {trade_id}: {err}")
    return False

async def csfloat_send_steam_trade(client: SteamClient, trade_id, buyer_steam_id=None, trade_url=None, asset_id=None, trade_token=None):
    try:

        # Определение контекста игры, например, CS2
        game_context = AppContext.CS2  # Убедитесь, что это правильный контекст для вашего предмета

        # Получение вашего инвентаря
        my_inv, _, _ = await client.get_inventory(game_context,count=2000)

        # Проверка структуры предметов в инвентаре
        if not my_inv:
            print("Your inventory is empty or could not be loaded.")
            return False
        
         #wip compare to history offers

        # Попытка найти предмет по asset_id
        asset_id = list(asset_id)
        if not asset_id:  #if all items to trade on csfloat are already included in created trade offers.
            print("Nothing to give for trade offer.")
            return False
        asset_id_len=len(asset_id)
        # print(f"asset_id {asset_id}")
        print(f"asset_id_len {asset_id_len}")
        items_to_give=[]
        try:
            for tai in asset_id:
                items_to_give.append(next((item for item in my_inv if item.asset_id == tai)))
            # items_to_give = list((item for item in my_inv if item.asset_id == asset_id))
            items_to_give_len=len(items_to_give)
            # print(f"items_to_give {items_to_give}")
            print(f"items_to_give_len {items_to_give_len}")
            
            if asset_id_len!=items_to_give_len:
                print("Can't find all items to give.")
                return False

        except ValueError:
            # items_to_give = next((item for item in my_inv if item.asset_id == asset_id), None)
            pass

        if not items_to_give: #wip find missing items
            if asset_id_len==1:
                print(f"Item with asset_id {asset_id} not found in the inventory.")
            else:
                print(f"Item with asset_id {asset_id[0]} and {asset_id_len-1} other items not found in the inventory.")
            # print(f"Предмет с asset_id {asset_id} не найден в инвентаре.")
            return False
        if items_to_give_len>1:
            trades_num_other=items_to_give_len-1
            offer_message=f"CSFloat Market Trade Offer #{trade_id} and {trades_num_other} other items Thanks for using CSFloat!"
        else:
            offer_message=f"CSFloat Market Trade Offer #{trade_id}. Thanks for using CSFloat!"
        print(f"trade_id {trade_id} buyer_steam_id {buyer_steam_id} trade_url {trade_url} asset_id {asset_id} trade_token {trade_token} offer_message {offer_message}")
        # return #debug
        # Вызов make_trade_offer с использованием Steam ID или Trade URL
        if trade_url:
            # Отправка через трейд-ссылку
            offer_id = await client.make_trade_offer(
                trade_url,                     # Трейд-ссылка как первый позиционный аргумент
                to_give=items_to_give,
                to_receive=[],
                message=offer_message,
                confirm=False #debug
            )
        elif buyer_steam_id:
            # Отправка через Steam ID партнёра
            if trade_token:
                offer_id = await client.make_trade_offer(
                    buyer_steam_id,              # Steam ID партнёра как первый позиционный аргумент
                    to_give=items_to_give,
                    to_receive=[],
                    message=offer_message,
                    token=trade_token,             # Передача trade_token, если требуется
                    confirm=False #debug
                )
            else:
                offer_id = await client.make_trade_offer(
                    buyer_steam_id,              # Steam ID партнёра как первый позиционный аргумент
                    to_give=items_to_give,
                    to_receive=[],
                    message=offer_message,
                    confirm=False #debug
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
    except ConnectionError as connect_err:
        print(f"connection error occurred while sending trade offer: {connect_err}")
    except Exception as e:
        print(f"An error occurred while sending trade offer: {e}")
    return False

# Функция подтверждения трейдов, если требуется
async def confirm_trade(client: SteamGuardMixin):
    return#debug
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

async def get_actionable_trades_sell(session, csfloat_api_key,my_steam_id):
    trades_info = await get_trades(session, csfloat_api_key)
    if isinstance(trades_info, dict):
        trades_list = trades_info.get('trades', [])
        trades_list_sell = list(filter(lambda c: int(c['seller_id']) ==my_steam_id and not any2bool(c['wait_for_cancel_ping']), trades_list))
        return trades_list_sell
    else:
        print(f"Unexpected trades data format: {type(trades_info)}")
        return None

async def check_actionable_trades(session, csfloat_api_key, client: MySteamClient, shared_secret, identity_secret, processed_trades, check_interval_seconds,my_steam_id):
    user_info = await get_user_info(session, csfloat_api_key)
    # print(user_info)#debug
        
    if user_info and user_info.get('actionable_trades', 0) > 0:
        print("Actionable trades found, fetching trade details...")
        # print(trades_info)#debug
        # sys.exit()#debug
        trades_list_sell=await get_actionable_trades_sell(session, csfloat_api_key,my_steam_id)
        if trades_list_sell:
            # return#debug
            # print(trades_list_sell)#debug
            buyer_id_n_market_hash_name=[]
            index_excluded=[]
            offer_maker=[]
            trades_list_sell_to_accept=list(filter(lambda c: not c.get('accepted_at'), trades_list_sell))
            # print(trades_list_sell_to_accept) #debug
            if trades_list_sell_to_accept:
                trades_list_sell_to_accept_processing=trades_list_sell_to_accept
                trades_accept_loop_count=0
                while True:
                    # print("asfdsgsd.")
                    if trades_accept_loop_count>8:
                        print(f"trades_accept looped more than {trades_accept_loop_count} times. Stop for this check.")
                        return
                    if trades_accept_loop_count%3==0:
                        print("Updating the trade list.") #wip fetch new items
                        trades_list_sell_to_accept=list(filter(lambda c: not c.get('accepted_at'), await get_actionable_trades_sell(session, csfloat_api_key,my_steam_id)))
                        # print(trades_list_sell_to_accept)#debug
                        if not trades_list_sell_to_accept:
                            print("All accetable trade accepted.")
                            break

                    if isinstance(trades_list_sell_to_accept, list):
                        # print("afsfsdsdf.")
                        for trade in trades_list_sell_to_accept:
                            # print("asfsdggs.")
                            if isinstance(trade, dict):
                                trade_id = trade.get('id')
                                seller_id = int(trade.get('seller_id'))  # ID отправителя
                                buyer_id = int(trade.get('buyer_id'))    # ID получателя
                                asset_id = trade.get('contract', {}).get('item', {}).get('asset_id')
                                trade_token = trade.get('trade_token')  # Получаем trade_token
                                trade_url = trade.get('trade_url')      # Получаем trade_url
                                trade_state = trade.get('state')        # Получаем состояние трейда
                                # print("sgdgdfasd.")
                                if trade_id and seller_id and buyer_id and asset_id:
                                    print(f"Trade {trade_id} is a sold trade.")
                                    # print(f"Trade {trade_id} is a sold trade.")
                                    # continue#debug

                                    print(f"Accepting trade {trade_id}...")
                                    accept_result = await accept_trade(session, csfloat_api_key, trade_id=str(trade_id), trade_token=trade_token)

                                    if accept_result:
                                        print(f"Accepted trade {trade_id}...")
                                        trades_list_sell_to_accept_processing=list(filter(lambda c: c["id"] != trade_id, trades_list_sell_to_accept_processing))
                                        # print(f"{trades_list_sell_to_accept_processing}")#debug

                                    else:
                                        print(f"Failed to accept trade {trade_id}")
                            # print("asasfsf.")
                            await asyncio.sleep(0.23)
                            # await asyncio.sleep(230)
                            print("sdgsdgsgd.")
                        if not trades_list_sell_to_accept_processing:
                            print("All accetable trade accepted.")
                            break        
                        else:
                            trades_list_sell_to_accept=trades_list_sell_to_accept_processing
                            trades_accept_loop_count+=1
                            print("asfsdggs.")
                    else:
                        print(f"Unexpected trades list format: {type(trades_list_sell)}")

            
            # print("assgdfdf.")
            # await asyncio.sleep(50000)
            # print("asfgdfd.")
            trades_list_sell_accepted=list(filter(lambda c: c.get('accepted_at'), await get_actionable_trades_sell(session, csfloat_api_key,my_steam_id)))
            if trades_list_sell_accepted:
                for i in range(len(trades_list_sell_accepted)):
                    if i not in index_excluded:
                        asset_id_list_temp=[]
                        for ii in range(len(trades_list_sell_accepted)):
                            if trades_list_sell_accepted[ii]['buyer_id']==trades_list_sell_accepted[i]['buyer_id'] and trades_list_sell_accepted[ii]["contract"]["item"]["market_hash_name"]==trades_list_sell_accepted[i]["contract"]["item"]["market_hash_name"]:
                                asset_id_list_temp.append(int(trades_list_sell_accepted[ii]["contract"]["item"]["asset_id"]))
                                index_excluded.append(ii)
                        offer_maker.append({"trade_id":int(trades_list_sell_accepted[i]["id"]),"buyer_id":int(trades_list_sell_accepted[i]["buyer_id"]),"seller_id":int(trades_list_sell_accepted[i]["seller_id"]),"asset_id":asset_id_list_temp,"trade_token":trades_list_sell_accepted[i]["trade_token"],"trade_url":trades_list_sell_accepted[i]["trade_url"],"accepted_at":trades_list_sell_accepted[i].get('accepted_at'),"trade_state":trades_list_sell_accepted[i]["state"]})
                        print(index_excluded)
                print(offer_maker)
            else:
                return None
            retryCount=0
            while True:
                try:
                    sentto, _, next_cursorvar = await client.get_trade_offers(active_only=False,received=False)
                except aiohttp.ClientResponseError as http_err:
                    print(f"HTTP error occurred while fetching Steam trade offers sent: {http_err}")
                except ConnectionError as connect_err:
                    print(f"connection error occurred while fetching Steam trade offers sent: {connect_err}")
                except Exception as err:
                    print(f"Other error occurred while fetching Steam trade offers sent: {err}")
                else:
                    break
                retryCount+=1
                if retryCount >5:
                    print("Failed too many times.")
                    return None
                await asyncio.sleep(50)
            for omi in range(len(offer_maker)):
            # for omi in offer_maker:
                asset_id_sent=[]
                for toi in range(len(sentto)):
                    if sentto[toi].partner_id >76561197960265728:
                        sentto[toi].partner_id-=76561197960265728
                    if offer_maker[omi]["buyer_id"] >76561197960265728:
                        offer_maker[omi]["buyer_id"]-=76561197960265728
                    if sentto[toi].status in (TradeOfferStatus.ACCEPTED,TradeOfferStatus.ACTIVE,TradeOfferStatus.CONFIRMATION_NEED) and sentto[toi].partner_id==offer_maker[omi]["buyer_id"]:                  
                        for itg in sentto[toi].items_to_give:
                            asset_id_sent.append(itg.asset_id)
                        if sentto[toi].status == TradeOfferStatus.CONFIRMATION_NEED:
                            asset_id_sent_check=asset_id_sent
                            # asset_id_sent_check.append(1522523)#debug
                            for itgom in offer_maker[omi]["asset_id"]:
                                asset_id_sent_check=list(filter(lambda c: c!=itgom,asset_id_sent_check))
                            if not asset_id_sent_check:
                                print("Trade offer to confirm matched.")
                                await confirm_trade_offer_retry(client,sentto[toi].trade_offer_id)
                            else:
                                print("Trade offer to confirm not matched.")

                print(asset_id_sent)
                if asset_id_sent:
                    for i in asset_id_sent:
                        offer_maker[omi]["asset_id"]=list(filter(lambda c: c!=i,offer_maker[omi]["asset_id"]))
                # if not offer_maker[omi]["asset_id"]:
                print(offer_maker[omi]["asset_id"])
            print(offer_maker)
            # for item in trades_list_sell_accepted:
            # extItem={"buyer_id":item['buyer_id'],"market_hash_name":item["contract"]["item"]["market_hash_name"],}
            #     buyer_id_n_market_hash_name.append(extItem)
            # buyer_id_n_market_hash_name=[dict(t) for t in {tuple(d.items()) for d in buyer_id_n_market_hash_name}]
            # # buyer_id_n_market_hash_name=list(OrderedDict.fromkeys(buyer_id_n_market_hash_name))
            # # buyer_id_n_market_hash_name=list(dict.fromkeys(buyer_id_n_market_hash_name))
            # print(buyer_id_n_market_hash_name)
            # for item in buyer_id_n_market_hash_name:
            #     findItem=next((filter(lambda c: c['buyer_id'] ==item['buyer_id'] and c["contract"]["item"]["market_hash_name"]==item["market_hash_name"], trades_list_sell_accepted)))
            # item.update({"trade_id": findItem["id"], "seller_id": findItem["seller_id"], "asset_id": findItem["contract"]["item"]["asset_id"], "trade_token": findItem["trade_token"], "trade_url": findItem["trade_url"], "accepted_at": findItem["accepted_at"], "trade_state": findItem["trade_state"]}) #wip multiple asset_id
            #     offer_maker.append(item)
            # print(offer_maker)
            # return #debug wip complete retry if confirm failed
            """
            if next(filter(lambda c: c.status==TradeOfferStatus.CONFIRMATION_NEED ,sentto)):
                retryCount=0
                while True:
                    if retryCount>4:
                        print("Failed too many times.")
                        sys.exit()
                    try:
                        confirmations=await client.get_confirmations(update_listings=False) # wip attr
                        trades_to_confirm=await client.get_confirmations(update_listings=False)
                        # print(fr"aaa11a.")
                        if trades_to_confirm:
                            # print(fr"aaa111.")
                            trades_to_confirm_correct = list(filter(lambda c: c.type == ConfirmationType.TRADE, trades_to_confirm)) # c.headline: 'Selling for ¥ 1.11'. c.summary: EconItem.description.market_hash_name
                            if trades_to_confirm_correct:
                                # print(fr"aaa112.")
                                await client.allow_multiple_confirmations(trades_to_confirm_correct)
                            else:
                                print("No matched confirmation found.")
                                break
                        else:
                            print("No matched confirmation found.")
                            break
                    except Exception as e:
                        print(fr"{type(e)} {e}")
                        # writeToFile(os.path.join(LOGS_FOLDER, "1.log"),fr"{type(e)} {e}","a")
                        await asyncio.sleep(5)
                    else:
                        break
                    retryCount+=1

            """
            if isinstance(offer_maker, list):
                for trade in offer_maker:
                    if isinstance(trade, dict):
                        trade_id = trade.get('trade_id')

                        """
                        # Проверка, был ли уже обработан этот trade_id
                        if str(trade_id) in processed_trades:
                            print(f"Trade {trade_id} has already been processed. Skipping.")
                            continue  # Пропустить уже обработанные трейды
                        """

                        seller_id = int(trade.get('seller_id'))  # ID отправителя
                        buyer_id = int(trade.get('buyer_id'))    # ID получателя
                        asset_id = trade.get('asset_id')
                        trade_token = trade.get('trade_token')  # Получаем trade_token
                        trade_url = trade.get('trade_url')      # Получаем trade_url
                        accepted_at = trade.get('accepted_at')  # Получаем время принятия, если есть
                        trade_state = trade.get('trade_state')        # Получаем состояние трейда
                        # print(trade)#debug
                        # continue#debug wip fix the bug that can't accept multiple trades.
                        
                        # print(f"seller_id {type(seller_id)} my_steam_id {type(my_steam_id)}")
                        if seller_id !=my_steam_id:
                            print(f"Trade {trade_id} is not a sold trade, skipping.")
                            continue

                        """
                        if trade_state == "verified":
                            # If the trade is already verified, add it to processed and skip it
                            processed_trades.add(str(trade_id))

                            continue
                        """

                        if trade_id and seller_id and buyer_id and asset_id:
                            print(f"Trade {trade_id} is a sold trade, proceeding.")
                            # print(f"Trade {trade_id} is a sold trade.")
                            # continue#debug wip retry if confirm failed

                            if accepted_at:
                                # The offer has already been accepted. Sending a trade offer
                                print(f"Trade {trade_id} has already been accepted. Proceed to sending a trade offer.")
                                offer_id = await csfloat_send_steam_trade( #wip if items disappered
                                    client,
                                    trade_id=int(trade_id),        # Передаём trade_id как строку
                                    buyer_steam_id=int(buyer_id),  # Передаём buyer_id как целое число
                                    asset_id=asset_id,
                                    trade_token=trade_token,
                                    trade_url=trade_url
                                )
                                # return#debug

                                if offer_id:
                                    # Автоматически подтверждаем трейды
                                    # await confirm_trade(client)
                                    await confirm_trade_offer_retry(client,offer_id)
                                else:
                                    print(f"Failed to send trade for {trade_id}")

                        # Добавляем trade_id в processed_trades независимо от результата
                        # processed_trades.add(str(trade_id))
                        
            else:
                print(f"Unexpected trade maker list format: {type(offer_maker)}")
        else:
            print("No actionable sold trades at the moment.")
    else:
        print(f"No actionable trades at the moment. Waiting for {check_interval_seconds} seconds before next check.")
def any2bool(v):
  return str(v).lower() in ("yes", "true", "t", "1")
def readConfigValue(configJson,jsonKey):
    try:
        jsonValue= configJson[jsonKey]
    except Exception as err:
        print(f"Couldn't load the item from the config file: {jsonKey}")
    else:
        return jsonValue
async def main():
    config = load_steam_config()  # Загрузка конфигурации

    csfloat_api_key = config['csfloat_api_key']
    steam_api_key = config.get('steam_api_key')
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
    check_interval_seconds_random = any2bool(config.get('check_interval_seconds_random'))
    if check_interval_seconds_random:
        check_interval_seconds_random_min=config.get('check_interval_seconds_random_min')
        check_interval_seconds_random_max=config.get('check_interval_seconds_random_max')
    check_interval_seconds=config.get('check_interval_seconds')
    if not check_interval_seconds:
        check_interval_seconds = 700  # Вы можете легко изменить это значение
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
    if cilent_proxy and steam_use_proxy:
        MySteamClient.proxy=cilent_proxy
        print("steam proxy true")
        # print(client.proxy)
    else:
        print("steam proxy false")
    # sys.exit()
    # Восстановление cookies, если они существуют


    if COOKIE_FILE.is_file():
        try:
            with COOKIE_FILE.open("r") as f:
                cookies = json.load(f)
            await restore_from_cookies_retry(cookies, client)
        except Exception as err:
            print(f"{err}")
            await steam_client_login_retry(client) #wip fix 502 errors
    else:
        await steam_client_login_retry(client)

    # Загрузка обработанных трейдов
    processed_trades = load_processed_trades()

    sessionConnector = ProxyConnector.from_url(cilent_proxy, ttl_dns_cache=300) if cilent_proxy else aiohttp.TCPConnector(
        resolver=aiohttp.resolver.AsyncResolver(),
        limit_per_host=50
    )
    
    async with aiohttp.ClientSession(connector=sessionConnector) as session:
        try:
            while True:
                if check_interval_seconds_random:
                    check_interval_seconds=round(random.uniform(check_interval_seconds_random_min, check_interval_seconds_random_max),4)
                    print(f"check_interval_seconds: {check_interval_seconds}")
                await check_actionable_trades(
                    session,
                    csfloat_api_key,
                    client,
                    shared_secret,
                    identity_secret,
                    processed_trades,           # Передача набора обработанных трейдов
                    check_interval_seconds,      # Передача продолжительности ожидания
                    my_steam_id=steam_id
                )
                save_processed_trades(processed_trades)  # Сохранение после каждой проверки
                await asyncio.sleep(check_interval_seconds)  # Ожидание заданное количество минут
        finally:
            # Сохранение cookies
            with COOKIE_FILE.open("w") as f:
                json.dump(get_jsonable_cookies(client.session), f, indent=2)

            await client.session.close()

if __name__ == "__main__":
    asyncio.run(main())
