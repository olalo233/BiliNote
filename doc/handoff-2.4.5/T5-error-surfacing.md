# T5 — 任务失败原因透出到前端 UI

## 根因（已实证：后端已支持，前端丢掉了）

- 后端失败链路是通的：`note.py` 异常时 `_update_status(task_id, FAILED, message=str(exc))`
  写入 `{task_id}.status.json` 的 `message` 字段；`GET /api/task_status/{task_id}`
  （`backend/app/routers/note.py:237`）对 FAILED 返回 `R.error(message, code=500)`——真实报错**已经在响应里**。
- 前端 `BillNote_frontend/src/hooks/useTaskPolling.ts` 把它丢了：
  - `R.error` 大概率被 axios 拦截器（`src/utils/request.ts`，实施前先核对其对 code!=0 响应的处理）
    转成 reject → 落入 `catch` 分支 → `updateTaskContent(task.id, { status: 'FAILED' })`，message никуда；
  - 即使走非异常分支，FAILED 时也只 `console.warn`，没有 toast、没有把 message 存进 taskStore。
- 用户侧表现：任务只显示笼统"失败"，两次线上事故都要 SSH 进容器翻两个日志文件才知道原因。

## 改动

1. 核对 `src/utils/request.ts` 拦截器：确保 task_status 的错误响应能拿到 message
   （从 reject 的 error 对象里取，或对该接口放行 code!=0 的响应体——选择改动最小的方式，
   不要全局改变拦截器语义）。
2. `useTaskPolling.ts`：FAILED 时
   - `updateTaskContent(task.id, { status: 'FAILED', error: message })`；
   - `toast.error('笔记生成失败：' + message)`（message 截断到 ~200 字符，避免超长 traceback 撑爆 toast）。
3. `store/taskStore` 的 task 类型增加可选 `error?: string` 字段（核对 IndexedDB persist 兼容，新增可选字段应无迁移问题）。
4. 任务列表/详情 UI（`pages/HomePage/` 下任务卡片组件）：FAILED 任务展示 error 摘要
   （一行截断 + hover/展开看全文，风格跟随现有组件）。
5. 后端顺手改一处（可选但推荐）：`note.py` 里 `message=str(exc)` 对 DownloadError 会带 ANSI 色码
   （日志里见 `ERROR:` 前有转义序列），入 status 前 strip ANSI（`re.sub(r'\x1b\[[0-9;]*m', '', s)`）。

## 验收标准

1. 本地起前后端，构造一个必然失败的任务（如提交一个不存在的视频 ID，或临时把 yt-dlp format
   改成不存在的值）：
   - 前端 toast 弹出含真实原因的失败提示（截图）；
   - 任务卡片上可见失败原因摘要（截图）；
   - 刷新页面后失败原因仍在（persist 生效）。
2. `GET /api/task_status/<失败task_id>` 的响应体里 message 无 ANSI 转义序列（贴响应）。
3. 成功任务的流程不受影响：提交一个 B 站视频跑通 SUCCESS，UI 正常出笔记。
4. `pnpm lint` + `pnpm build` 通过。
