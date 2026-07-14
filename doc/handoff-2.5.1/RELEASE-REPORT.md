# v2.5.1-ex 交付报告

## 已实现

- T1：归档线程按 video/audio/subtitle/transcript 透出 pending、running、done、failed、skipped 状态；资源包面板自动轮询归档中状态，并支持失败重试。
- T2：缓存加载、预取字幕缓存和资产还原均保留 `raw`；对象不存在的 stat 检查只记 debug。
- T3：新视频归档优先 avc1；YouTube 归档人工字幕轨与选中轨；资源包返回语言列表并提供同源 WebVTT 与原生 `<track>`。
- T4：README、CHANGELOG、部署说明和 AV1 存量说明已更新。

## 本地验证记录

以下命令在 `2026-07-14` 于本工作树实际执行：

```text
cd backend && PYTHONPATH=. pytest -q
86 passed, 3 subtests passed

cd backend && PYTHONPATH=. python -m compileall -q app tests
passed

cd BillNote_frontend && pnpm exec tsc --noEmit
passed

cd BillNote_frontend && pnpm exec eslint src/services/resourcePack.ts src/pages/HomePage/components/ResourcePackDialog.tsx
passed

cd BillNote_frontend && pnpm build
passed

cd BillNote_frontend && pnpm lint
failed on the repository baseline: 115 errors and 16 warnings; the two changed frontend files pass targeted lint above.
```

新增用例覆盖归档状态生命周期、缓存 `raw` 往返、旧缓存兼容、NoSuchKey 日志、H.264 格式契约、多语字幕选择、VTT 时间戳/转义、语言路径校验和资源包响应。

## 尚待部署环境验证

- 本机 Browser 初始化失败（`Cannot redefine property: process`），因此未把静态构建冒充成渲染录屏或 DOM 证据。
- 真实 NAS/S3 的大视频对象列表、`https://s3.expii.top` presign、206 range、ffprobe H.264 和多语字幕播放仍需在部署环境执行；本地对该端点的只读检查未获外部访问授权，未改动桶内容。
- 已归档 AV1 存量不迁移；见 [FINDINGS.md](FINDINGS.md)。

## 部署清单

1. 极空间换镜像 `ghcr.io/olalo233/bilinote:2.5.1-ex`。
2. 设置页两个存储源使用 endpoint `s3.expii.top`、启用 SSL；图床 `public_base_url` 使用 `https://s3.expii.top/img`，分别测试连接。
3. 旧 AV1 归档如需 Safari 播放：资源包删除旧视频后重新勾选归档。

本地 bugfix commit 已标记 annotated tag `v2.5.1-ex`；发布镜像、CI run 链接和 NAS 录屏需在完成部署验证后补入本报告，当前尚未执行 push。
