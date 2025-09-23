import requests
import time
from datetime import datetime, timezone
import base64
import hmac
import hashlib
import json
from urllib.parse import urlencode
import asyncio
import websockets
import logging

class OKXAccount:
    BASE_URL = "https://www.okx.com"
    WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"
    WS_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"
    WS_BUSINESS = "wss://ws.okx.com:8443/ws/v5/business"
    # 模拟盘（paper） WS endpoints
    SIM_WS_PUBLIC = "wss://wspap.okx.com:8443/ws/v5/public"
    SIM_WS_PRIVATE = "wss://wspap.okx.com:8443/ws/v5/private"
    SIM_WS_BUSINESS = "wss://wspap.okx.com:8443/ws/v5/business"

    def __init__(self, api_key, api_secret, passphrase, simulated=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.simulated = simulated
        # logger: DEBUG 时会记录 headers/登录参数（会对敏感字段进行遮掩）
        self.logger = logging.getLogger(__name__)
        # 实例级别的 WS endpoints（根据 simulated 切换）
        if self.simulated:
            self.ws_public = self.SIM_WS_PUBLIC
            self.ws_private = self.SIM_WS_PRIVATE
            self.ws_business = self.SIM_WS_BUSINESS
        else:
            self.ws_public = self.WS_PUBLIC
            self.ws_private = self.WS_PRIVATE
            self.ws_business = self.WS_BUSINESS

    # ============ 签名工具 ============
    def _sign(self, message: str):
        return base64.b64encode(
            hmac.new(self.api_secret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()

    def _now_iso(self):
        """生成符合 OKX 要求的 ISO8601 UTC 毫秒时间戳

        示例格式: 2025-09-22T06:37:18.359Z
        """
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _headers(self, method, request_path, body=""):
        # ts = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        # ts = str(time.time())
        ts = self._now_iso()
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
        # 仅在 DEBUG 级别记录（并遮掩敏感字段）
        if self.logger.isEnabledFor(logging.DEBUG):
            try:
                masked = self._mask_sensitive(headers)
                self.logger.debug("Request headers for %s %s: %s", method, request_path, json.dumps(masked, ensure_ascii=False))
            except Exception:
                # 避免 logging 导致请求失败
                pass
        return headers

    def _mask_sensitive(self, d: dict):
        """Return a copy of dict with sensitive values masked for safe debug logging."""
        masked = {}
        for k, v in d.items():
            kl = k.lower()
            if any(x in kl for x in ("key", "sign", "passphrase", "secret", "api")):
                s = str(v or "")
                if len(s) <= 8:
                    masked[k] = "****"
                else:
                    masked[k] = s[:4] + "..." + s[-4:]
            else:
                masked[k] = v
        return masked

    def _request(self, method, path, params=None, body=None, private=False):
        url = self.BASE_URL + path
        body_str = json.dumps(body) if body else ""

        # 如果是私有请求且存在 params，把 params 编码并追加到 request path 用于签名
        request_path_for_sign = path
        if private and params:
            # urlencode 保持参数顺序不变；如果需要按字母排序可改为 sorted(params.items())
            qs = urlencode(params, doseq=True)
            request_path_for_sign = path + "?" + qs

        headers = self._headers(method, request_path_for_sign, body_str) if private else {}
        # DEBUG 时记录请求体（已遮掩敏感字段）
        if self.logger.isEnabledFor(logging.DEBUG) and private:
            try:
                masked_headers = self._mask_sensitive(headers)
                masked_body = body if body is not None else {}
                self.logger.debug("HTTP %s %s\nheaders=%s\nbody=%s", method, path, json.dumps(masked_headers, ensure_ascii=False), json.dumps(masked_body, ensure_ascii=False))
            except Exception:
                pass

        resp = requests.request(method, url, headers=headers, params=params, data=body_str)
        return resp.json()

    # ============ REST API ============
    def get_balance(self, ccy=None):
        """
        获取交易账户中资金余额信息
        ccy: 币种字符串，如 "BTC" 或 "BTC,ETH"；默认 None 查询所有资产
        """
        path = "/api/v5/account/balance"
        if ccy:
            path += f"?ccy={ccy}"
        return self._request("GET", path, private=True)

    def get_positions(self, instType=None, instId=None, posId=None):
        """
        获取账户持仓信息
        instType: 产品类型 (MARGIN / SWAP / FUTURES / OPTION)
        instId: 单个或多个交易产品ID (逗号分隔，≤10)
        posId: 单个或多个持仓ID (逗号分隔，≤20)
        """
        path = "/api/v5/account/positions"
        params = {}
        if instType:
            params["instType"] = instType
        if instId:
            params["instId"] = instId
        if posId:
            params["posId"] = posId
        return self._request("GET", path, params=params, private=True)

    def get_account_config(self):
        """
        查看账户配置
        文档: GET /api/v5/account/config

        返回示例参见 OKX 文档，包含 acctLv、posMode、perm 等字段。
        """
        path = "/api/v5/account/config"
        return self._request("GET", path, private=True)

    def get_trade_fee(self, instType, instId=None, instFamily=None, ruleType=None):
        """
        获取当前账户交易手续费费率
        文档: GET /api/v5/account/trade-fee

        参数:
        - instType: 必填，SPOT/MARGIN/SWAP/FUTURES/OPTION
        - instId: 选填，产品ID（仅适用于币币/币币杠杆）
        - instFamily: 选填，交易品种（适用于交割/永续/期权，如 BTC-USD）
        - ruleType: 选填，normal 或 pre_market（与 instId/instFamily 互斥）
        """
        if not instType:
            raise ValueError("instType is required")
        if ruleType and (instId or instFamily):
            raise ValueError("ruleType cannot be used with instId/instFamily")

        path = "/api/v5/account/trade-fee"
        params = {"instType": instType}
        if instId:
            params["instId"] = instId
        if instFamily:
            params["instFamily"] = instFamily
        if ruleType:
            params["ruleType"] = ruleType
        return self._request("GET", path, params=params, private=True)

    def get_price(self, instId="BTC-USDT"):
        path = "/api/v5/market/ticker"
        params = {"instId": instId}
        return self._request("GET", path, params=params, private=False)

    def place_order(
        self, instId, tdMode="cross", side="buy", ordType="market", sz="1",
        px=None, posSide=None, ccy=None, clOrdId=None, tag=None, reduceOnly=None,
        tgtCcy=None, banAmend=None, pxAmendType=None, tradeQuoteCcy=None,
        stpMode=None, attachAlgoOrds=None
    ):
        """
        下单接口（支持完整参数）
        文档: https://www.okx.com/docs-v5/zh/#rest-api-trade-place-order

        instId: 产品ID，如 BTC-USDT
        tdMode: 交易模式 (cross / isolated / cash / spot_isolated)
        side: buy 或 sell
        ordType: market / limit / post_only / fok / ioc / optimal_limit_ioc 等
        sz: 委托数量
        px: 委托价格，仅限价单/IOC等需要
        其他参数参考官方文档
        """
        path = "/api/v5/trade/order"
        body = {
            "instId": instId,
            "tdMode": tdMode,
            "side": side,
            "ordType": ordType,
            "sz": sz
        }
        if px is not None:
            body["px"] = px
        if posSide is not None:
            body["posSide"] = posSide
        if ccy is not None:
            body["ccy"] = ccy
        if clOrdId is not None:
            body["clOrdId"] = clOrdId
        if tag is not None:
            body["tag"] = tag
        if reduceOnly is not None:
            body["reduceOnly"] = reduceOnly
        if tgtCcy is not None:
            body["tgtCcy"] = tgtCcy
        if banAmend is not None:
            body["banAmend"] = banAmend
        if pxAmendType is not None:
            body["pxAmendType"] = pxAmendType
        if tradeQuoteCcy is not None:
            body["tradeQuoteCcy"] = tradeQuoteCcy
        if stpMode is not None:
            body["stpMode"] = stpMode
        if attachAlgoOrds is not None:
            body["attachAlgoOrds"] = attachAlgoOrds

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
        # WebSocket login requires timestamp as Unix epoch seconds (string),
        # e.g. Date.now()/1000 in JS. Use float seconds to include milliseconds.
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
        # 仅在 DEBUG 级别记录（遮掩敏感字段）
        if self.logger.isEnabledFor(logging.DEBUG):
            try:
                masked = self._mask_sensitive(args)
                self.logger.debug("WS login args: %s", json.dumps(masked, ensure_ascii=False))
            except Exception:
                pass
        return {"op": "login", "args": [args]}

    async def _ws_public(self, instId):
        async with websockets.connect(self.ws_public) as ws:
            sub = {"op": "subscribe", "args": [{"channel": "tickers", "instId": instId}]}
            await ws.send(json.dumps(sub))
            async for msg in ws:
                try:
                    data = json.loads(msg)
                except Exception:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("Failed to parse WS public message: %s", msg)
                    continue

                if "arg" in data and data["arg"].get("channel") == "tickers":
                    arr = data.get("data")
                    if arr and isinstance(arr, list) and len(arr) > 0 and "last" in arr[0]:
                        price = arr[0]["last"]
                        print(f"📈 实时价格 {instId} = {price}")
                    else:
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug("WS tickers message without price field: %s", data)

    async def _ws_private(self):
        async with websockets.connect(self.ws_private) as ws:
            # 登录
            await ws.send(json.dumps(self._login_params()))
            # 订阅仓位
            sub = {"op": "subscribe", "args": [{"channel": "positions", "instType": "SWAP"}]}
            await ws.send(json.dumps(sub))
            async for msg in ws:
                try:
                    data = json.loads(msg)
                except Exception:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("Failed to parse WS private message: %s", msg)
                    continue

                if "arg" in data and data["arg"].get("channel") == "positions":
                    arr = data.get("data")
                    if arr and isinstance(arr, list) and len(arr) > 0:
                        pos = arr[0]
                        print(f"📊 仓位变化: {pos}")
                    else:
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug("WS positions message without data: %s", data)

    async def start_ws(self, instId="BTC-USDT"):
        await asyncio.gather(
            self._ws_public(instId),
            self._ws_private()
        )
