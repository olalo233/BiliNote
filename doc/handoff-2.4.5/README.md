# v2.4.5 修复批次 — 执行交接总纲

> 本目录是排查会话（2026-07-13）产出的实施指引。根因均已在线上环境（NAS 容器 bilinote，镜像 2.4.4）实证，
> 执行者按任务文档实施即可，**不需要重新排查根因**；但每个任务的验收标准必须逐条跑过并附证据。

## 背景

线上 BiliNote 2.4.4 解析 YouTube 视频失败。排查确认了两层根因（yt-dlp 过旧 + 缺 JS 运行时），
顺带发现若干工程问题。本批次在 fork（olalo233/BiliNote）内修复并发布 2.4.5 镜像。

## 铁律

1. **禁止向上游 JefferyHcool/BiliNote 发 PR 或 push**。所有工作只在 origin（olalo233/BiliNote）。
2. 工作分支：`hotfix/2.4.5`（已从 master 切出）。每完成一个任务 commit 一次并 push 到 origin。
3. Commit message 必须符合 commitlint：`type(scope): subject`（如 `fix(youtube): ...`）。
4. **验收标准必须真实执行**，在任务完成汇报中粘贴命令与输出。不允许"理论上可行"式跳过。
   本机无法触达 YouTube 的验收项，标注了替代验证方式，按标注执行。
5. 不做任务文档范围之外的重构。发现新问题记录到本目录 `FINDINGS.md`（新建），不擅自扩scope。

## 任务清单（建议执行顺序）

| # | 文件 | 主题 | 层 |
|---|------|------|----|
| T1 | [T1-ytdlp-deno.md](T1-ytdlp-deno.md) | yt-dlp 升级 + 镜像内置 deno JS 运行时 | backend deps / Dockerfile |
| T2 | [T2-cookie-delete.md](T2-cookie-delete.md) | Cookie 删除端点 + 前端清除按钮 | backend + frontend |
| T3 | [T3-spa-refresh-blank.md](T3-spa-refresh-blank.md) | 设置页刷新白屏（vite base 相对路径） | frontend build |
| T4 | [T4-metadata-degrade.md](T4-metadata-degrade.md) | 有字幕时元信息提取不应因格式选择崩掉；媒体失败降级 | backend |
| T5 | [T5-error-surfacing.md](T5-error-surfacing.md) | 任务失败原因透出到前端 UI | frontend（backend 已支持） |
| T6 | [T6-ytdlp-auto-update.md](T6-ytdlp-auto-update.md) | 可选的 yt-dlp 启动自更新开关 | Dockerfile/supervisor |
| T7 | [T7-release-image.md](T7-release-image.md) | CHANGELOG、版本号、构建 2.4.5 镜像 | release |

T1–T6 相互独立可并行，T7 必须最后做（依赖前面全部合入）。

## 本地环境须知

- 本机 macOS，`docker` 已 alias 到 podman（applehv machine）。构建镜像必须指定 `--platform linux/amd64`
  （目标 NAS 是 x86_64）。
- 后端本地跑：`cd backend && pip install -r requirements.txt && python main.py`（Python 3.11）。
- 前端本地跑：`cd BillNote_frontend && pnpm install && pnpm dev`（Node 20+，pnpm 9）。
- 本机网络可直连 YouTube（有代理）。容器内验证 YouTube 连通性时结果受构建机网络影响，验收标准里已注明。

## 线上事实（排查已确认，写指引时的依据）

- 线上容器：NAS（极空间 Z423）上名为 `bilinote` 的容器，镜像 tag 2.4.4，supervisor 托管 nginx + `python main.py`。
- 后端日志两处：`/app/backend/logs/app.log`（logger 输出）与 `/var/log/supervisor/backend.log`（stdout/traceback）。
- 已实证的故障链：yt-dlp 2025.3.31 nsig 解密失败 → 只解出 storyboard → `bestaudio` 选择失败 →
  `DownloadError: Requested format is not available` → 任务 FAILED。容器内手动升级 yt-dlp 2026.7.4 后格式解析恢复
  （但有 "No supported JavaScript runtime" 警告 → 因此 T1 要求内置 deno）。
