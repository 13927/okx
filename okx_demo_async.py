from okx_account import OKXAccount
import asyncio

# 请替换为你的 API Key
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
PASSPHRASE = "your_passphrase"

async def main():
    # 初始化账户 (设置 simulated=True 使用模拟盘)
    okx = OKXAccount(API_KEY, API_SECRET, PASSPHRASE, simulated=True)

    # 1. 查询余额
    print("💰 账户余额:", okx.get_balance("USDT"))

    # 2. 获取当前价格
    price_info = okx.get_price("BTC-USDT")
    print("📈 价格:", price_info)

    # 3. 下单 (示例：开空 1 张 BTC-USDT-SWAP)
    order = okx.place_order(
        instId="BTC-USDT-SWAP",
        tdMode="cross",
        side="sell",
        posSide="short",
        ordType="market",
        sz="1"
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