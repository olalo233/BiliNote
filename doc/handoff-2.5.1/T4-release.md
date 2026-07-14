# T4 — 发版 v2.5.1-ex

## 步骤

1. CHANGELOG `## [2.5.1-ex]`（Fixed：归档状态可见/缓存字幕归档/h264/字幕挂载/日志降噪）；
   README 的 storage 配置示例把 endpoint 更新为 `s3.expii.top` + `use_ssl: true`、
   `public_base_url: https://s3.expii.top/img`，并注明 http 直连入口仍可用于纯内网 http 场景。
2. 合并 `fix/2.5.1-playback` → master（`chore(release): v2.5.1-ex`），tag `v2.5.1-ex`，
   CI（build→smoke→push）绿。
3. 交付清单：镜像 tag、全部验收证据、FINDINGS（含 av1 存量说明）。

## 部署交接（写给用户的清单，附在交付报告里）

1. 极空间换镜像 `ghcr.io/olalo233/bilinote:2.5.1-ex`。
2. BiliNote 设置页两个源的 endpoint 改为 `s3.expii.top`、启用 SSL；
   图床 public_base_url 改为 `https://s3.expii.top/img`；各自测试连接。
3. 旧的 av1 归档视频如需 Safari 播放：资源包删除后重新勾选归档（会按 h264 重下）。

## 验收标准

1. CI 全绿（贴 run 链接）。
2. 拉发布镜像本地起，配 https 源后完整跑：生成（勾归档）→ 面板显示归档中→已归档 →
   播放（https presign + 206）→ 字幕切换。全链路证据。
