# 小智 MCP 硬件接入示例

这个示例演示如何把一个“小智 MCP”设备接入到 Physical Agent。

最重要的边界很简单：

```text
agent 只把意图写进 Markdown workspace。
watch 负责加载 driver、执行安全检查，再去调用硬件或 MCP 网关。
```

这个目录本身就是一个完整的 two-file driver 示例，它包含：

```text
physical_driver.yaml
driver.py
```

示例 driver 名称是 `xiaozhi_mcp`，支持两种模式：

- `mock`：本地联调，不需要真实硬件
- `http`：连接真实的 MCP 接入点

## 目录结构

```text
examples/xiaozhi_mcp_hardware/
  physical_driver.yaml
  driver.py
  physical-agent.yaml
  .env.example
  README.zh-CN.md
```

## 快速开始

先在仓库根目录安装并初始化项目：

```bash
physical-agent init
```

如果你想单独跑这个示例，直接进入这个目录，把 `physical-agent.yaml` 当作该目录下的配置使用即可。

## 先用 mock 跑通

示例配置默认使用：

```yaml
robots:
  xiaozhi_1:
    driver: .
    config:
      mode: mock
```

在示例目录里启动 watch：

```bash
physical-agent watch --config examples/xiaozhi_mcp_hardware/physical-agent.yaml
```

另开一个终端提交任务：

```bash
physical-agent run --config examples/xiaozhi_mcp_hardware/physical-agent.yaml --task "让设备说 hello"
```

或者：

```bash
physical-agent run --config examples/xiaozhi_mcp_hardware/physical-agent.yaml --task "把灯调成 red"
```

rule-based planner 会把任务翻译成结构化动作，watch 再去执行。

## 接入真实的小智 MCP

先把 `.env.example` 复制成 `.env`，再填写真实地址：

```env
XIAOZHI_MCP_ENDPOINT=http://你的MCP网关地址
XIAOZHI_MCP_TOKEN=如果需要鉴权就填
```

如果你的 MCP 网关不是 HTTP JSON-RPC，而是 WebSocket、串口或别的协议，建议先加一个很薄的桥接层，把外部协议转换成这个示例 driver 里使用的 JSON-RPC 调用格式。

## 这个 driver 做了什么

`xiaozhi_mcp` 提供三个能力：

- `observe`：读取设备状态
- `say`：让设备播报一句话
- `set_light`：控制 RGB 灯光

这些能力会写进 `CAPABILITIES.md`。agent 只能看到这些 Markdown 文档，不会直接碰硬件。

## 同事最应该记住的几句话

```text
1. 先跑 mock。
2. driver 放在 watch 侧。
3. 先改 physical-agent.yaml，再改 .env。
4. 真正的硬件调用留在 driver.py。
5. agent 只写 workspace，不直接调用硬件 SDK。
```

## 排查顺序

如果任务没有执行，先检查：

1. `physical-agent doctor`
2. `physical-agent inspect`
3. `workspace/CAPABILITIES.md`
4. `workspace/ACTIONS.md`
5. `workspace/FEEDBACK.md`

常见原因：

- `XIAOZHI_MCP_ENDPOINT` 没配置
- MCP 网关没启动
- token 不正确
- 你的网关不是 HTTP JSON-RPC，需要一个桥接层

## 从这个示例迁移到真实硬件

你可以直接复制 `examples/xiaozhi_mcp_hardware/` 作为新项目起点，然后：

1. 保持 `physical_driver.yaml` 和 `driver.py` 这两个核心文件。
2. 修改 `tools`，让它匹配你的设备真实能力。
3. 修改 `observe`、`say`、`set_light` 为你的动作集合。
4. 如果需要，把 `_post_jsonrpc()` 换成你真实的通信层。

这就是 Physical Agent 的 Two-file Driver Protocol。
