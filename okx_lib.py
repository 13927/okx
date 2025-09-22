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

API_KEY = os.getenv('OKX_API_KEY', "你的APIKEY")
API_SECRET = os.getenv('OKX_API_SECRET', "你的SECRET")
PASSPHRASE = os.getenv('OKX_PASSPHRASE', "你的PASSPHRASE")
BASE_URL = os.getenv('OKX_BASE_URL', "https://www.okx.com")
WS_PUBLIC = os.getenv('OKX_WS_PUBLIC', "wss://ws.okx.com:8443/ws/v5/public")
WS_PRIVATE = os.getenv('OKX_WS_PRIVATE', "wss://ws.okx.com:8443/ws/v5/private")

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

def place_order(instId="SOL-USDC-SWAP", tdMode="cross", side="buy", ordType="market", sz="1", px=None, posSide=None, reduceOnly=False):
    """
    Place an order.

    Args:
      instId: instrument id, e.g. "SOL-USDC-SWAP" for swap.
      tdMode: trading mode, e.g. "cross" or "isolated".
      side: "buy" or "sell". For opening a short position usually use side="sell".
      ordType: "market" or "limit".
      sz: size (quantity) as string or number.
      px: price for limit orders (optional).
      posSide: optional, "long" or "short" in dual-side position mode.
      reduceOnly: optional bool, set True to mark order as reduce-only.

    Note: behaviour depends on your OKX account/market settings (single-side vs dual-side). If your account uses
    dual-side (hedged) mode and you need to explicitly open a short, pass posSide="short" and side="sell".
    """
    path = "/api/v5/trade/order"
    url = BASE_URL + path
    body = {
        "instId": instId,
        "tdMode": tdMode,
        "side": side,
        "ordType": ordType,
        "sz": str(sz)
    }

    # 可选参数
    if px is not None:
        # OKX 接口期望字符串形式的价格
        body["px"] = str(px)
    if posSide is not None:
        # "long" or "short"（仅在双向持仓模式需要）
        body["posSide"] = posSide
    if reduceOnly:
        # 标记为只减仓（布尔值或字符串均可，API 会接受 true/false）
        body["reduceOnly"] = True

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

def build_order_payload(instId="SOL-USDC-SWAP", tdMode="cross", side="buy", ordType="market", sz="1", px=None, posSide=None, reduceOnly=False):
    """Return the order payload dictionary without sending it. Useful for testing payload composition."""
    body = {
        "instId": instId,
        "tdMode": tdMode,
        "side": side,
        "ordType": ordType,
        "sz": str(sz)
    }
    if px is not None:
        body["px"] = str(px)
    if posSide is not None:
        body["posSide"] = posSide
    if reduceOnly:
        body["reduceOnly"] = True
    return body

# ============ 示例 ============
if __name__ == "__main__":
    print("💰 账户余额:", get_balance("USDT"))
    print("📊 当前仓位:", get_positions("SOL-USDC-SWAP"))
    print("📈 当前价格:", get_price("SOL-USDC"))

    start_ws()

    # demo: 构造一个开空（卖空）限价单的 payload（仅打印，不发送）
    demo_payload = build_order_payload(instId="SOL-USDC-SWAP", tdMode="cross", side="sell", ordType="limit", sz=1, px=6.5, posSide="short", reduceOnly=False)
    print("示例下单 payload (开空):", json.dumps(demo_payload, ensure_ascii=False))

    # keep WS running
    while True:
        time.sleep(10)