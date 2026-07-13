# v2.4.5 执行发现

## `SerialTaskExecutor` 并发测试失败（超出 T1–T7 范围）

- 验证命令：`PYTHONPATH=backend /tmp/bilinote-t1-venv/bin/python -m pytest -q backend/tests`
- 结果：`50 passed, 1 failed`
- 失败项：`backend/tests/test_task_serial_executor.py::TestTaskSerialExecutor::test_executor_runs_tasks_one_by_one`
- 现象：两个并发调用 `SerialTaskExecutor.run()` 时，测试观测到 `peak_active == 2`，预期为 `1`。
- 处理：未在本批次擅自修改任务串行器；该问题与 T1–T7 交接任务无直接关系，留待后续专项处理。

## 容器验收环境限制

- 本机未安装 Docker，Podman machine 也未启动，无法执行 `Dockerfile.complete` 的镜像构建、deno 容器检查和 supervisor 启动矩阵。
- 已完成可执行的替代验证：后端依赖安装与 `yt-dlp==2026.7.4` 检查、frontend 两种 base 构建、shell 命令语法检查，以及后端单测。
