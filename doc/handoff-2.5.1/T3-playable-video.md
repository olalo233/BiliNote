# T3 — 可播放视频：h264 偏好 + 多语字幕挂载

## 需求

### 1. 归档视频格式偏好 h264（`youtube_downloader.download_video` 及各平台同名方法）

```
'format': 'bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
```

- 优先 h264(avc1)，无 h264 流时按序回退（宁可 av1 也不要下载失败）。
- 已归档的 av1 视频不迁移（用户自行决定是否删了重新归档），FINDINGS 里注明。
- B 站视频本来就是 h264 为主，确认不受影响即可。

### 2. 多语字幕归档

- `youtube_subtitle.py` 现在只取一条最优轨。归档时改为：**所有人工字幕轨 + 已选中的那条**
  （自动轨只归档选中的，避免几十种机翻轨刷爆桶），每条存 `subtitle.{lang}.json`。
  实现建议：`YouTubeSubtitleFetcher` 增加 `fetch_all_manual()`，归档线程里调用，
  失败单条跳过不影响其他。
- 资源包 API 的字幕行返回可用语言列表。

### 3. 播放器字幕挂载

- 后端新端点 `GET /api/resource_pack/subtitle_vtt/{platform}/{video_id}/{lang}`：
  读资产桶 `subtitle.{lang}.json` → 转 WebVTT 文本返回（`text/vtt; charset=utf-8`）。
  时间戳格式 `HH:MM:SS.mmm`，从 segments 的 start/end 生成。**同源接口，天然无 mixed content。**
- 前端 `ResourcePackDialog` 播放器：`<video crossorigin="anonymous">` 内按语言列表渲染
  `<track kind="subtitles" srclang={lang} label={lang} src={vtt端点}>`，第一条 default。
  浏览器原生字幕菜单即可切换，不必自绘 UI。

## 验收标准

1. 新归档一个 YouTube 视频（有多语人工字幕的，如 TED 演讲）：桶内出现 ≥2 个 `subtitle.*.json`
   （贴对象列表）；ffprobe 确认 video.mp4 为 **h264**（贴 codec 输出）。
2. 通过 **https://bilinote.expii.top**（真实 NAS 部署或本地等价 https 环境）打开资源包：
   视频可播放、可拖进度、字幕可开启且随播放滚动、多语言可切换（录屏/截图；
   Network 面板显示 presign URL 为 https://s3.expii.top 且视频请求 206）。
   本地无 https 环境时：至少验证 presign URL 为 https + `<track>` DOM 正确 + VTT 端点内容
   合法（在线 VTT validator 或 ffprobe 读取），并在交付说明中注明剩余部分待 NAS 实测。
3. VTT 端点对不存在的 lang 返回 404；lang 参数校验拒绝路径穿越字符（贴请求）。
4. 全量 pytest + VTT 转换单测（含中文、多行、特殊字符转义）。
