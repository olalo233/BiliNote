# T6 — 发版 v2.5.0-ex

> 前置：T1–T5 全部验收通过并合入 `feat/2.5.0-storage`。

## 步骤

1. `CHANGELOG.md` 新增 `## [2.5.0-ex] - 日期`（Added：图床/资产归档/资源包/存储用量；
   fork 发版沿用 `-ex` 后缀约定）。README 版本号与新功能摘要段同步，并在 Docker 部署段
   补充 storage.json 说明与 MinIO 配置示例（用户实例参数作为示例值，**不含真实 key**）。
2. 合并 `feat/2.5.0-storage` → `master`（merge commit `chore(release): v2.5.0-ex`），push。
3. 打 annotated tag `v2.5.0-ex` push，触发 docker-build workflow（现有流程：build → smoke → 通过才 push 镜像）。
4. smoke 扩展（改 `.github/workflows/docker-build.yml` 冒烟脚本）：
   - `GET /api/storage/config` 返回 200 且结构含 sources/image_bed/assets 键（未配置时为空值）；
   - 未配置存储时生成链路回归断言保持原样（默认容器现有断言不动）。
   ⚠️ 不在 CI 里打真 MinIO（runner 摸不到内网）——真桶 e2e 属于 T2/T3/T4 的本地验收，
   CI 只做"未配置=现状"回归。
5. CI 绿后交付清单：镜像 `ghcr.io/olalo233/bilinote:2.5.0-ex`（+latest）、
   全部任务的验收证据汇总、FINDINGS.md（如有）。

## 验收标准

1. CI run 全绿（贴 run 链接与 job 结果）。
2. 本地拉取发布镜像，配置 storage.json 后完整跑一次"生成带截图笔记 + 归档 + 资源包查看"
   （用户实例 MinIO），全链路正常（贴关键日志与截图）。
3. 部署交接说明：NAS 上用户需要做的事——MinIO 新建 `bilinote-assets` 桶（private）
   与受限 access key、极空间 UI 换镜像 tag。写成一段可直接照做的清单。
