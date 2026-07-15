# v2.5.2-ex 范围外发现与未完成验收

更新时间：2026-07-14

## 需要 CI/NAS 才能完成的验收

- Fork CI run [29382737030](https://github.com/olalo233/BiliNote/actions/runs/29382737030) 在真正进入 smoke 前失败：`docker/build-push-action@v6` 拒绝不支持的 `progress` input，原 BtbN 归档 URL 返回 HTTP 404。已改为可访问的固定 FFmpeg 7.1.5 归档并显式校验 SHA256，同时用 `BUILDKIT_PROGRESS=plain` 保留可审计构建日志；需重新跑 CI 才能取得最终硬指标。
- 后续 CI run [29382955194](https://github.com/olalo233/BiliNote/actions/runs/29382955194) 已完成镜像构建，但 smoke 因分支名被误用为 Docker tag（`feat/2.5.2` 含 `/`）在 `docker run` 前失败；已改为分支 smoke 使用 `latest`，tag smoke 才使用去掉 `v` 的 release 版本。
- CI run [29383251692](https://github.com/olalo233/BiliNote/actions/runs/29383251692) 已证明镜像尺寸为 `1099834273` bytes（低于 1.2GB）、容器启动与基础 smoke 通过，随后因缓存断言把 BuildKit 的“操作行”和下一行的 `#N CACHED` 当成同一行而误报失败；已改为按 BuildKit step ID 配对验证。
- CI run [29383372976](https://github.com/olalo233/BiliNote/actions/runs/29383372976) 已完成镜像构建、尺寸检查和基础 smoke，但缓存断言修复中的 Python 正则又被过度转义，未匹配 BuildKit step ID；已改为使用单层 `\\d` 正则并重跑。
- Fork CI run [29383602066](https://github.com/olalo233/BiliNote/actions/runs/29383602066) 已完成 T1 的镜像硬指标：`Default image size: 1099834273 bytes`；`docker history` 显示应用代码层 `1.54MB`、site-packages `528MB`、Deno `106MB`、静态 FFmpeg 两层各 `139MB`；默认镜像中 `faster-whisper`、`ctranslate2`、`av` 的 `pip show` 均返回 `Package(s) not found`；第二次构建报告 `Second build cached operation lines: 21`，并逐项打印 requirements/pip、FFmpeg、Deno、site-packages 的 `cached:` 命中。该 run 全绿并已由 CI 推送验证镜像标签。
- 同一 CI run 明确标注 Bilibili/YouTube live format check 在 runner 上不可用；真实 B 站下载+截图，以及挂载卷运行时安装本地 Whisper、首次真实转写和重建后免重复安装，仍需 NAS 或其他网络稳定的 Linux 主机补做，不能用占位内容替代。用户已明确本机热点环境禁止拉取/构建大镜像。
- T5 的镜像 push、分支合并、tag 与发版 CI 尚未执行；此前 HTTPS push 曾因 OAuth App 缺少 `workflow` scope 被拒，现已改用已恢复的 SSH 链路完成分支推送。

## 当前环境无法产生真实内容的验收

- T4 的“新浏览器/无本地 store 加载真实笔记”和 Obsidian Clipper 属性截图未完成：当前后端没有 `backend/note_results` 笔记产物，前端模型列表为空（页面提示“请先添加模型”）。不会创建合成笔记、占位视频或空心截图冒充验收证据。
- T3 浏览器验收已确认删除按钮和引用保护 API；带确认框的无引用源 UI 删除动作未在浏览器中点击，避免未经用户确认删除本地配置。后端测试和真实 API 引用保护请求已覆盖核心行为。

## 既有 lint 债务

2026-07-14 在 `BillNote_frontend` 执行 `pnpm lint`，结果为 `105 errors, 16 warnings`。错误分布在多个既有页面、组件、store 和工具文件；本批次未扩大范围修复。T4 相关的 TypeScript 检查和生产构建仍通过。
