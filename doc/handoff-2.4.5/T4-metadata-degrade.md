# T4 — 有字幕时元信息提取不应因格式选择崩掉；媒体下载失败降级

## 根因（已实证，有个反直觉点）

`backend/app/services/note.py` 的 `generate()` 其实**已经**做了"有字幕就跳过下载"：
拿到平台字幕后 `need_full_download=False`，以 `skip_download=True` 调 `_download_media()`（约 176 行）。

但线上日志证明它照样崩：字幕成功（627 段）后，任务仍以
`DownloadError: Requested format is not available` FAILED。原因在
`backend/app/downloaders/youtube_downloader.py` 的 `download()`：

```python
ydl_opts = {'format': 'bestaudio[ext=m4a]/bestaudio/best', ...}
if skip_download:
    ydl_opts['skip_download'] = True
info = ydl.extract_info(video_url, download=not skip_download)
```

`skip_download=True` 只是不落盘，**格式选择仍然执行**——yt-dlp 解不出流时（老版本 nsig 失败，
或未来任何一次 YouTube 变更），连"只取标题/时长/封面"的元信息路径也会抛
`Requested format is not available`。字幕白拿了，任务整体失败。

T1 升级 yt-dlp 后此问题当下不触发，但这是结构性脆弱点：**字幕已到手的任务不应被媒体层杀死**。

## 改动

### 1. `youtube_downloader.py::download` — 元信息模式不做格式选择

`skip_download=True` 时调整 ydl_opts：

```python
if skip_download:
    ydl_opts['skip_download'] = True
    ydl_opts.pop('format', None)                  # 不请求特定格式
    ydl_opts['ignore_no_formats_error'] = True    # 解不出流也返回元信息而非抛错
```

`extract_info` 返回的 info 仍含 id/title/duration/thumbnail（元信息来自页面而非流）。
注意 `ext` 字段此时可能缺失，现有代码有 `info.get("ext", "m4a")` 兜底，核对 audio_path
在 skip 场景下本来就不会被读取（`_download_media` 上层）。

### 2. `note.py::generate` — 媒体下载失败时降级而非失败

包住 `_download_media` 调用：**当 `has_transcript=True` 时**媒体下载抛异常不再让任务 FAILED，
而是：

- log warning（含原始异常）；
- 构造最小 `AudioDownloadResult`（video_id 用 `extract_video_id(video_url)`，title 可用
  video_id 兜底，duration=0，cover_url=None，file_path 置空/None——核对下游
  `_summarize_text` / `_save_metadata` 对这些字段的使用，确保 None 安全）；
- 若用户勾选了 screenshot / video_understanding，在降级时给出明确日志
  "媒体下载失败，本次笔记不含截图/视频理解"，并跳过对应后处理（`_post_process_markdown`
  的 screenshot 分支、`video_img_urls`）；
- 继续走 GPT 总结，产出纯文字笔记。

`has_transcript=False` 时行为不变（没字幕又下不了媒体，本来就该失败）。

## 验收标准

1. 单测（`backend/tests/`，pytest）：mock `YoutubeDownloader.download` 抛 `DownloadError`，
   且 `download_subtitles` 返回有效 transcript，断言 `generate()` 正常产出 markdown、
   状态最终为 SUCCESS 而非 FAILED。证据：pytest 输出。
2. 单测：`skip_download=True` 路径下构造的 ydl_opts 不含 `format`、含
   `ignore_no_formats_error=True`（可抽小函数便于测试）。
3. 集成验证（本机代理网络，backend 本地起）：提交一个**有字幕**的 YouTube 视频
   （如 YM0_8mOaKic）不开截图 → 任务 SUCCESS，日志显示"成功获取平台字幕"且无媒体下载报错。
4. 回归：提交一个**无字幕**的 YouTube 视频（或 mock）→ 仍走音频下载+转写路径；
   B 站视频（BV1CNLQ6REGh）全流程不受影响（含截图路径）。证据：两次任务的状态与日志摘录。
