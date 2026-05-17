# Physical Agent

[Chinese version](README.zh-CN.md)

Physical Agent is a Markdown-native runtime for safe physical-world agents.

The core idea is deliberately small:

```text
Terminal 1: physical-agent watch
Terminal 2: physical-agent run --task "..."
Workspace: Markdown files are the protocol between cognition and execution.
```

The v1 principle is:

```text
Agent can propose actions. Watch decides whether and how they touch the physical world.
```

## Architecture

Physical Agent separates cognition from physical execution with a two-process runtime.

```text
physical-agent watch
  owns hardware or simulator
  owns driver lifecycle
  owns observation loop
  owns safety enforcement
  owns action execution

workspace/*.md
  Markdown protocol and blackboard

physical-agent run
  reads task, capabilities, world, and feedback
  writes structured action intent
```

`physical-agent run` never imports hardware drivers or SDKs. It only sees Markdown protocol documents. `physical-agent watch` is the only runtime that loads drivers and calls `driver.execute(action)`.

## Quick Start

```bash
pip install -e .
physical-agent init
```

Start the physical side in one terminal:

```bash
physical-agent watch
```

Submit a task from another terminal:

```bash
physical-agent run --task "pick the red block and place it on the tray"
```

Inspect the workspace state:

```bash
physical-agent inspect
```

The default project uses the built-in `mock_arm` driver, so no hardware or API key is required.

## Markdown Workspace Protocol

The workspace is dynamic protocol state. Each file uses YAML front matter, Markdown prose, and fenced YAML blocks for machine-readable data.

```text
workspace/
  TASK.md
  CAPABILITIES.md
  WORLD.md
  ACTIONS.md
  FEEDBACK.md
  SAFETY.md
  LOG.md
  artifacts/
```

`TASK.md` records the active task and human constraints.

`CAPABILITIES.md` is written by watch from loaded driver capabilities. The agent treats it as read-only.

`WORLD.md` is written by watch from driver observations. It contains robot state, objects, environment data, and artifact paths.

`ACTIONS.md` is written by the agent. It contains pending, completed, and cancelled action boards. Watch reads pending actions and moves them after execution or safety rejection.

`FEEDBACK.md` is written by watch. It records latest execution feedback and history for the agent to read.

`SAFETY.md` is owned by humans and enforced by watch. The agent can read it but cannot bypass it.

`LOG.md` is an audit log for human review.

Static configuration belongs in `physical-agent.yaml`. Dynamic state belongs in the Markdown workspace.

## Driver Contract

Two files are enough to connect a robot:

```text
my_robot_driver/
  physical_driver.yaml
  driver.py
```

`physical_driver.yaml` declares the adapter: name, version, entrypoint, robot kind, configuration schema, dependencies, and capability contract.

`driver.py` implements the adapter by subclassing `PhysicalDriver`. The driver turns structured `Action` objects into hardware or simulator calls, and turns device state into `Observation` objects.

Important boundaries:

- The driver only talks to `physical-agent watch`.
- The driver does not parse Markdown.
- The driver does not call the agent runtime.
- The agent only sees capabilities, world state, actions, and feedback through Markdown.

Create a new local driver scaffold:

```bash
physical-agent driver new my_arm_driver
```

Use it from `physical-agent.yaml`:

```yaml
robots:
  arm_1:
    driver: ./my_arm_driver
    config: {}
```

## Built-In Drivers

`mock_arm` supports:

- `observe`
- `move_to`
- `pick`
- `place`

It maintains a simulated pose, held object, and object map. The default quickstart includes `red_block` and `tray`.

`mock_rover` supports:

- `observe`
- `move_to`

It demonstrates that the driver protocol is not arm-specific.

## Safety Gate

Watch validates every action before execution:

- robot exists
- capability exists
- params satisfy the capability JSON schema
- capability constraints are satisfied
- workspace safety rules allow execution
- human approval requirements are respected
- action IDs are not duplicated
- dependencies are already completed

If validation fails, watch does not call the driver. It writes clear feedback, logs the rejection, and removes the action from pending.

## Rule-Based Planner

The first planner is intentionally local and deterministic:

- `observe`, `look`, or `scan` produces `observe`
- `move` or `go` produces `move_to`
- `pick` or `grasp` produces `pick`
- `place` or `drop` produces `place`

For example:

```text
pick the red block and place it on the tray
```

produces a `pick` action followed by a dependent `place` action.

## Clean-Room Implementation

Physical Agent is an independent implementation. It uses general public architecture ideas such as embodied-agent layering, watchdog/runtime separation, declarative driver manifests, Markdown workspace protocols, and MCP-style tool facades. It does not include third-party competitor code, copied file contents, copied README wording, copied CLI design, copied example task suites, or copied implementation details.
