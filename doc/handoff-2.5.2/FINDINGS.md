# v2.5.2-ex 范围外发现与未完成验收

更新时间：2026-07-15

## T5 发版证据

- `master` 已从最新 `origin/master`（`2cd0356`，包含 2.5.1）快进后，以 merge commit `ec6755fdb4762f91f23df8fd3383cff1f32bc1e4`（`chore(release): v2.5.2-ex`）合并 `feat/2.5.2`，并已推送到 fork `origin/master`。
- annotated tag `v2.5.2-ex` 已推送到 origin，指向上述 release merge commit。
- 发版 Docker CI [29386182139](https://github.com/olalo233/BiliNote/actions/runs/29386182139) 全绿：release tag 校验、Docker 构建、smoke、verified image push 和 usage instructions 均通过。日志内容检查：`Default image size: 1099834285 bytes`、`faster-whisper`/`ctranslate2`/`av` 均为 `Package(s) not found`、第二次构建 `Second build cached operation lines: 12`；推送标签 `ghcr.io/olalo233/bilinote:2.5.2-ex` 与 `ghcr.io/olalo233/bilinote:latest` 同 digest `sha256:0faa918943b894d6ce9d2e446016abcaccb6726cb2a7ff9fe6d117afb26c0eec`。

## 需要 CI/NAS 才能完成的验收

- Fork CI run [29382737030](https://github.com/olalo233/BiliNote/actions/runs/29382737030) 在真正进入 smoke 前失败：`docker/build-push-action@v6` 拒绝不支持的 `progress` input，原 BtbN 归档 URL 返回 HTTP 404。已改为可访问的固定 FFmpeg 7.1.5 归档并显式校验 SHA256，同时用 `BUILDKIT_PROGRESS=plain` 保留可审计构建日志；需重新跑 CI 才能取得最终硬指标。
- 后续 CI run [29382955194](https://github.com/olalo233/BiliNote/actions/runs/29382955194) 已完成镜像构建，但 smoke 因分支名被误用为 Docker tag（`feat/2.5.2` 含 `/`）在 `docker run` 前失败；已改为分支 smoke 使用 `latest`，tag smoke 才使用去掉 `v` 的 release 版本。
- CI run [29383251692](https://github.com/olalo233/BiliNote/actions/runs/29383251692) 已证明镜像尺寸为 `1099834273` bytes（低于 1.2GB）、容器启动与基础 smoke 通过，随后因缓存断言把 BuildKit 的“操作行”和下一行的 `#N CACHED` 当成同一行而误报失败；已改为按 BuildKit step ID 配对验证。
- CI run [29383372976](https://github.com/olalo233/BiliNote/actions/runs/29383372976) 已完成镜像构建、尺寸检查和基础 smoke，但缓存断言修复中的 Python 正则又被过度转义，未匹配 BuildKit step ID；已改为使用单层 `\\d` 正则并重跑。
- Fork CI run [29383602066](https://github.com/olalo233/BiliNote/actions/runs/29383602066) 已完成 T1 的镜像硬指标：`Default image size: 1099834273 bytes`；`docker history` 显示应用代码层 `1.54MB`、site-packages `528MB`、Deno `106MB`、静态 FFmpeg 两层各 `139MB`；默认镜像中 `faster-whisper`、`ctranslate2`、`av` 的 `pip show` 均返回 `Package(s) not found`；第二次构建报告 `Second build cached operation lines: 21`，并逐项打印 requirements/pip、FFmpeg、Deno、site-packages 的 `cached:` 命中。该 run 全绿并已由 CI 推送验证镜像标签。
- NAS `nas_z423` 已补做真实内容检查：隔离容器用 `yt-dlp` 下载公开视频 `https://www.bilibili.com/video/BV1VR4y1p7zq/` 的真实音频并转 WAV；仓库 `generate_screenshot()` 对真实视频流生成 JPEG，输出 `SCREENSHOT_BYTES=16661`、JPEG magic `ffd8ffe000104a464946`。
- NAS 临时卷已验证本地 Whisper 懒加载的关键链路：首次 `ensure_local_whisper()` 日志显示固定三包安装到 `/app/backend/data/runtime-deps/py311`；同卷新容器再次启动只输出 `local_whisper_runtime_ready`，未重复安装；使用官方 `faster-whisper-tiny` 模型对该真实 B 站音频转写，输出 `TRANSCRIBE_LANGUAGE=zh`、`TRANSCRIPT_CHARS=1278`，抽查文本为可读中文（有正常模型误识别，不是对象 repr/空文本）。用户已明确几乎不使用本地 Whisper，本批次不再继续该方向探索。
- NAS 的 Hugging Face Hub 自动 HEAD/重定向探测在 `hf-mirror.com` 上失败；为完成一次真实转写，模型文件通过该镜像可用的 `resolve` GET 接口放入临时卷后加载。该网络兼容性事实保留，不把它包装成默认自动下载已验证。
- Fork CI run [29385226801](https://github.com/olalo233/BiliNote/actions/runs/29385226801) 已针对提交 `a13a887` 全绿：Docker 构建、镜像 smoke、验证标签推送和 usage instructions 均通过，耗时 3m6s；仅保留 Node 24 强制兼容提示以及 CI runner 无法访问 Bilibili/YouTube 的既有 warning。NAS 拉取该 run 推送的 `latest` 镜像成功，digest 为 `sha256:fc7b98de8c4e4ba324427625f67da20599e00f742e248f9478284dd09c216acd`。
- 新镜像在 NAS 隔离容器 `bilinote-252-app-e2e` 上启动成功。该镜像首次深链打开真实 task `32a0a7c5-9771-41b9-90e8-b818a50fdd59` 时曾暴露前端 `ReferenceError: field is not defined`；根因是 `NoteForm` 的平台 `FormField` 回调没有解构 `field`，已由 `a13a887` 修复。修复镜像浏览器实测渲染真实 Markdown（标题“高并发热点账户性能攻坚”）、页面 URL 保持 `/note/<task_id>`，无运行时 error。
- T5 的镜像 push、分支合并、tag 与发版 CI 尚未执行；此前 HTTPS push 曾因 OAuth App 缺少 `workflow` scope 被拒，现已改用已恢复的 SSH 链路完成分支推送。

## 已完成真实内容验收

- T4 深链在更新后的 CI 镜像上用独立浏览器 tab 实测：新镜像从后端水化真实 task，DOM 含完整标题、目录和正文；地址栏为 `http://127.0.0.1:18081/note/32a0a7c5-9771-41b9-90e8-b818a50fdd59`，工具栏含“复制笔记链接”，点击后无 console error。刷新后仍能加载。不存在的 id 显示“笔记不存在或已删除”和“回到首页”，不白屏；仅有既有 Dialog `aria-describedby` warning 和预期的 not-found warning。
- T3 在 NAS 隔离配置副本中创建未引用源 `T3-delete-unreferenced-20260715`，通过真实前端删除按钮完成确认、toast“已删除”、列表移除，刷新后源仍不存在。对真实绑定的 `minio-img-ssl` 发起删除，得到 `HTTP_STATUS=400`、`source minio-img-ssl 正被功能引用: image_bed`，配置再次读取确认源仍存在。

## 当前环境无法产生真实内容的验收

- T2 的真实模型生成验收和 T4 的 Obsidian Web Clipper 属性验收由用户接手验证；本批次不再由执行环境重复验证。提示词库实现、模板 CRUD 证据及 T4 Web 深链证据仍保留在上文，用户完成后可补充最终截图/生成产物。

## 既有 lint 债务

2026-07-14 在 `BillNote_frontend` 执行 `pnpm lint`，结果为 `105 errors, 16 warnings`。错误分布在多个既有页面、组件、store 和工具文件；本批次未扩大范围修复。T4 相关的 TypeScript 检查和生产构建仍通过。
