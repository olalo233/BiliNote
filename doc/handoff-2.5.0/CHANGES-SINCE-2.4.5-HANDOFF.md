# 上批次（2.4.5）交接后的修正记录 — 开工前必读

你（执行者）上次交付后，审阅方又做了以下修正并已合入 master。
**这些不是你的遗留任务，不要重做**；但其中的教训已写入本批次铁律，违反会被打回。

| commit | 内容 | 对你的含义 |
|---|---|---|
| `4a77d2e` | CI 重构：单 job build(load)→smoke→通过才 push；smoke 的自更新场景去掉了 `pip uninstall`（backend 顶层 import yt_dlp，卸载必崩，你当时测的是"包不存在"而非"升级失败降级"）；诊断补收容器内 backend.log | 改 workflow 时保持这个结构；排障先拿 backend.log 再动手 |
| `c91d659` | 修复 YTDLP_AUTO_UPDATE 开关从未生效的 bug：Dockerfile 未加引号的 `COPY <<EOF` heredoc 在**构建期**展开 `$VAR`，把开关固化成 0。改用 supervisord 的 `%(ENV_x)s` 运行时展开 | **本批次禁止新增 supervisor 环境变量**，配置一律走 config/*.json 文件（见 README 铁律） |
| `39ad3f5` | 修复 YouTube 字幕解析产出对象 repr 垃圾：youtube-transcript-api ≥1.0 返回对象而非 dict，旧代码 `str(snippet)` 兜底把 repr 当字幕文本 | 你当时验收只断言"拿到 627 段"没抽查内容——本批次验收必须看内容 |
| tag 约定 | 废弃 `v2.4.5e` 式裸字母后缀，fork tag 用 `-ex` 连字符后缀（`v2.4.5-ex`、`v2.4.5-ex.2`，本批次 `v2.5.0-ex`）；桌面端/插件 workflow 触发已收窄为严格三段版本号 | 打 tag 按新约定 |
| 现役版本 | 线上镜像 `2.4.5-ex.2`（含以上全部修复），NAS 已部署并 e2e 验证 | 你的工作基线是当前 master，不是你记忆中交付的那个 commit |
