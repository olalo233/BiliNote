# T5 — 设置页：图床/资产 tab、源管理、用量展示

## 需求

### 1. 设置页新增一级 tab「图床」「资产」

- 路由 `settings/image-bed`、`settings/assets`（沿用 SettingPage 现有 tab 结构；
  注意 App.tsx 路由与 T3 白屏修复的绝对 base 无冲突）。
- 每页结构（照 README 设计稿）：
  1. 启用开关 + 源下拉（列出 sources 池）+「新建源」（表单字段=源模型；secret 输入框 type=password）；
  2. 功能特有设置：图床页 `public_base_url`、`path_prefix`；资产页无额外字段（自动归档说明文案）；
  3. 「测试连接」按钮 → 调 T1 test API，三步结果逐项打勾/打叉展示；
  4. 「保存」→ POST feature/source API，toast 反馈。
- 源管理是共享池：在任一 tab 新建的源，另一 tab 下拉可见；删除被引用的源时按 T1 的 400 提示。

### 2. 用量展示

- 后端 `GET /api/storage/usage/{feature}`：调 T1 `list_prefix_stats` 聚合
  （图床：前缀 `{path_prefix}/`；资产：整桶，并按 kind 前缀细分 video/audio/subtitle+transcript 三类）。
  结果按 feature 内存缓存 1h，带 `?refresh=1` 强刷。
- 前端：功能页底部用量卡片（对象数、人类可读大小、最近上传时间；资产页附三类明细一行），
  右上手动刷新按钮。样式对齐设计稿（metric card）。

## 验收标准

1. 全流程 UI 操作录证：新建两个源 → 图床/资产分别绑定 → 测试连接三步全绿 → 保存 →
   刷新页面配置仍在（截图序列）。
2. 用量卡片数字与 `mc du`（或 list 汇总）一致，误差为 0（贴对照）；`?refresh=1` 后
   新上传对象计入。
3. secret 在页面回显与 network 响应中均为打码（截图 + 响应片段）。
4. 设置页多级路由（`/settings/image-bed`）强刷新不白屏（2.4.5 T3 回归项）。
5. `pnpm lint`（改动文件无新增 error）+ `pnpm build`；全量 pytest。
