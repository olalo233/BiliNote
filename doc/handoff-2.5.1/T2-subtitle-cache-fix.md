# T2 — 缓存路径字幕归档修复 + stat 日志降噪

## 需求

1. **根因修复**：`note.py` 从 `{task_id}_transcript.json` 缓存加载时，构造
   `TranscriptResult(language, full_text, segments)` 丢失了 `raw`。修法二选一（推荐 a）：
   a. 缓存写入时序列化完整 `asdict(transcript)`（含 raw），加载时还原 raw——检查现有缓存
      写入点是否已含 raw（`transcript_cache_file.write_text(json.dumps(asdict(...)))` 应该已含），
      则只需加载侧补 `raw=data.get("raw")`、`language=data.get("language")`；
   b. `archive_note` 的字幕归档不依赖 `note.transcript.raw`，改从缓存文件/资产桶已有信息推导。
   注意兼容旧缓存文件（无 raw 键）不崩。
2. **还原路径同样处理**：`asset_archive.restore_transcript` 从资产桶还原时也要带 raw，
   避免"还原→重新归档字幕"再次因 raw 缺失跳过。
3. **日志降噪**：`object_storage.stat_object` 对 `NoSuchKey` 是幂等检查的预期分支，
   当前打全栈 traceback（exc_info）刷屏。改为：NoSuchKey → 单行 debug；
   其他 S3 错误保留 warning + traceback。

## 验收标准

1. 复现修复：删除资产桶中某视频的 `subtitle.*.json`（保留本地 task 缓存）→ 重跑该任务
   （重新生成）→ 字幕重新归档成功（贴桶对象列表前后对比 + 日志）。
2. backend.log 中不再出现 NoSuchKey 的多行 traceback（贴幂等跳过场景的日志片段）。
3. 旧格式缓存文件（手工删掉 raw 键）加载不崩、任务成功。
4. 全量 pytest + 针对性单测（缓存 raw 往返、NoSuchKey 降噪）。
