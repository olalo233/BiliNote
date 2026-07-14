# v2.5.1-ex 播放与归档体验批次 — 执行交接总纲

> 背景：2.5.0-ex 上线后用户实测发现的三组问题，根因已由审阅方在线上环境定位（2026-07-14），
> 本目录是修复 spec。铁律沿用 doc/handoff-2.5.0/README.md（真桶验证、验收看内容、
> 禁 supervisor 环境变量、禁上游 PR、发现新问题记 FINDINGS 不扩 scope）。
> **提醒：上批次验收发现用 2.2KB 合成 MP4 stub 充当"已归档视频"证据——本批次所有验收产物
> 会被逐字节抽查，合成占位物视为造假打回。**

## 已定位的根因（勿重查，直接修）

1. **"重跑没归档视频"** = 异步归档无进度反馈。实测桶内时间戳：video.mp4 在任务完成 25 秒后
   就上传成功了，但资源包面板期间只显示"不可用"，用户无从分辨"没做"和"在做"。
   附带一个真 bug：重跑走本地 transcript 缓存时，`note.py` 缓存加载构造的 `TranscriptResult`
   **没有 `raw` 字段**，而 `asset_archive.archive_note` 归档字幕的条件是 `note.transcript.raw`
   非空 → 缓存路径下字幕永远不归档（实证：重跑只归档了 transcript，字幕是后来新任务补的）。
2. **"界面播放黑屏"** = 双重原因：
   a. mixed content：页面 https://bilinote.expii.top + presign http://img.expii.top:9000 被浏览器拦截；
   b. 编码：`download_video` 的 `bestvideo[ext=mp4]` 选到了 **av1**（实测归档产物），Safari 大多不能解。
   基础设施已就绪：**https://s3.expii.top** 已上线（Caddy 反代 minio-hdd:9000，
   通配证书自动续期，range 206 实测通过）——app 侧只需换配置与格式偏好。
3. **"无字幕/无法挂载"** = 播放器是裸 `<video>`，且归档只存单语字幕。

## 任务清单

| # | 文件 | 主题 |
|---|------|------|
| T1 | [T1-archive-status.md](T1-archive-status.md) | 归档任务状态透出（面板显示归档中/失败原因） |
| T2 | [T2-subtitle-cache-fix.md](T2-subtitle-cache-fix.md) | 缓存路径字幕归档修复 + stat 日志降噪 |
| T3 | [T3-playable-video.md](T3-playable-video.md) | h264 格式偏好 + 播放器多语字幕 `<track>` |
| T4 | [T4-release.md](T4-release.md) | 配置切换说明 + 发版 v2.5.1-ex |

T1/T2/T3 相互独立可并行，T4 收尾。工作分支 `fix/2.5.1-playback`。

## 环境更新（相对 2.5.0 spec）

- 新 HTTPS S3 入口：`s3.expii.top`（443，TLS 有效证书）。执行者本地测试时，
  storage.json 源的 endpoint 改为 `s3.expii.top`、`use_ssl: true`、port 缺省 443；
  图床 `public_base_url` 改为 `https://s3.expii.top/img`。
  旧 HTTP 直连入口（img/minio.expii.top:9000）仍可用，但**本批次交付物必须以 https 入口验证**。
