# v2.5.0-ex 对象存储批次 — 执行交接总纲

> 设计讨论已完成（2026-07-13 会话），本目录是定稿 spec。执行者按任务文档实施，
> 不需要重新做方案取舍；每个任务的验收标准必须逐条真实执行并附证据。

## 目标

1. **图床**：笔记截图上传到 S3 兼容对象存储，笔记内写入公网可访问的绝对 URL——
   解决 Web Clipper 剪藏后 `/static/screenshots/...` 相对路径图片全裂的问题。
2. **资产归档**：字幕/转写（小而不可再生）自动归档到私有资产桶；音频跟随现有下载行为归档；
   原始视频按次勾选归档。让"收藏过的视频"对源站下架、出口 IP 被封等故障免疫。
3. **资源包**：按 video_id 维度管理归档资产（查看/下载/删除/播放），多版本笔记共享。
4. **存储用量**：功能页内展示桶用量，防止资产桶失控。

## 核心设计决策（已定稿，勿重开讨论）

- **两个功能、一池命名源**：设置页一级 tab「图床」「资产」；存储源（source）是命名的
  连接配置，定义在**桶粒度**：`{name, type: "s3", endpoint, access_key, secret_key,
  bucket, path_style, use_ssl}`。功能层绑定一个 source 名 + 功能特有设置。
  同一台 MinIO 的两个桶 = 两条源记录，模型保持扁平（PicGo 多图床心智）。
- **配置存储**：`config/storage.json`，复用 `CookieConfigManager`/`ProxyConfigManager`
  的实时读写文件模式（挂载卷持久化、改完即生效、无需重启）。**不要**引入新的
  supervisor 环境变量（heredoc 构建期展开有坑，见 docker-build.yml 内注释的历史教训）。
- **资产桶布局**：`{platform}/{video_id}/video.mp4|audio.m4a|subtitle.{lang}.json|transcript.json`
  ——按视频去重，多任务/多版本笔记共享。
- **图床桶布局**：`{path_prefix}/{YYYY-MM}/{task_id}/{filename}.jpg`。
- **访问策略**：图床桶 public-read（笔记要匿名可读）；资产桶 private，
  播放/下载走 presigned URL（有效期 1h 级）。
- **降级语义**：未配置或上传失败 → 保持现有本地行为 + log warning，**任务绝不因存储失败而 FAILED**。
- **归档异步**：资产归档在笔记生成主链路之外做（线程/后台任务），不增加出笔记延迟。
- **SDK**：`minio` python 包（轻量、path-style 友好）。前端 UI 照抄现有
  LLM 供应商列表（`pages/SettingPage` 下 provider 相关组件）的壳。

## 铁律（同 handoff-2.4.5，重申要点）

1. 禁止向上游 JefferyHcool/BiliNote 发 PR 或 push；只在 origin（olalo233/BiliNote）。
2. 工作分支 `feat/2.5.0-storage`，每完成一个任务 commit + push；commitlint `type(scope): subject`。
3. 验收标准逐条真跑、贴证据。**验收要看内容，不只看状态码**——2.4.5 的教训：
   字幕"成功拿到 627 段"但内容全是对象 repr 垃圾，没人抽查内容就发版了。
4. 本地有真实 MinIO 可用（img.expii.top:9000，见 T1 环境说明），e2e 必须打真桶验证，
   不允许只 mock。发现新问题记 `FINDINGS.md`，不擅自扩 scope。
5. 发版走 T6：CHANGELOG、tag `v2.5.0-ex`，CI（build→smoke→push）绿后交付。
   镜像 push 由 CI 完成；如需人工推送凭据，停下来找用户。

## 任务清单（依赖顺序）

| # | 文件 | 主题 |
|---|------|------|
| T1 | [T1-storage-framework.md](T1-storage-framework.md) | 存储源框架：配置管理、S3 客户端、源 CRUD/测试连接 API |
| T2 | [T2-image-bed.md](T2-image-bed.md) | 图床：截图上传 + 笔记 URL 替换 + 降级 |
| T3 | [T3-asset-archive.md](T3-asset-archive.md) | 资产归档：字幕/转写/音频自动归档、原视频勾选归档 |
| T4 | [T4-resource-pack.md](T4-resource-pack.md) | 资源包：API + 前端面板（列表/下载/删除/播放） |
| T5 | [T5-settings-ui-usage.md](T5-settings-ui-usage.md) | 设置页：图床/资产两个 tab、源管理 UI、用量展示 |
| T6 | [T6-release.md](T6-release.md) | 发版 v2.5.0-ex |

T1 是地基必须最先；T2/T3 依赖 T1 可并行；T4 依赖 T3；T5 依赖 T1（用量部分依赖 T2/T3）；T6 收尾。

## UI 设计稿要点（会话中已与用户对齐）

- 设置页新增一级 tab「图床」「资产」（与模型/下载器/转写器并列）。
- 每个功能页：源下拉选择 + 「新建源」表单 + 功能特有设置 + 「测试连接」按钮
  （测试 = PUT 1px 探针对象再 GET+DELETE，图床源额外验证 public_base_url 可匿名 GET）+
  保存；下方用量卡片（对象数/总大小/最近上传，后端聚合缓存 1h，可手动刷新）。
- 生成表单「笔记格式」下方新增「归档」组（仅配置资产功能后显示）：
  「字幕与转写自动归档」（勾选态展示，随资产功能启用，disabled）、「归档原始视频」（默认关，按次勾选）。
- 笔记详情工具栏新增「资源包」入口，展开面板按行列出：原始视频（播放/下载/删除）、
  音频（下载/删除）、字幕/转写（下载）、笔记截图（查看，注明在图床桶）。
  未归档的本地资源显示「上传到对象存储」。删除仅删对象存储副本，不动笔记文本。

## 用户实例参数（写进默认占位/文档示例，不硬编码进代码）

- MinIO：`img.expii.top:9000`，path-style，无 SSL。
- 图床源：bucket `img`（已存在，public-read），public_base_url `http://img.expii.top:9000/img`，
  path_prefix `bilinote`。
- 资产源：bucket `bilinote-assets`（**需在 MinIO 上新建，private**）。
- 权限模型（已配好并实测）：用户 `bilinote` 挂 `bilinote-rw` 策略——
  `bilinote-assets` 整桶读写；`img` 桶仅 `bilinote/*` 前缀读写删列（IAM prefix Condition），
  桶根与其他前缀均拒绝。代码中所有 img 桶操作必须落在 path_prefix 之下。
- access key：用户会在 MinIO Console 给 BiliNote 建受限 key（两桶读写），执行者测试期间
  可先用用户提供的测试 key（找用户要，不要自己造/翻配置文件）。
