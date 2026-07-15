# v2.5.2-ex 批次 — 执行交接总纲

> 设计已在 2026-07-14 会话与用户对齐定稿。执行者按任务实施，不重开方案讨论；
> 每条验收标准必须真实执行并贴证据。铁律沿用 handoff-2.5.0/2.5.1（真桶验证、
> 验收看内容不只看状态码、禁上游 PR、发现新问题记 FINDINGS 不擅自扩 scope）。

## ⚠️ 基线分支（最重要，先看）

master 仍停在 2.5.0-ex；2.5.1 的全部代码（对象存储播放/字幕/资源包 + h264 回退）
**只在 tag `v2.5.1-ex.2` 上，未并入 master**。

- 本批次工作分支 `feat/2.5.2` **已从 `v2.5.1-ex.2` 切出**（本 spec 就在其上），继续在此分支干。
- **绝对不要从 master 起分支或 rebase 到 master**，否则丢失 2.5.1 全部功能。
- 发版时（T5）合并去向问题见 T5，届时一并把 2.5.1+2.5.2 一起并入 master。

## 本批次四件事

| # | 文件 | 主题 | 风险 |
|---|------|------|------|
| T1 | [T1-image-optimize.md](T1-image-optimize.md) | 镜像优化：缓存命中确定化 + 瘦身 + 本地 whisper 懒加载落盘 | 高（结构性改动） |
| T2 | [T2-prompt-library.md](T2-prompt-library.md) | 提示词小抄：备注区模板库（搜索/滚动/载入/存/删） | 低 |
| T3 | [T3-delete-source-button.md](T3-delete-source-button.md) | 存储设置补「删除供应商」按钮（接已有 API） | 极低 |
| T4 | [T4-note-deeplink.md](T4-note-deeplink.md) | 笔记深链 `/note/:taskId` + 复制链接 + Clipper 属性 | 中 |
| T5 | [T5-release.md](T5-release.md) | 发版 v2.5.2-ex（含 2.5.1 并入 master） | — |

T1–T4 相互独立可并行；T5 收尾。

## 环境

- 真实 MinIO：`s3.expii.top`（HTTPS，443，有效证书）；旧 http 直连 `img.expii.top:9000` 仍在。
  受限凭据 access_key=`bilinote`，secret 找用户要（勿翻配置/勿自造）。仅 `img`（限 `bilinote/*` 前缀）
  与 `bilinote-assets` 两桶可操作。
- 本机 docker=podman（applehv machine）。**用户禁止在 MacBook 拉大镜像**（热点环境）——
  镜像相关的真实验证在 CI 或极空间 NAS 上做；本地只做能离线跑的部分（构建分析用
  `docker history`、层 digest 比对可在 CI 产物上做）。
- 本机直连 YouTube 不稳定；涉及真实下载的验证若本地失败，在 NAS 或 CI 补做并注明。

## 已锁定的设计决策（勿改）

- **本地 whisper：懒加载落盘**（用户很少用本地转写）。镜像默认**不含** faster-whisper/
  ctranslate2/av；用户在设置里选「本地 whisper」且库不存在时，运行时 pip 装到挂载卷的
  固定路径并加入 import 路径。**不做 lite/full 双镜像**。
- **deno 保持内置**（核心依赖，YouTube nsig 解密；不赌运行时下载失败打断主功能）。
- **提示词库：载入=替换备注框**（整段人格，非片段插入）；扁平命名列表；模糊搜（名+内容）+
  固定高度滚动（不翻页）；预置官方模板作起点；存 `config/prompts.json`（挂载卷）。
- **笔记深链用 task_id**（精确到剪藏的那个版本——不同版本笔记内容本就不同）。
