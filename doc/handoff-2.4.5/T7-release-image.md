# T7 — 发版 2.4.5：CHANGELOG、版本号、构建镜像

> 前置：T1–T6 全部完成、验收通过并已合入 `hotfix/2.4.5` 分支。

## 改动

1. `CHANGELOG.md` 新增段（Keep a Changelog 格式，日期用实际执行日）：

   ```
   ## [2.4.5] - 2026-07-XX
   ### Fixed
   - YouTube 解析失败（Requested format is not available）：升级 yt-dlp 2025.3.31 → 2026.7.4，镜像内置 deno JS 运行时用于 nsig 解密
   - 设置页多级路由刷新白屏：Docker/Web 构建改用绝对 base，Tauri 构建保留相对路径
   - 已获取平台字幕的任务不再因媒体元信息提取失败而整体失败（降级为纯文字笔记）
   ### Added
   - Cookie 删除 API 与设置页"清除 Cookie"按钮
   - 任务失败原因透出到前端（toast + 任务卡片）
   - YTDLP_AUTO_UPDATE 环境变量：启动时自更新 yt-dlp（默认关闭）
   ```

2. `README.md` 顶部版本号改 2.4.5，新增"v2.4.5 新增"摘要段（跟随现有版式）。
3. 本批次为 fork 自用发版，**不走上游的 release PR/商店流程**（RELEASING.md 的商店部分忽略）；
   合并 `hotfix/2.4.5` → `master` 在本地完成（merge commit 标题 `chore(release): v2.4.5`），
   push master 到 origin，打 tag `v2.4.5` 并 push tag。
   ⚠️ 若 push tag 触发 fork 上的 GitHub Actions 失败，不阻塞本任务（插件商店 workflow 与我们无关），
   记录到 FINDINGS.md 即可。

## 构建镜像

本机 docker=podman，目标平台 NAS x86_64：

```bash
cd ~/space/BiliNote
docker build --platform linux/amd64 \
  -f Dockerfile.complete \
  -t ghcr.io/olalo233/bilinote:2.4.5 \
  -t ghcr.io/olalo233/bilinote:latest .
```

网络注意：Dockerfile 默认 apt/pip 走清华源、BASE_REGISTRY=docker.io；如 docker.io 拉不动
按文件头注释换 `--build-arg BASE_REGISTRY=docker.m.daocloud.io`（deno-bin 阶段同样受此 ARG 控制，需确认镜像源有 denoland/deno）。

## 镜像冒烟测试（验收核心）

```bash
docker run -d --name bilinote-smoke -p 18080:80 --platform linux/amd64 ghcr.io/olalo233/bilinote:2.4.5
```

1. `curl -s localhost:18080/ | head` 返回前端 HTML，且 script src 为绝对路径 `/assets/...`。
2. `curl -s localhost:18080/settings/model | grep assets` 同样为绝对路径（T3 生效于镜像产物）。
3. `curl -s localhost:18080/api/model_list` 返回 JSON（backend 起来了）。
4. 容器内 `deno --version`、`python -m yt_dlp --version`（=2026.07.04）。
5. cookie 三连（写/删/查，见 T2 验收第1条）在 `localhost:18080/api/*` 上跑通。
6. 浏览器打开 `http://localhost:18080/settings/model` 强刷新不白屏（截图）。
7. 完整 e2e（需 LLM key，可选）：若本机代理可用，配一个 provider 提交 YouTube 视频出笔记。
   不可行则注明，由用户在 NAS 部署后做最终 e2e。

证据：以上命令输出/截图逐条贴。测完 `docker rm -f bilinote-smoke`。

## 推送镜像

`docker push` 到 ghcr 需要 `write:packages` 权限的登录态：

```bash
gh auth token | docker login ghcr.io -u olalo233 --password-stdin
docker push ghcr.io/olalo233/bilinote:2.4.5
docker push ghcr.io/olalo233/bilinote:latest
```

⚠️ 推送是对外发布动作：**推送前停下来向用户确认**（gh token 权限不足时也是找用户，不要自行折腾凭据）。

## 交付物清单

- [ ] origin master 含全部修复 + tag v2.4.5
- [ ] ghcr.io/olalo233/bilinote:2.4.5 镜像（已推送或本地待推，视用户确认）
- [ ] 冒烟测试证据（本文件验收 1–6）
- [ ] FINDINGS.md（若过程中发现新问题）

## 部署（不在执行者范围内，留给用户）

NAS 为极空间自研系统，禁止 SSH 部署：用户在 NAS 容器 UI 里把镜像换成
`ghcr.io/olalo233/bilinote:2.4.5`，环境变量加 `YTDLP_AUTO_UPDATE=1`，沿用现有卷挂载重建容器。
之后由排查会话在日志层面确认全链路（字幕→笔记）跑通，并更新 ansible 仓 vars/nas-services.yml 的镜像登记。
