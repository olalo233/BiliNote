# T4 — 资源包：按视频维度的资产管理

## 需求

### 1. 后端 API（新 router 或并入 storage router）

- `GET /api/resource_pack/{platform}/{video_id}`：聚合返回该视频的资产清单——
  每项 `{kind: video|audio|subtitle|transcript|images, archived: bool, local: bool,
  size, key?, count?}`。images 项来自图床桶 `{path_prefix}/*/{task_id}/` 按该视频的
  task 汇总（task→video 映射查 `video_task_dao`）。
- `GET /api/resource_pack/presign?key=...`：对资产桶对象签发 presigned GET（1h），
  用于下载与播放。**校验 key 归属该功能的桶且不含 `..`**。
- `DELETE /api/resource_pack/object?key=...`：删除资产桶对象（仅资产桶；图床图片不提供删除，
  笔记还引用着）。
- `POST /api/resource_pack/archive`：对"本地有、桶里无"的资产手动触发归档（复用 T3 逻辑）。

### 2. 前端面板

- 笔记详情工具栏加「资源包」按钮（与"导出 Markdown"同排），展开 Sheet/Dialog 面板，
  布局按 README 设计稿要点：行式列表（视频/音频/字幕转写/截图），行尾操作按钮。
- 播放：`<video>` 标签 src 用 presigned URL（MinIO 支持 range，可拖进度条）。
- 删除有二次确认；删除后行状态变为「未归档」+「上传到对象存储」按钮。
- assets 未启用时入口隐藏。

## 验收标准

1. 对已归档视频打开资源包：四类行齐全、大小正确（与 `mc ls` 对照，贴截图+对照）。
2. 点播放：浏览器内可播放并拖动进度（贴截图；确认 Network 里是 206 分段响应）。
3. 删除音频 → 桶内对象消失、面板状态变未归档；点「上传到对象存储」→ 恢复（贴操作前后对象列表）。
4. presign 接口对非资产桶 key / 带 `..` 的 key 返回 400（贴两个请求响应）。
5. `pnpm lint`（改动文件无新增 error）+ `pnpm build` 通过；全量 pytest 通过。
