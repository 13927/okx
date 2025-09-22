import logging
from okx_account import OKXAccount
import asyncio
import os
from dotenv import load_dotenv

# 请替换为你的 API Key
# 从项目根目录的 .env 文件加载环境变量
load_dotenv(dotenv_path=".env")

# 启用 DEBUG 日志到终端（可在生产环境移除或改为文件输出）
# level 可选项（从严重到详细）：
#   CRITICAL = 50  严重错误，程序可能无法继续
#   ERROR    = 40  错误事件，会导致某些功能失败
#   WARNING  = 30  警告信息，需要注意但不是错误
#   INFO     = 20  常规运行信息（生产环境常用）
#   DEBUG    = 10  调试信息（开发时最详细）
#   NOTSET   = 0   未设置等级，继承父 logger 的等级
# 示例：开发时用 logging.DEBUG；上线时常用 logging.INFO 或 logging.WARNING
# logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

API_KEY = os.getenv("OKX_API_KEY")
API_SECRET = os.getenv("OKX_API_SECRET")
PASSPHRASE = os.getenv("OKX_PASSPHRASE")

print("Using API_KEY:", API_KEY)
print("Using API_SECRET:", "****" + API_SECRET[-4:] if API_SECRET else None)
print("Using PASSPHRASE:", "****" + PASSPHRASE[-4:] if PASSPHRASE else None)

if not all([API_KEY, API_SECRET, PASSPHRASE]):
    raise RuntimeError("Missing OKX credentials in .env. Please set OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE")

async def main():
    # 初始化账户 (设置 simulated=True 使用模拟盘)
    okx = OKXAccount(API_KEY, API_SECRET, PASSPHRASE, simulated=True)

    # 1. 查询余额
    print("💰 账户余额:", okx.get_balance("USDT"))

    # 2. 获取当前价格
    price_info = okx.get_price("BTC-USDT")
    print("📈 价格:", price_info)

    # 3. 下单 (示例：开空 1 张 BTC-USDT-SWAP)
    # 3. 下单示例：现货市场下单（示例为市价买入 0.001 BTC）
    order = okx.place_order(
        instId="BTC-USDT",
        side="buy",
        ordType="market",
        sz="0.001"
    )
    print("🟢 下单:", order)

    # 提取订单号
    ordId = order.get("data", [{}])[0].get("ordId")

    # 4. 查询订单
    if ordId:
        query = okx.query_order("BTC-USDT-SWAP", ordId=ordId)
        print("🔍 查询订单:", query)

        # 5. 撤单
        cancel = okx.cancel_order("BTC-USDT-SWAP", ordId=ordId)
        print("❌ 撤单:", cancel)

    # 6. 启动 WebSocket 监听行情+仓位（异步）
    await okx.start_ws("BTC-USDT")

if __name__ == "__main__":
    asyncio.run(main())