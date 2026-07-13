# v2.4.5e Docker 发布验证记录

## 已完成的本地验证

- 执行器测试修复 commit：`0429de4`。
- Docker 发布 workflow 与运行时透传 commit：`2f9ea5c`。
- fork-only 版本号兼容 commit：`91a7c68`。
- `PYTHONPATH=backend /tmp/bilinote-t1-venv/bin/python -m pytest -q backend/tests/test_task_serial_executor.py`：`4 passed`。
- `PYTHONPATH=backend /tmp/bilinote-t1-venv/bin/python -m pytest -q backend/tests`：`54 passed, 3 subtests passed`。
- `CI=1 corepack pnpm@9.15.0 install --frozen-lockfile`：通过。
- `DOCKER_BUILD=1 corepack pnpm@9.15.0 build`：通过，产物引用 `/assets/...`。
- `env -u DOCKER_BUILD corepack pnpm@9.15.0 build`：通过，产物引用 `./assets/...`。
- `corepack pnpm@9.15.0 lint`：`115 errors, 16 warnings`；均为现有前端技术债，本批次未修改前端源文件，不作为 Docker 发布硬门槛。
- 本机无法使用 Docker/Podman；本地构建是在 Node `v26.5.0` 上完成，Node 20 的最终构建由 `Dockerfile.complete` 的 `node:20-alpine` 和 GitHub Actions 验证。

## 已实现的 fork-only 发布验证

- `.github/workflows/docker-build.yml` 固定 `linux/amd64`，并对任意 `v*` tag 生成去掉前缀 `v` 的原始镜像 tag；本次 `v2.4.5e` 对应 `2.4.5e` 与 `latest`，同时增加镜像 smoke job。
- `v2.4.5e` 不是严格 SemVer，因此桌面端和浏览器扩展 workflow 会跳过该 fork-only tag；本次发布范围保持为 Docker。
- smoke job 覆盖首页、`/settings/model` 资源路径和 JavaScript content type、模型/健康路由、deno、锁定的 yt-dlp 版本、Cookie 增删查及重复删除、`YTDLP_AUTO_UPDATE` 默认关闭与失败降级、YouTube/B 站格式探测。
- YouTube/B 站实时格式探测若受 runner 网络限制只产生 warning，需在可访问 Linux/NAS 环境补做同一命令。
- `Dockerfile.complete` 将 `PIP_INDEX_URL` 透传给 supervisor backend，支持验证自动更新失败时 backend 仍启动。

## 远端发布状态

- fork 现有 `v2.4.5` tag 仍指向 `bc487c6`，且对应 GitHub Release 包含扩展与桌面端资产；本次不删除、不改写旧 tag/Release。
- 修复后的 fork `master` 提交为 `91a7c68`；下一步在该提交上创建 annotated `v2.4.5e` 并只推送到 `origin`。
- 未向 `upstream` 创建 PR 或推送。

## v2.5.0-ex 运行环境发现

- 2026-07-13：提供的 MinIO 受限 key 对 `img/_probe/*` 返回 `AccessDenied`，但对配置的 `img/bilinote/*` 前缀可 PUT/DELETE；T1 连接探针因此落在图床 `path_prefix` 下，并完成 PUT → GET → 匿名 GET → DELETE。未操作授权范围外的桶。
- 2026-07-13：T5 设置页浏览器 smoke 在既有 `BackendInitDialog.tsx` 的 Radix `DialogContent` 发现 `Missing Description or aria-describedby` warning（两条），不影响页面渲染；该文件不属于本批次，未扩 scope 修复。
