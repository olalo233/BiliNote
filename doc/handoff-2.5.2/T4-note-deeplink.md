# T4 — 笔记深链 + 复制链接 + Web Clipper 属性

## 背景（现状与可行性，已核实）

- 现在**没有**直达某篇笔记的路由。路由只有 `/`、`/settings/*`、`/onboarding`；
  笔记靠点历史栏、客户端状态 `currentTaskId` 切换，**地址栏恒为 `/`**。
- 笔记数据在前端 taskStore（Zustand + IndexedDB，按浏览器）；但**后端也按 id 存**——
  `GET /api/task_status/{task_id}` 从数据卷 `{task_id}.json` 返回 markdown/transcript/audio_meta。
  所以深链可从后端水化，跨浏览器/设备可用（只要笔记文件还在服务端卷里）。
- 目标闭环：bilinote 笔记有稳定 URL → Web Clipper 把它剪进 Obsidian → 从 Obsidian 一键跳回。
- 用户已定：链接用 **task_id**（精确到剪藏的那个版本，不同版本笔记内容不同）。

## 需求

### 前端路由与水化

- 新增路由 `/note/:taskId`（Web 端 BrowserRouter；注意与 2.4.5 修复的绝对 base 兼容，
  刷新不白屏）。
- 进入 `/note/:taskId`：
  1. 若该 task 在本地 store → `setCurrentTask(taskId)` 直接展示；
  2. 若不在（换了浏览器/清了缓存）→ 调 `GET /api/task_status/{taskId}` 拉回，水化进 store 再展示；
  3. 后端也没有（已删/不存在）→ 友好空态「笔记不存在或已删除」，提供回首页。
- 展示的就是现有笔记视图（含版本、资源包、AI 问答等），不重做。

### 复制链接按钮

- 笔记工具栏（`MarkdownHeader.tsx`，与"导出 Markdown""资源包"同排）加「复制笔记链接」：
  复制 `<origin>/note/{task_id}`（origin 取 `window.location.origin`，自动适配部署域名）。
  toast「链接已复制」。
- 打开某篇笔记时，浏览器地址栏应同步反映 `/note/{task_id}`（便于直接复制地址栏）。

### Web Clipper 属性（文档 + 模板）

- 更新之前的 Clipper 模板文档（若仓库里有留存则改，否则在本任务文档附最终模板 JSON）：
  新增一条属性「bilinote 链接」抓取当前页面 URL（`{{url}}`，此时即 `/note/{taskId}`），
  与原有「原文链接」（原视频 URL）并存。
- 说明：Obsidian 笔记于是同时握有原视频链接 + bilinote 笔记链接，双向可跳。

## 验收标准

1. 生成一篇笔记后，地址栏出现 `/note/{taskId}`；点「复制笔记链接」复制到的 URL 在
   **新开的隐身窗口**（无本地 store）打开 → 笔记正常加载（证明走后端水化）（录屏/截图）。
2. `/note/不存在的id` → 友好空态，不白屏不报错。
3. `/note/:taskId` 刷新页面不白屏（2.4.5 T3 回归）。
4. Clipper 模板剪藏一篇 → Obsidian 笔记属性里「bilinote 链接」为 `/note/{taskId}` 且可点开、
   「原文链接」为原视频 URL（截图 Obsidian 属性区）。
5. `pnpm lint` + `pnpm build`；涉及后端则全量 pytest。

## 最终 Web Clipper 模板 JSON

仓库没有此前留存的 Clipper 模板文件，以下 JSON 可直接导入 Obsidian Web Clipper。
其中「原文链接」保留原视频 URL，「bilinote 链接」抓取当前页面的 `/note/{taskId}` 深链。

```json
{
  "schemaVersion": "0.1.0",
  "name": "BiliNote 笔记",
  "behavior": "create",
  "noteContentFormat": "{{content}}\n\n---\n\n原文链接：{{selector:a[href^=\"http\"]?href}}\nbilinote 链接：{{url}}",
  "properties": [
    {
      "name": "原文链接",
      "value": "{{selector:a[href^=\"http\"]?href}}",
      "type": "text"
    },
    {
      "name": "bilinote 链接",
      "value": "{{url}}",
      "type": "text"
    }
  ],
  "triggers": [],
  "noteNameFormat": "{{title}}",
  "path": "Clippings/BiliNote"
}
```

使用时应从 BiliNote 的 `/note/{taskId}` 页面启动剪藏；原视频 URL 可按现有模板
保留在「原文链接」属性中，`bilinote 链接` 则使用当前页面 URL。
