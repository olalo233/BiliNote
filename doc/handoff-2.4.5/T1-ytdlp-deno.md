# T1 — yt-dlp 升级到 2026.7.4 + 镜像内置 deno JS 运行时

## 根因（已实证，勿重查）

1. `backend/requirements.txt:128` 锁死 `yt-dlp==2025.3.31`。YouTube 已更换播放器签名算法（nsig），
   旧版解不出任何音视频流（`yt-dlp -F` 只列 storyboard 缩略图），于是
   `format: 'bestaudio[ext=m4a]/bestaudio/best'` 必然报
   `ERROR: Requested format is not available`。
2. 新版 yt-dlp（2025.10+ 引入 EJS）需要外部 JS 运行时做 nsig 解密，默认只启用 **deno**。
   当前镜像没有任何 JS 运行时，新版能靠降级路径工作但会警告
   `No supported JavaScript runtime could be found`，且 YouTube 下次改算法时会再次失效。

## 改动

### 1. requirements.txt

```
yt-dlp==2025.3.31  →  yt-dlp==2026.7.4
```

（2026.7.4 是 2026-07-13 时 PyPI 最新版，已在线上容器实测可解析格式。）

### 2. Dockerfile.complete — 阶段3 运行时镜像内置 deno

用官方二进制镜像多阶段拷贝（不要用 curl 安装脚本，避免构建时网络不确定性）：

```dockerfile
# 在阶段3 FROM python:3.11-slim 之前增加：
FROM ${BASE_REGISTRY}/denoland/deno:bin AS deno-bin

# 阶段3内、apt 安装之后增加：
COPY --from=deno-bin /deno /usr/local/bin/deno
```

注意：
- `denoland/deno:bin` 的 tag 建议 pin 具体版本（去 hub 查当前 2.x 最新的 `bin-2.x.y` tag），
  与本仓其他依赖 pin 风格一致；确实查不到可用 `bin`（latest）。
- deno 是 glibc 动态链接二进制，python:3.11-slim（bookworm）可直接运行，无需额外依赖。
- yt-dlp 从 PATH 自动发现 deno，无需配置。
- deno/yt-dlp EJS 需要可写缓存目录；容器以 root 跑，默认 HOME=/root 可写，一般无需处理。
  若验收时遇到缓存写入报错，加 `ENV DENO_DIR=/tmp/deno-cache` 解决。
- `docker-compose.gpu.yml` 若引用了独立的 GPU Dockerfile，本任务**不改** GPU 变体（超范围）。

## 验收标准

1. `pip install -r backend/requirements.txt` 在干净 venv（Python 3.11）中成功，无依赖冲突。
   证据：安装输出末尾 + `pip show yt-dlp` 显示 2026.7.4。
2. 构建镜像（可只 build 到阶段3，`--platform linux/amd64`）后，容器内：
   - `deno --version` 输出版本号；
   - `python -m yt_dlp --version` 输出 `2026.07.04`。
3. 容器内跑（本机代理网络下）：
   `python -m yt_dlp -F 'https://www.youtube.com/watch?v=YM0_8mOaKic'`
   - 格式表中存在 m4a/webm 音频行（不再只有 sb* storyboard）；
   - stderr **没有** `nsig extraction failed`、**没有** `No supported JavaScript runtime`。
   若构建机容器内无法走代理触达 YouTube：改为在宿主机 venv 装 yt-dlp==2026.7.4 + 本机 deno 验证同一命令，
   并单独证明镜像内 deno 可执行（验收项2）。
4. 回归：`python -m yt_dlp -F` 对一个 B 站视频（如 BV1CNLQ6REGh）仍能列出格式（B 站路径不受影响）。
