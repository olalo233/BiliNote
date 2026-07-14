# v2.5.2-ex 范围外发现与未完成验收

更新时间：2026-07-14

## 需要 CI/NAS 才能完成的验收

- T1 镜像大小、`docker history`、两次构建缓存命中、默认镜像不含本地 Whisper 依赖及运行时安装转写，未在本机执行。用户已明确本机热点环境禁止拉取/构建大镜像，需由 GitHub Actions 或极空间 NAS 产出真实日志。
- T5 的镜像 push、分支合并、tag 与发版 CI 尚未执行；当前 HTTPS push 被 GitHub 拒绝：`refusing to allow an OAuth App to create or update workflow .github/workflows/docker-build.yml without workflow scope`。需要刷新 HTTPS 凭据并授予 `workflow` scope 后重试。

## 当前环境无法产生真实内容的验收

- T4 的“新浏览器/无本地 store 加载真实笔记”和 Obsidian Clipper 属性截图未完成：当前后端没有 `backend/note_results` 笔记产物，前端模型列表为空（页面提示“请先添加模型”）。不会创建合成笔记、占位视频或空心截图冒充验收证据。
- T3 浏览器验收已确认删除按钮和引用保护 API；带确认框的无引用源 UI 删除动作未在浏览器中点击，避免未经用户确认删除本地配置。后端测试和真实 API 引用保护请求已覆盖核心行为。

## 既有 lint 债务

2026-07-14 在 `BillNote_frontend` 执行 `pnpm lint`，结果为 `105 errors, 16 warnings`。错误分布在多个既有页面、组件、store 和工具文件；本批次未扩大范围修复。T4 相关的 TypeScript 检查和生产构建仍通过。
