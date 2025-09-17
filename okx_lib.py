import requests
import time
import base64
import hmac
import hashlib
import json
import websocket
import threading

# ============ 配置 ============
API_KEY = "你的APIKEY"
API_SECRET = "你的SECRET"
PASSPHRASE = "你的PASSPHRASE"
BASE_URL = "https://www.okx.com"
WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"
WS_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"

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
    resp = requests.get(url, headers=_headers("GET", path))
    return resp.json()

def get_positions(instId=None):
    path = "/api/v5/account/positions"
    if instId:
        path += f"?instId={instId}"
    url = BASE_URL + path
    resp = requests.get(url, headers=_headers("GET", path))
    return resp.json()

def get_price(instId="BTC-USDT"):
    path = f"/api/v5/market/ticker?instId={instId}"
    url = BASE_URL + path
    resp = requests.get(url)
    data = resp.json()
    if data.get("data"):
        return float(data["data"][0]["last"])
    return None

def place_order(instId="BTC-USDT-SWAP", tdMode="cross", side="buy", ordType="market", sz="1"):
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
    resp = requests.post(url, headers=_headers("POST", path, body_str), data=body_str)
    return resp.json()

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

def on_open_public(ws):
    # 订阅 BTC-USDT 实时价格
    sub = {"op": "subscribe", "args": [{"channel": "tickers", "instId": "BTC-USDT"}]}
    ws.send(json.dumps(sub))

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
    print("📊 当前仓位:", get_positions("BTC-USDT-SWAP"))
    print("📈 当前价格:", get_price("BTC-USDT"))

    start_ws()

    while True:
        time.sleep(10)