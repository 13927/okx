import logging
import json
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
    okx = OKXAccount(API_KEY, API_SECRET, PASSPHRASE, simulated=False)

    def pjson(label, obj):
        try:
            print(f"{label}:\n{json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, default=str)}")
        except Exception as e:
            print(f"{label} (format error: {e}): {obj}")

    # 1. 查询余额
    pjson("💰 账户余额", okx.get_balance("USDT"))

    # 2. 获取当前价格（永续合约 SOL-USDT-SWAP）
    price_info = okx.get_price("SOL-USDT-SWAP")
    pjson("📈 价格SOL-USDT-SWAP", price_info)

    # 2.1 查看账户配置示例
    cfg = okx.get_account_config()
    pjson("🧾 账户配置", cfg)

    # 2.2 获取交易手续费费率示例（仅 SWAP：SOL-USDT）
    try:
        fee_swap = okx.get_trade_fee(instType="SWAP", instFamily="SOL-USDT")
        pjson("💸 手续费[SWAP SOL-USDT]", fee_swap)
    except Exception as e:
        print("获取 SOL-USDT-SWAP 手续费失败:", e)

    # 3. 下单 (示例：SOL-USDT-SWAP 开空，量尽可能小: 1张)
    try:
        pos_mode = None
        try:
            if isinstance(cfg, dict) and cfg.get("data"):
                pos_mode = cfg["data"][0].get("posMode")
        except Exception:
            pass

        order_args = {
            "instId": "SOL-USDT-SWAP",
            "tdMode": "cross",
            "side": "sell",
            "ordType": "market",
            "sz": "0.001",
        }
        if pos_mode == "long_short_mode":
            order_args["posSide"] = "short"

        order = okx.place_order(**order_args)
        pjson("🟢 下空单[SOL-USDT-SWAP sz=0.001]", order)
    except Exception as e:
        print("下空单失败:", e)

    # # 提取订单号
    # ordId = order.get("data", [{}])[0].get("ordId")

    # # 4. 查询订单
    # if ordId:
    #     query = okx.query_order("SOL-USDT-SWAP", ordId=ordId)
    #     print("🔍 查询订单:", query)

    #     # 5. 撤单
    #     cancel = okx.cancel_order("SOL-USDT-SWAP", ordId=ordId)
    #     print("❌ 撤单:", cancel)

    # 6. 启动 WebSocket 监听行情+仓位（异步）
    # await okx.start_ws("SOL-USDT")

if __name__ == "__main__":
    asyncio.run(main())
