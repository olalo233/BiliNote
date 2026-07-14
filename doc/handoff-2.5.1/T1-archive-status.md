# T1 — 归档任务状态透出

## 需求

1. 后端：`asset_archive` 为每个 video_id 维护归档作业状态（内存 dict + 线程锁即可，
   不引入新存储）：`{kind: {state: pending|running|done|failed|skipped, error?, updated_at}}`，
   kind ∈ video/audio/subtitle/transcript。`enqueue_archive` 时置 pending，线程内逐项更新。
2. `GET /api/resource_pack/{platform}/{video_id}` 响应中合并作业状态：桶里没有对象但作业
   running → 前端应显示「归档中」；failed → 显示失败原因摘要。
3. 前端资源包面板：
   - running 行显示 spinner +「归档中」；failed 行显示红色摘要 + 「重试」按钮
     （调既有 `POST /api/resource_pack/archive`）；
   - 面板打开时若存在 running 项，**每 5s 自动刷新**直到无 running；
   - 视频行在 running 状态隐藏播放/下载按钮。
4. 进程重启后状态丢失（内存态）可接受：无作业状态时回退现有"已归档/不可用"两态。

## 验收标准

1. 勾选归档原视频生成一个新视频（>50MB 级，真视频）：任务完成后立即打开资源包，
   视频行显示「归档中」，无需手动刷新，归档完成后自动变为「已归档 · 大小」（录屏或时序截图）。
2. 把资产源 secret 改错重跑归档：行显示失败原因，「重试」在修复 secret 后成功（截图序列）。
3. 全量 pytest + 新增状态机单测。
