# v2.5.1-ex.2 交付报告

## 已实现

- T1：归档线程按 video/audio/subtitle/transcript 透出 pending、running、done、failed、skipped 状态；资源包面板自动轮询归档中状态，并支持失败重试。
- T2：缓存加载、预取字幕缓存和资产还原均保留 `raw`；对象不存在的 stat 检查只记 debug。
- T3：YouTube 和 Bilibili 归档取源站最佳编码，不强制 H.264；HTTPS S3 入口解决 mixed content；YouTube 归档人工字幕轨与选中轨；资源包返回语言列表并提供同源 WebVTT 与原生 `<track>`。
- T4：README、CHANGELOG、部署说明和 AV1 存量说明已更新。

## 本地验证记录

以下命令在 2026-07-14、包含 `de88408` 的工作树实际执行：

```text
cd backend && PYTHONPATH=. pytest -q
86 passed, 3 subtests passed in 13.56s

cd backend && PYTHONPATH=. python -m compileall -q app tests
passed

cd BillNote_frontend && pnpm exec tsc --noEmit
passed

cd BillNote_frontend && pnpm exec eslint src/services/resourcePack.ts src/pages/HomePage/components/ResourcePackDialog.tsx
passed

cd BillNote_frontend && pnpm build
passed
```

完整 frontend lint 仍有仓库基线问题：115 errors、16 warnings；变更文件 targeted lint 通过。

新增用例覆盖归档状态生命周期、缓存 `raw` 往返、旧缓存兼容、NoSuchKey 日志、源站最佳编码契约、多语字幕选择、VTT 时间戳/转义、语言路径校验和资源包响应。

## 部署环境验证

2026-07-14，验收方确认 T4 部署验证完成，覆盖 HTTPS S3 配置、归档状态可见、视频播放、206 range 和多语字幕切换。播放策略经实测确认：mixed content 是黑屏根因，现代浏览器可播放 AV1-in-MP4，因此最终版本恢复各平台源站最佳编码，不强制 H.264。

本报告不使用合成 MP4 或占位媒体作为验收证据；已归档 AV1 存量不迁移。

## 部署清单

1. 使用镜像 `ghcr.io/olalo233/bilinote:2.5.1-ex.2`。
2. 设置页两个存储源使用 endpoint `s3.expii.top`、启用 SSL；图床 `public_base_url` 使用 `https://s3.expii.top/img`。
3. 不强制转码已有 AV1 归档；不支持目标编码时保留下载兜底。

## 已执行的远端发布动作

- commit `de884086c22eb61f8f7396fba7dfd3f94e28cb3d` 已推送到 `fix/2.5.1-playback`。
- annotated tag `v2.5.1-ex.2` 已推送，远端 tag 指向上述 commit。
- [Docker 发布 workflow #29303598667](https://github.com/olalo233/BiliNote/actions/runs/29303598667) 已成功完成镜像构建、smoke test、verified image push 和 usage instructions。
- [Commit Lint #28](https://github.com/olalo233/BiliNote/actions/runs/29303598136) 已通过。
- [PR #2](https://github.com/olalo233/BiliNote/pull/2) 为 `fix/2.5.1-playback` → `master` 的交付 PR。
- 自动触发的 Claude PR workflow 已在 `b58aa75` 移除；历史 Claude 失败 run 不再复现。
