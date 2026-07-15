# T1 — 镜像优化：缓存命中确定化 + 瘦身 + 本地 whisper 懒加载

## 背景（审阅方已在 NAS 实测的层分布）

`2.5.1-ex.2` 镜像 2.01GB，`docker history` 大头：

| 层 | 大小 | 处置 |
|---|---|---|
| Python site-packages | 1.25GB | 见下（whisper 移出 + hf-xet 删） |
| apt ffmpeg + 编解码依赖 | 509MB | 换静态 ffmpeg 构建 → ~80MB |
| deno | 106MB | **保持内置**（核心依赖，勿动） |
| debian base + python 构建依赖 | ~120MB | 固定，不动 |

site-packages 内实测最大项：hf_xet 209MB、ctranslate2(.libs) 195MB、av(.libs) 114MB、
modelscope 61MB、chromadb_rust_bindings 57MB、onnxruntime 49MB、sympy 77MB、kubernetes+asyncio 85MB。
依赖关系（pipdeptree --reverse 实测）：av←faster-whisper；kubernetes←chromadb；
sympy←onnxruntime←(chromadb + faster-whisper)。

## 目标（硬指标，验收按数字卡）

1. 默认镜像 **< 1.2GB**（当前 2.01GB）。
2. **仅改后端代码**的增量更新，重新构建后**只有应用代码层变化**（不重拉 GB 级依赖层）。

## 需求

### A. 删 hf-xet（-209MB，零功能损失）

- `requirements.txt` 删除 `hf-xet==1.0.0` 显式 pin。它只是 huggingface_hub 的可选下载加速器，
  移除后模型下载退回普通 HTTP，功能不变。
- 若 huggingface_hub 仍把它当可选 extra 拉回，追加约束或 `--no-binary`/环境变量
  `HF_HUB_DISABLE_XET=1` 兜底，确保镜像内 site-packages 不含 `hf_xet`。

### B. ffmpeg 换静态构建（-~400MB，零功能损失）

- `Dockerfile.complete` 运行时镜像：不再 `apt install ffmpeg`（保留 nginx supervisor procps）。
  改为多阶段拉取静态 ffmpeg+ffprobe 二进制放 `/usr/local/bin`。
  推荐 johnvansickle amd64 static（GPL，自托管无碍），pin 具体版本 URL/校验和；
  或用一个可信的 ffmpeg-static 镜像 `COPY --from`。
- 校验：`ffmpeg -version` / `ffprobe -version` 可执行；截图抽帧（`generate_screenshot`）
  与 B 站音频 `FFmpegExtractAudio` mp3 转码正常。

### C. 本地 whisper 懒加载落盘（-~250-320MB，功能改为按需）

这是本任务最复杂、最高风险的部分，仔细做：

1. `requirements.txt` 移除 `faster-whisper`、`ctranslate2`、`av`（PyAV）。
   （onnxruntime/sympy 因 chromadb 仍需要，**留着**——别误删导致 chromadb 崩。）
2. 代码去顶层硬 import：`app/transcriber/whisper.py` 的 `from faster_whisper import WhisperModel`
   等必须改为**函数内延迟 import**；`transcriber_provider.py` 工厂对 whisper 类型做
   try-import，缺失时不影响其它引擎（bcut/groq/kuaishou）与整体启动。
3. 运行时安装器：新增 `app/services/optional_deps.py`（或类似），提供
   `ensure_local_whisper()`：
   - 目标路径为挂载卷下的固定目录（如 `${DATA_DIR}/runtime-deps/py311`），加入 `sys.path`；
   - check-then-install：先尝试 import，失败则 `pip install --target=<路径>` **pin 死版本**
     （faster-whisper==1.1.1 ctranslate2==4.6.0 av==14.2.0，与移除前一致）；
   - 装完再 import；全过程有清晰日志与状态，失败不崩主进程、向前端回明确原因。
4. 触发时机：用户在「转写设置」选择 fast-whisper 且库缺失时触发安装（可复用现有的
   转写模型就绪门禁 `transcriber_model_not_ready` 那套 UX，新增一个
   `local_whisper_not_installed` 状态引导）。**默认 bcut 路径完全不碰这些库。**
5. 版本匹配：`pip install --target` 的包必须匹配容器 Python 3.11 + glibc；用镜像内
   同一 pip 安装即可保证 ABI 一致。

### D. 缓存命中确定化（解决"每次更新重拉大层"）

1. builder 阶段 pip 安装加 `--no-compile`（不生成随机时间戳的 .pyc）+ 设
   `PYTHONDONTWRITEBYTECODE=1`；确保同一 `requirements.txt` 产出**字节稳定**的 site-packages
   层（layer digest 可复现）。
2. 严格分层顺序（稳定→易变）：base → apt(nginx/supervisor/procps) → ffmpeg-static →
   `COPY requirements.txt` + `pip install`（依赖层，只随 requirements 变）→ deno →
   前端 dist → **后端代码（最后、最小、最常变）**。
3. CI 缓存改用 **registry cache**（`cache-to: type=registry,ref=...,mode=max` +
   `cache-from: type=registry`），替代/叠加 gha cache（gha 10GB LRU 会驱逐导致非确定重建）。
   registry 缓存可复用 ghcr 同仓的一个 `:buildcache` tag。

## 验收标准（逐条贴证据）

1. **尺寸**：`docker history` 显示默认镜像 < 1.2GB；site-packages 层不含 `hf_xet`/
   `faster_whisper`/`ctranslate2`/`av`（贴 `docker run --rm --entrypoint sh IMG -c
   'du -sm /usr/local/lib/python3.11/site-packages/* | sort -rn | head' + pip list | grep -iE ...'`）。
   —— 在 CI 或 NAS 上做，勿在 MacBook 拉。
2. **缓存命中（核心）**：在 CI 上连续两次构建，第二次仅改一行后端代码 →
   第二次构建日志显示依赖层/ffmpeg 层/deno 层全部 `CACHED`，只有后端代码层重建；
   贴两次构建的 buildkit 层缓存日志对比。
3. **ffmpeg**：容器内 `ffmpeg -version` 正常；真实跑一个带截图的 B 站笔记，截图正常生成
   （NAS 或 CI）。
4. **本地 whisper 懒加载**：
   a. 默认镜像 `pip list` 无 faster-whisper/ctranslate2/av；backend 正常启动（bcut 可用）；
   b. 触发本地 whisper → 运行时安装到挂载卷路径 → 首次转写成功（NAS 实测，贴日志：
      安装过程 + 转写产出内容抽查非空非乱码）；
   c. 容器重建后（卷保留）第二次用本地 whisper 不重复安装（命中卷内已装）。
5. **回归**：默认路径（bcut 在线转写、图床、资产归档、资源包播放）与 2.5.1-ex.2 行为一致。
6. 全量 pytest 通过（whisper 相关测试若依赖库存在，用 skip/mock 保证默认环境可跑）。
