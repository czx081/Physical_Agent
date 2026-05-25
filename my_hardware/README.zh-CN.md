# my_hardware

这是一个本地 Physical Agent driver 模板。

watch 进程会加载这个目录，校验 `physical_driver.yaml`，
导入 `driver.py`，并把结构化的 `Action` 对象传给 driver。
driver 不解析 Markdown，也不会直接调用 agent runtime。
