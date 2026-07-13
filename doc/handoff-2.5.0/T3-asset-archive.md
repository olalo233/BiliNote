# T3 — 资产归档：字幕/转写/音频自动，原视频按次勾选

## 需求

### 1. 自动归档（assets 功能启用即生效，无单独开关）

- 时机：笔记生成成功后（`run_note_task` 保存结果之后），投递异步归档任务
  （`threading.Thread` 或复用现有任务执行器均可，不阻塞主链路）。
- 内容与 key（资产桶）：
  - `{platform}/{video_id}/transcript.json` ——转写结果（task 的 `_transcript.json` 内容）；
  - `{platform}/{video_id}/subtitle.{lang}.json` ——平台字幕原始结果（有则存）；
  - `{platform}/{video_id}/audio.{ext}` ——本地存在音频文件时归档（本次任务下载的或历史缓存的）。
- 幂等：同 key 已存在且 size 一致则跳过（stat 后比对），避免每个版本重复上传大文件。
- 失败重试一次，仍失败仅 log error，不影响任务状态。

### 2. 原视频归档（按次勾选）

- 生成请求模型加 `archive_video: bool = False`；前端生成表单「归档」组加勾选
  （仅 assets 启用时显示，见 README 设计稿要点）。
- 勾选时：任务流程中额外用 yt-dlp 下载**完整视频**（`bestvideo*+bestaudio/best`，
  mp4 优先，落地 `{video_id}.mp4`），归档到 `{platform}/{video_id}/video.mp4`。
  注意与现有 skip_download/仅音频逻辑隔离——不要改变未勾选时的行为。
- 视频下载失败：笔记流程照常完成，归档记 warning（与 2.4.5 的 T4 降级语义一致）。

### 3. 归档还原（红利，必须做）

- `note.py::generate` 读缓存的优先级改为：本地 task 缓存 → **资产桶按 video_id 拉
  transcript/subtitle** → 平台拉取。资产桶命中时写回本地缓存文件后走原逻辑。
- 效果：同一视频重新生成笔记不再依赖源站可达。

## 验收标准

1. 真实 e2e（用户实例参数）：生成 YouTube 笔记（不勾视频）后，
   `mc ls`/list API 显示资产桶存在 `youtube/{video_id}/transcript.json` 与 `subtitle.en-US.json`
   （贴对象列表）；再生成一个版本，大对象未重复上传（贴幂等跳过日志）。
2. 勾选「归档原始视频」生成：资产桶出现 `video.mp4`，本地 `mc`/presigned URL 可下载播放头部（`ffprobe` 探测格式正常，贴输出）。
3. 还原验证（核心）：删掉本地 `*_transcript.json` 缓存 + **临时断掉容器到 YouTube 的出口**
   （或改 hosts 指黑洞），重新生成同视频 → 字幕从资产桶还原、任务 SUCCESS（贴日志中"从资产桶还原"行）。
4. assets 未启用时：全流程行为与 2.4.5-ex.2 完全一致（回归：跑一个 B 站 + 一个 YouTube 任务）。
5. 单测覆盖幂等比对与还原优先级；全量 pytest 通过。
