---
schema: physical-agent/plan/v1
owner: agent
revision: 6
---

# Plan

## Current

```yaml
status: proposed_actions
intent: act
summary: "\u597D\u7684\uFF0C\u60A8\u8981\u5C07\u8155\u90E8\u95DC\u7BC0\u518D\u8F49\
  +20\u5EA6\uFF08\u76F8\u5C0D\u904B\u52D5\uFF09\u3002\u7576\u524D\u8155\u90E8\u89D2\
  \u5EA6\u70BA-20\u5EA6\uFF0C\u8F49+20\u5EA6\u5F8C\u76EE\u6A19\u89D2\u5EA6\u70BA0\u5EA6\
  \u3002\u6211\u5C07\u5EFA\u8B70\u4E00\u500B\u52D5\u4F5C\uFF0C\u7531\u76E3\u63A7\u7CFB\
  \u7D71\u9A57\u8B49\u4E26\u57F7\u884C\u3002"
steps: []
actions:
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
needs_watch: true
```
