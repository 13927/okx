import requests
import time
import os
from pathlib import Path
import base64
import hmac
import hashlib
import json
import websocket
import threading

# ============ 配置 ============
# 尝试从 .env 文件加载（如果安装了 python-dotenv），否则使用环境变量，最后回退到占位字符串
try:
    from dotenv import load_dotenv
    # 加载仓库根目录下的 .env（脚本所在目录）
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except Exception:
    # 如果没有安装 python-dotenv，也可以直接依赖环境变量
    pass

API_KEY = os.getenv('API_KEY', "你的APIKEY")
API_SECRET = os.getenv('API_SECRET', "你的SECRET")
PASSPHRASE = os.getenv('PASSPHRASE', "你的PASSPHRASE")
BASE_URL = os.getenv('BASE_URL', "https://www.okx.com")
WS_PUBLIC = os.getenv('WS_PUBLIC', "wss://ws.okx.com:8443/ws/v5/public")
WS_PRIVATE = os.getenv('WS_PRIVATE', "wss://ws.okx.com:8443/ws/v5/private")

# ============ 签名工具 ============
def _sign(message: str, secret_key: str):
    return base64.b64encode(
        hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()

def _headers(method, request_path, body=""):
    ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    prehash = f"{ts}{method}{request_path}{body}"
    sign = _sign(prehash, API_SECRET)
    return {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# ============ REST 封装 ============
def get_balance(ccy="USDT"):
    path = f"/api/v5/account/balance?ccy={ccy}"
    url = BASE_URL + path
    try:
        resp = requests.get(url, headers=_headers("GET", path))
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def get_positions(instId=None):
    path = "/api/v5/account/positions"
    if instId:
        path += f"?instId={instId}"
    url = BASE_URL + path
    try:
        resp = requests.get(url, headers=_headers("GET", path))
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def get_price(instId="SOL-USDC"):
    path = f"/api/v5/market/ticker?instId={instId}"
    url = BASE_URL + path
    try:
        resp = requests.get(url)
        data = resp.json()
        if data.get("data"):
            return float(data["data"][0]["last"])
        return None
    except Exception as e:
        return {"error": str(e)}

def place_order(instId="SOL-USDC-SWAP", tdMode="cross", side="buy", ordType="market", sz="1"):
    path = "/api/v5/trade/order"
    url = BASE_URL + path
    body = {
        "instId": instId,
        "tdMode": tdMode,
        "side": side,
        "ordType": ordType,
        "sz": sz
    }
    body_str = json.dumps(body)
    try:
        resp = requests.post(url, headers=_headers("POST", path, body_str), data=body_str)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def get_orders(instId=None, state="live"):
    path = f"/api/v5/trade/orders-pending?state={state}"
    if instId:
        path += f"&instId={instId}"
    url = BASE_URL + path
    try:
        resp = requests.get(url, headers=_headers("GET", path))
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def cancel_order(instId, ordId):
    path = "/api/v5/trade/cancel-order"
    url = BASE_URL + path
    body = {"instId": instId, "ordId": ordId}
    body_str = json.dumps(body)
    try:
        resp = requests.post(url, headers=_headers("POST", path, body_str), data=body_str)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def get_fills(instId=None, limit=20):
    path = f"/api/v5/trade/fills?limit={limit}"
    if instId:
        path += f"&instId={instId}"
    url = BASE_URL + path
    try:
        resp = requests.get(url, headers=_headers("GET", path))
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# ============ WebSocket 封装 ============
def login_params():
    ts = str(time.time())
    sign = _sign(ts + "GET" + "/users/self/verify", API_SECRET)
    return {
        "op": "login",
        "args": [{
            "apiKey": API_KEY,
            "passphrase": PASSPHRASE,
            "timestamp": ts,
            "sign": sign
        }]
    }

def on_message(ws, message):
    msg = json.loads(message)
    if "event" in msg:
        print("系统消息:", msg)
        return

    if "arg" in msg and "data" in msg:
        channel = msg["arg"]["channel"]
        if channel == "tickers":
            price = msg["data"][0]["last"]
            print(f"📈 实时价格 {msg['arg']['instId']} = {price}")
        elif channel == "positions":
            pos = msg["data"][0]
            print(f"📊 仓位变化: {pos}")
        elif channel == "books":
            bids = msg["data"][0]["bids"]
            asks = msg["data"][0]["asks"]
            if bids and asks:
                print(f"💎盘口: 买一 {bids[0]} / 卖一 {asks[0]}")

def on_open_public(ws):
    # 订阅 SOL-USDC 实时价格
    sub = {"op": "subscribe", "args": [{"channel": "tickers", "instId": "SOL-USDC"}]}
    ws.send(json.dumps(sub))
    # 订阅深度
    sub_book = {"op": "subscribe", "args": [{"channel": "books", "instId": "SOL-USDC"}]}
    ws.send(json.dumps(sub_book))

def on_open_private(ws):
    # 登录
    ws.send(json.dumps(login_params()))
    time.sleep(1)
    # 订阅仓位变化
    sub = {"op": "subscribe", "args": [{"channel": "positions", "instType": "SWAP"}]}
    ws.send(json.dumps(sub))

def start_ws():
    # 公共WS（行情）
    t1 = threading.Thread(target=lambda: websocket.WebSocketApp(
        WS_PUBLIC,
        on_message=on_message,
        on_open=on_open_public
    ).run_forever())
    t1.start()

    # 私有WS（仓位）
    t2 = threading.Thread(target=lambda: websocket.WebSocketApp(
        WS_PRIVATE,
        on_message=on_message,
        on_open=on_open_private
    ).run_forever())
    t2.start()

# ============ 示例 ============
if __name__ == "__main__":
    print("💰 账户余额:", get_balance("USDT"))
    print("📊 当前仓位:", get_positions("SOL-USDC-SWAP"))
    print("📈 当前价格:", get_price("SOL-USDC"))

    start_ws()

    while True:
        time.sleep(10)