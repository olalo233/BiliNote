# T3 — 设置页刷新白屏（vite base 相对路径）

## 根因（已实证，注意：不是 nginx 问题）

- `nginx/standalone.conf` 的 SPA fallback（`try_files $uri $uri/ /index.html`）**是有的**，线上容器也确认生效。
- 真凶：`BillNote_frontend/vite.config.ts:34` 的 `base: './'`。构建产物 index.html 用**相对路径**引资源
  （`./assets/index-*.js`）。Web 端用 BrowserRouter，设置页路由是多级路径
  （`/settings/model`、`/settings/download/:id`，见 `src/App.tsx`）。
- 在 `/settings/model` 刷新时：浏览器把 `./assets/index-*.js` 解析成 `/settings/assets/index-*.js`
  → 该文件不存在 → nginx fallback 返回 index.html（`text/html`）→ ES module 加载失败 → 白屏。
  已用线上域名实证：`curl https://bilinote.expii.top/settings` 返回的 HTML 中 script src 为 `./assets/...`。
- `base: './'` 的存在理由是 Tauri 桌面端（file:// 协议必须相对路径，且桌面端用 HashRouter 不受影响）。
  所以**不能无脑改成 '/'**，要按构建目标区分。

## 改动

`BillNote_frontend/vite.config.ts`：Docker/Web 构建用绝对 base，Tauri 构建保留相对 base。
Dockerfile.complete 已经设置 `ENV DOCKER_BUILD=1`，且 vite.config.ts 已读取该变量（文件内搜 `DOCKER_BUILD`
确认现有读取方式，跟随其写法），示例：

```ts
base: process.env.DOCKER_BUILD ? '/' : './',
```

注意核对 `pnpm dev`（本地开发）不受影响：dev server 下 base 通常无感，跑一遍确认。

## 验收标准

1. `DOCKER_BUILD=1 pnpm build` 后，`dist/index.html` 中所有 `src=`/`href=` 以 `/assets/`、`/icon.svg`
   等**绝对路径**开头（贴 index.html head 部分）。
2. 不带 `DOCKER_BUILD` 的 `pnpm build`（Tauri 路径）产物仍是 `./assets/...` 相对路径（贴对比）。
3. 端到端复现验收（核心）：本地构建完整镜像或用 nginx 容器挂 dist + standalone.conf 等价配置，
   浏览器/curl 验证：
   - `GET /settings/model` 返回的 HTML 中 script 指向 `/assets/...`；
   - `GET /assets/index-*.js` 返回 `content-type: javascript`（非 text/html）；
   - 浏览器直接打开 `http://<host>/settings/model` 并强刷新，页面正常渲染设置页，**不白屏**。
   证据：curl 输出 + 浏览器截图。
4. 首页 `/`、二级路由 `/settings/download/bilibili` 刷新均正常。
