


import requests
import time
import base64
import hmac
import hashlib
import json
import asyncio
import websockets

class OKXAccount:
    BASE_URL = "https://www.okx.com"
    WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"
    WS_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"

    def __init__(self, api_key, api_secret, passphrase, simulated=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.simulated = simulated

    # ============ 签名工具 ============
    def _sign(self, message: str):
        return base64.b64encode(
            hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()

    def _headers(self, method, request_path, body=""):
        ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        prehash = f"{ts}{method}{request_path}{body}"
        sign = self._sign(prehash)
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }
        if self.simulated:
            headers["x-simulated-trading"] = "1"
        return headers

    def _request(self, method, path, params=None, body=None, private=False):
        url = self.BASE_URL + path
        body_str = json.dumps(body) if body else ""
        headers = self._headers(method, path, body_str) if private else {}
        resp = requests.request(method, url, headers=headers, params=params, data=body_str)
        return resp.json()

    # ============ REST API ============
    def get_balance(self, ccy="USDT"):
        path = f"/api/v5/account/balance?ccy={ccy}"
        return self._request("GET", path, private=True)

    def get_positions(self, instId=None):
        path = "/api/v5/account/positions"
        if instId:
            path += f"?instId={instId}"
        return self._request("GET", path, private=True)

    def get_price(self, instId="BTC-USDT"):
        path = "/api/v5/market/ticker"
        params = {"instId": instId}
        return self._request("GET", path, params=params, private=False)

    def place_order(self, instId, tdMode="cross", side="buy", ordType="market", sz="1", posSide=None, px=None):
        path = "/api/v5/trade/order"
        body = {
            "instId": instId,
            "tdMode": tdMode,
            "side": side,
            "ordType": ordType,
            "sz": sz
        }
        if posSide:
            body["posSide"] = posSide
        if px:
            body["px"] = px
        return self._request("POST", path, body=body, private=True)

    def cancel_order(self, instId, ordId=None, clOrdId=None):
        path = "/api/v5/trade/cancel-order"
        body = {"instId": instId}
        if ordId:
            body["ordId"] = ordId
        if clOrdId:
            body["clOrdId"] = clOrdId
        return self._request("POST", path, body=body, private=True)

    def query_order(self, instId, ordId=None, clOrdId=None):
        path = "/api/v5/trade/order"
        params = {"instId": instId}
        if ordId:
            params["ordId"] = ordId
        if clOrdId:
            params["clOrdId"] = clOrdId
        return self._request("GET", path, params=params, private=True)

    # ============ WebSocket ============
    def _login_params(self):
        ts = str(time.time())
        sign = self._sign(ts + "GET" + "/users/self/verify")
        args = {
            "apiKey": self.api_key,
            "passphrase": self.passphrase,
            "timestamp": ts,
            "sign": sign
        }
        if self.simulated:
            args["x-simulated-trading"] = "1"
        return {"op": "login", "args": [args]}

    async def _ws_public(self, instId):
        async with websockets.connect(self.WS_PUBLIC) as ws:
            sub = {"op": "subscribe", "args": [{"channel": "tickers", "instId": instId}]}
            await ws.send(json.dumps(sub))
            async for msg in ws:
                data = json.loads(msg)
                if "arg" in data and data["arg"]["channel"] == "tickers":
                    price = data["data"][0]["last"]
                    print(f"📈 实时价格 {instId} = {price}")

    async def _ws_private(self):
        async with websockets.connect(self.WS_PRIVATE) as ws:
            # 登录
            await ws.send(json.dumps(self._login_params()))
            # 订阅仓位
            sub = {"op": "subscribe", "args": [{"channel": "positions", "instType": "SWAP"}]}
            await ws.send(json.dumps(sub))
            async for msg in ws:
                data = json.loads(msg)
                if "arg" in data and data["arg"]["channel"] == "positions":
                    pos = data["data"][0]
                    print(f"📊 仓位变化: {pos}")

    async def start_ws(self, instId="BTC-USDT"):
        await asyncio.gather(
            self._ws_public(instId),
            self._ws_private()
        )