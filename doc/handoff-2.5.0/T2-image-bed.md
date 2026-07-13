# T2 — 图床：笔记截图上传与 URL 替换

## 背景

现状截图 URL 为 `IMAGE_BASE_URL`（`/static/screenshots`）相对路径，剪藏出站后全裂。

## 需求

1. 上传时机：`note.py::_post_process_markdown` 及 `_summarize_text` 中所有把截图路径
   写入 markdown 的位置（顺着 `generate_screenshot` / `video_img_urls` / `IMAGE_BASE_URL`
   的引用找全，**不要只改一处**）。图床启用时：截图落盘后 PUT 到图床源，
   key = `{path_prefix}/{YYYY-MM}/{task_id}/{basename}`，markdown 写
   `{public_base_url}/{key}`；本地文件保留（仍作为 /static 兜底与站内预览）。
2. content_type 按扩展名正确设置（jpg/png/webp），否则浏览器可能当附件下载。
3. 降级：图床未启用或单张上传失败 → 该张回退相对路径 + warning，任务不失败。
4. 幂等：重传同 key 直接覆盖（对象存储天然幂等，不需要 exists 预检）。

## 验收标准

1. 配置图床源后生成一个带截图的 B 站视频笔记（真实跑，用户实例参数）：
   - markdown 中所有图片 URL 为 `http://img.expii.top:9000/img/bilinote/...` 绝对地址（贴 markdown 片段）；
   - 任一 URL 在**未登录 BiliNote 的环境**（curl 无 cookie）GET 返回 200 且 content-type 为 image/*（贴 header）。
2. 关闭图床配置再生成：回退 `/static/screenshots/` 现状行为，任务成功。
3. 模拟上传失败（把源的 secret 改错）：任务仍 SUCCESS，日志有降级 warning，图片为相对路径。
4. 单测覆盖 key 生成与降级分支；全量 pytest 通过。
