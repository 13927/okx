import json
import time
from okx.api import account as AccountModule
from okx.api import trade as TradeModule
from okx.api import market as MarketModule
from okx.api import public as PublicModule
# note: the installed okx package doesn't expose a top-level WebSocket module named WebSocket
# The official package uses different modules (or separate libraries) for websocket; keep a placeholder
WebSocket = None

# ============ 配置 ============
API_KEY = "你的APIKEY"
API_SECRET = "你的SECRET"
PASSPHRASE = "你的PASSPHRASE"
IS_SANDBOX = False   # True=模拟盘，False=实盘

# 账户 & 下单客户端
# The installed okx package exposes classes named Account, Trade, Market in the okx.api subpackages.
# These classes expect configuration via a Client or direct init depending on version. We'll try the high-level classes first.
try:
    accountAPI = AccountModule.Account(API_KEY, API_SECRET, PASSPHRASE, IS_SANDBOX)
except Exception:
    # fallback to Client if available
    try:
        accountAPI = AccountModule.Client(API_KEY, API_SECRET, PASSPHRASE, IS_SANDBOX)
    except Exception:
        accountAPI = None

try:
    tradeAPI = TradeModule.Trade(API_KEY, API_SECRET, PASSPHRASE, IS_SANDBOX)
except Exception:
    try:
        tradeAPI = TradeModule.Client(API_KEY, API_SECRET, PASSPHRASE, IS_SANDBOX)
    except Exception:
        tradeAPI = None

try:
    marketAPI = MarketModule.Market(API_KEY, API_SECRET, PASSPHRASE, IS_SANDBOX)
except Exception:
    try:
        marketAPI = MarketModule.Client(API_KEY, API_SECRET, PASSPHRASE, IS_SANDBOX)
    except Exception:
        marketAPI = None

# ============ 封装方法 ============
def get_balance(ccy="USDT"):
    """查询账户余额"""
    result = accountAPI.get_balance(ccy=ccy)
    return result

def get_positions(instId=None):
    """查询持仓"""
    result = accountAPI.get_positions(instId=instId)
    return result

def get_price(instId="BTC-USDT"):
    """获取某币种的最新价格"""
    result = marketAPI.get_ticker(instId)
    if "last" in result:
        return float(result["last"])
    return None

def place_order(instId="BTC-USDT", tdMode="cross", side="buy", ordType="market", sz="0.001"):
    """下单"""
    result = tradeAPI.place_order(
        instId=instId,
        tdMode=tdMode,   # cross=全仓, isolated=逐仓
        side=side,       # buy 或 sell
        ordType=ordType, # market 或 limit
        sz=sz            # 数量
    )
    return result

# ============ WebSocket 回调 ============
def handle_message(msg):
    """处理WebSocket推送"""
    if "arg" in msg and "data" in msg:
        channel = msg["arg"]["channel"]
        if channel == "tickers":
            price = msg["data"][0]["last"]
            print(f"📈 实时价格: {msg['arg']['instId']} = {price}")
        elif channel == "positions":
            pos = msg["data"][0]
            print(f"📊 仓位变化: {pos}")

# 启动WebSocket
def start_ws(instId="BTC-USDT"):
    # The installed okx package may not provide a WebSocket class named PublicWs/PrivateWs.
    # If WebSocket is unavailable, skip WS startup and return (None, None).
    if WebSocket is None:
        print('WebSocket client not found in installed okx package; skipping WS startup.')
        return None, None

    ws = WebSocket.PublicWs(is_sandbox=IS_SANDBOX)
    ws.start()
    ws.subscribe([{"channel": "tickers", "instId": instId}], callback=handle_message)

    private_ws = WebSocket.PrivateWs(API_KEY, API_SECRET, PASSPHRASE, is_sandbox=IS_SANDBOX)
    private_ws.start()
    private_ws.subscribe([{"channel": "positions", "instType": "SWAP"}], callback=handle_message)

    return ws, private_ws


# ============ 示例运行 ============
if __name__ == "__main__":
    # 启动 WebSocket 监听
    ws, pws = start_ws("BTC-USDT")

    # REST 查询示例
    print("💰 账户余额:", get_balance("USDT"))
    print("📊 当前仓位:", get_positions("BTC-USDT-SWAP"))
    print("📈 当前价格:", get_price("BTC-USDT"))

    # 示例：市价买入 0.001 BTC
    # print("🟢 下单:", place_order("BTC-USDT-SWAP", side="buy", tdMode="cross", sz="1"))

    while True:
        time.sleep(5)