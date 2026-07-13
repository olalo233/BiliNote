# v2.4.5 Docker 发布验证记录

## 已完成的本地验证

- 执行器测试修复 commit：`0429de4`。
- Docker 发布 workflow 与运行时透传 commit：`2f9ea5c`。
- `PYTHONPATH=backend /tmp/bilinote-t1-venv/bin/python -m pytest -q backend/tests/test_task_serial_executor.py`：`4 passed`。
- `PYTHONPATH=backend /tmp/bilinote-t1-venv/bin/python -m pytest -q backend/tests`：`54 passed, 3 subtests passed`。
- `CI=1 corepack pnpm@9.15.0 install --frozen-lockfile`：通过。
- `DOCKER_BUILD=1 corepack pnpm@9.15.0 build`：通过，产物引用 `/assets/...`。
- `env -u DOCKER_BUILD corepack pnpm@9.15.0 build`：通过，产物引用 `./assets/...`。
- `corepack pnpm@9.15.0 lint`：`115 errors, 16 warnings`；均为现有前端技术债，本批次未修改前端源文件，不作为 Docker 发布硬门槛。
- 本机无法使用 Docker/Podman；本地构建是在 Node `v26.5.0` 上完成，Node 20 的最终构建由 `Dockerfile.complete` 的 `node:20-alpine` 和 GitHub Actions 验证。

## 已实现的 fork-only 发布验证

- `.github/workflows/docker-build.yml` 固定 `linux/amd64`，tag 构建明确校验 `2.4.5` 与 `latest`，并增加镜像 smoke job。
- smoke job 覆盖首页、`/settings/model` 资源路径和 JavaScript content type、模型/健康路由、deno、锁定的 yt-dlp 版本、Cookie 增删查及重复删除、`YTDLP_AUTO_UPDATE` 默认关闭与失败降级、YouTube/B 站格式探测。
- YouTube/B 站实时格式探测若受 runner 网络限制只产生 warning，需在可访问 Linux/NAS 环境补做同一命令。
- `Dockerfile.complete` 将 `PIP_INDEX_URL` 透传给 supervisor backend，支持验证自动更新失败时 backend 仍启动。

## 发布前阻塞项

- 本机 `gh auth status` 显示 fork token 已失效，无法读取 Actions/GHCR 私有状态或执行远端 tag 操作。
- fork 现有 `v2.4.5` tag 指向 `bc487c6`，且 GitHub Release 已存在并包含扩展与桌面端资产。删除并重建该 tag 可能影响已有消费者；在用户确认保护策略并完成 GitHub 重新认证前，不执行远端 tag 删除、Release 删除或 GHCR 发布。
- 当前验证分支已推送到 `origin/codex/v245-docker-validation`；未向 `upstream` 创建 PR 或推送。
