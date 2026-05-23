---
schema: physical-agent/actions/v1
owner: agent
revision: 13
---

# Action Board

## Pending

```yaml
[]
```

## Completed

```yaml
- id: act_004
  robot: momo_1
  capability: move_joint
  params:
    joint_name: wrist_roll
    target_deg: 10.0
  reason: The task asks for a joint-level movement.
  depends_on: []
- id: act_005
  robot: momo_1
  capability: move_joint
  params:
    joint_name: wrist_roll
    delta_deg: -20
    speed_percent: 50
  reason: "\u7528\u6237\u8981\u6C42\u65CB\u8F6C-20\u5EA6\uFF0C\u5F53\u524D\u8155\u90E8\
    \u89D2\u5EA6\u4E3A10\u5EA6\uFF0C\u4F7F\u7528\u76F8\u5BF9\u8FD0\u52A8\uFF08delta_deg\uFF09\
    \u5B9E\u73B0\u3002"
  depends_on: []
- id: act_006
  robot: momo_1
  capability: move_joint
  params:
    joint_name: wrist_roll
    delta_deg: 20
    speed_percent: 50
  reason: "\u7528\u6236\u8981\u6C42\u8F4920\u5EA6\uFF0C\u7576\u524D\u8155\u90E8\u89D2\
    \u5EA6\u70BA-20\u5EA6\uFF0C\u4F7F\u7528\u76F8\u5C0D\u904B\u52D5\uFF08delta_deg=20\uFF09\
    \u4F7F\u5176\u56DE\u52300\u5EA6\u3002"
  depends_on: []
```

## Cancelled

```yaml
[]
```
