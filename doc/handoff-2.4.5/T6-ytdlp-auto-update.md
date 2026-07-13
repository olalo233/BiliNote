# T6 — 可选的 yt-dlp 启动自更新开关（YTDLP_AUTO_UPDATE）

## 动机

yt-dlp 与 YouTube 是持续军备竞赛：这次锁 2026.7.4，若干个月后大概率再次腐烂
（症状同本次：`Requested format is not available` / nsig 失败）。给镜像加一个
**默认关闭**的启动自更新开关，线上（NAS）打开，让容器重启即取最新 yt-dlp，不必等新镜像。

## 改动

`Dockerfile.complete` 阶段3 的 supervisor 配置（heredoc 内 `[program:backend]`）：

1. 新增环境变量，默认关闭。跟随文件内现有模式——**两处都要写**
   （`[supervisord]` 的 `environment=` 兜底默认值 + `[program:backend]` 的 `%(ENV_*)s` 透传，
   Dockerfile 注释已说明漏透传就是"改 .env 没反应"的根因）：
   - `[supervisord]` environment 追加：`YTDLP_AUTO_UPDATE="0"`
   - `[program:backend]` environment 追加：`YTDLP_AUTO_UPDATE="%(ENV_YTDLP_AUTO_UPDATE)s"`
2. backend 启动命令包一层：

   ```
   command=sh -c 'if [ "$YTDLP_AUTO_UPDATE" = "1" ]; then pip install --no-cache-dir -U yt-dlp || echo "[ytdlp-auto-update] 升级失败，继续用镜像内置版本"; fi; exec python main.py'
   ```

   要点：升级失败**不阻塞启动**（`|| echo`）；`exec` 保证 python 是 supervisor 直接子进程
   （信号/重启语义不变）。
3. 在 `docker-compose.yml` 的 backend 环境变量注释区（若有集中登记处）补一行说明该开关。
4. README.md 的 Docker 部署段补一句：`YTDLP_AUTO_UPDATE=1` 开启启动时自更新（需容器出网到 PyPI）。

## 验收标准

1. 构建镜像后，默认启动（不传该变量）：`/var/log/supervisor/backend.log` **无** pip 升级动作，
   `python -m yt_dlp --version` 为镜像内置版本（2026.07.04）。证据：日志摘录 + 版本输出。
2. `-e YTDLP_AUTO_UPDATE=1` 启动：backend.log 可见 pip 升级过程，且 backend 正常进入
   `Starting server on 0.0.0.0:8483`。证据：日志摘录。
3. 断网升级失败场景（可用 `-e PIP_INDEX_URL=http://127.0.0.1:1/simple` 模拟）：
   升级报错但 backend 仍正常启动。证据：日志摘录。
4. `supervisorctl restart backend`（容器内）后 backend 能正常重启（exec 语义没破坏）。
