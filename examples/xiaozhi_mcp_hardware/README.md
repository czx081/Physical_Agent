# Xiaozhi MCP Hardware Example

This example shows how to connect a Xiaozhi MCP-style device to Physical Agent.

The important boundary is simple:

```text
agent writes intent into Markdown workspace files.
watch loads the driver, enforces safety, and talks to hardware or the MCP bridge.
```

This folder is a complete two-file driver example. It contains:

```text
physical_driver.yaml
driver.py
```

The example driver is `xiaozhi_mcp`. It supports:

- `mock` mode for local end-to-end testing without hardware
- `http` mode for a real MCP endpoint

## Layout

```text
examples/xiaozhi_mcp_hardware/
  physical_driver.yaml
  driver.py
  physical-agent.yaml
  .env.example
  README.md
```

## Quick Start

From the repository root:

```bash
physical-agent init
```

If you want to run this example as a standalone project, copy this folder into your own project and keep the same relative path, or change `driver:` in `physical-agent.yaml` to match where you place the folder.

Then initialize the workspace:

```bash
physical-agent init
```

## Run in Mock Mode First

The example config defaults to:

```yaml
robots:
  xiaozhi_1:
    driver: xiaozhi_mcp
    config:
      mode: mock
```

Start watch:

```bash
physical-agent watch
```

In another terminal, submit a task:

```bash
physical-agent run --task "ask the device to say hello"
```

Or:

```bash
physical-agent run --task "turn the light red"
```

The rule-based planner will turn the request into structured actions, and watch will execute them.

## Connect Real Xiaozhi MCP Hardware

Copy `.env.example` to `.env` and fill in the real endpoint:

```env
XIAOZHI_MCP_ENDPOINT=http://your-mcp-bridge
XIAOZHI_MCP_TOKEN=if-needed
```

If your MCP bridge exposes a non-HTTP transport, keep the Physical Agent side unchanged and add a small bridge that translates the transport into the HTTP JSON-RPC format used by the example driver.

## What the Driver Does

`xiaozhi_mcp` handles:

- `observe` to inspect the device state
- `say` to speak a short sentence
- `set_light` to control RGB light output

Those capabilities are published into `CAPABILITIES.md`, so the agent only sees Markdown and never touches hardware directly.

## What Your Teammate Should Remember

```text
1. Start from physical-agent.yaml.
2. Keep hardware logic in the watch-side driver.
3. Begin with mock mode.
4. Switch .env to the real MCP endpoint only after the mock flow works.
5. The agent only writes workspace files.
```

## Troubleshooting Order

If execution does not happen, check:

1. `physical-agent doctor`
2. `physical-agent inspect`
3. `workspace/CAPABILITIES.md`
4. `workspace/ACTIONS.md`
5. `workspace/FEEDBACK.md`

Typical causes:

- `XIAOZHI_MCP_ENDPOINT` is missing
- the MCP bridge is not running
- the token is wrong
- the bridge is not HTTP JSON-RPC, so a thin adapter is needed

## Migrating This Example to Real Hardware

You can copy `examples/xiaozhi_mcp_hardware/` as a starting point and then:

1. Replace `xiaozhi_mcp` with your real driver name.
2. Update `tools` to match the MCP tool names your device exposes.
3. Replace `observe`, `say`, and `set_light` with your actual capability set.
4. Swap `_post_jsonrpc()` for your real transport if needed.

In practice, teammates only need two files:

```text
physical_driver.yaml
driver.py
```

That is the Physical Agent Two-file Driver Protocol.
