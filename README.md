# okx helpers

示例脚本 `okx_run.py` 演示如何使用已安装的 `okx` Python 包进行 REST 查询与（可选）WebSocket 监听。

准备：
- 复制 `.env.example` 为 `.env` 并填写 API_KEY/API_SECRET/PASSPHRASE
- 安装依赖：

```
pip install okx requests websocket-client
```

运行：

```
python okx_run.py
```

注意：当前 `okx` 包的 WebSocket 客户端在不同版本中命名不同，脚本会在找不到 WebSocket 实现时安全跳过。
