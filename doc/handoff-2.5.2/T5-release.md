# T5 — 发版 v2.5.2-ex（含 2.5.1 一并并入 master）

> 前置：T1–T4 全部验收通过并合入 `feat/2.5.2`。

## 处理分支欠账

master 目前停在 2.5.0-ex，2.5.1 与 2.5.2 都未并入。本次一次性收敛：

1. 将 `feat/2.5.2`（其历史已包含 2.5.1-ex.2 的全部提交）合并到 `master`
   （merge commit `chore(release): v2.5.2-ex`）。这样 master 一步到位包含 2.5.1+2.5.2。
2. push master。
3. 打 annotated tag `v2.5.2-ex`，push tag → 触发 docker-build workflow。

## CHANGELOG / README

- CHANGELOG 新增 `## [2.5.2-ex]`：
  - Changed：镜像瘦身（2.0GB→<1.2GB，删 hf-xet、ffmpeg 静态化、本地 whisper 懒加载落盘）、
    构建缓存确定化（增量更新不再重拉依赖层）。
  - Added：提示词库（备注模板保存/复用/搜索）、笔记深链 `/note/:taskId` + 复制链接、
    存储供应商删除按钮。
  - 补记本地 whisper 由内置改为按需安装到挂载卷（默认镜像不含）。
- README：Docker 部署段补充「本地 whisper 首次使用会联网安装到 data 卷」的说明；
  存储配置示例已是 s3.expii.top（2.5.1 已改，确认无遗漏）。

## CI smoke 扩展（docker-build.yml）

- 保留现有「未配置存储=现状」回归。
- 新增：默认镜像断言 `pip show faster-whisper` 不存在（返回非 0）——防止 whisper 库
  意外被重新打包进镜像；断言最终镜像大小 < 1.2GB（`docker image inspect -f '{{.Size}}'`，
  设阈值 gate）。
- CI 摸不到内网 MinIO / 不稳定连 YouTube 的部分仍只在 NAS 补测（沿用既有约定）。

## 验收标准

1. CI run 全绿（贴链接）；`docker image inspect` 尺寸 < 1.2GB（贴数字）。
2. master 合并后包含 2.5.1+2.5.2 全部提交（`git log --oneline` 佐证）。
3. 交付清单：镜像 tag `ghcr.io/olalo233/bilinote:2.5.2-ex`（+latest）、全部任务验收证据、FINDINGS。
4. 部署交接清单（写给用户）：极空间换镜像 `2.5.2-ex`；本地 whisper 首用需容器可联网装依赖；
   其余沿用现有卷/网络/环境变量。
