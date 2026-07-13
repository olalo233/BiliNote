# T1 — 存储源框架：配置管理、S3 客户端、源管理 API

## 目标

建立"命名存储源池 + 功能绑定"的地基，供 T2–T5 使用。

## 需求

### 1. 配置模型 `config/storage.json`

```json
{
  "sources": {
    "minio-img":    {"type": "s3", "endpoint": "img.expii.top:9000", "access_key": "...", "secret_key": "...", "bucket": "img", "path_style": true, "use_ssl": false},
    "minio-assets": {"type": "s3", "endpoint": "img.expii.top:9000", "access_key": "...", "secret_key": "...", "bucket": "bilinote-assets", "path_style": true, "use_ssl": false}
  },
  "image_bed": {"enabled": true, "source": "minio-img", "public_base_url": "http://img.expii.top:9000/img", "path_prefix": "bilinote"},
  "assets":    {"enabled": true, "source": "minio-assets"}
}
```

- 新建 `app/services/storage_config_manager.py`，模式照抄 `cookie_manager.py`：
  实时读写、无缓存、文件不存在时返回空配置。
- `image_bed.enabled` / `assets.enabled` 的判定必须同时校验所引用 source 存在，
  引用悬空视为未启用（log warning）。

### 2. S3 客户端封装 `app/services/object_storage.py`

- 依赖 `minio`（requirements.txt 加 pin 版本）。
- 按 source 名构造 client 的工厂函数；封装：`put_file(source, key, filepath, content_type)`、
  `get_presigned_url(source, key, expires)`、`delete_object(source, key)`、
  `stat_object`、`list_prefix_stats(source, prefix)`（返回对象数+总字节，供 T5）。
- 所有方法异常不外抛裸 SDK 错误——包一层带 source 名与 key 的日志后 raise 自定义
  `ObjectStorageError`，调用方决定降级。

### 3. 源管理 API（`app/routers/config.py` 或新 router `storage.py`）

- `GET /api/storage/config`：返回配置（**secret_key 打码**为 `••••` + 尾 4 位）。
- `POST /api/storage/source`：新建/更新源（传全量字段；更新时 secret 传打码值则保留旧值）。
- `DELETE /api/storage/source/{name}`：删除源；被功能引用时返回 400 与提示。
- `POST /api/storage/feature`：更新 image_bed / assets 功能绑定与设置。
- `POST /api/storage/test/{name}`：测试连接——PUT 1 字节探针 `\_probe/{uuid}` → GET → DELETE，
  返回三步结果；若该源被 image_bed 引用，额外匿名 GET `public_base_url` 下的探针验证公开可读。

## 验收标准

1. 单测：config manager 读写/悬空引用判定/secret 打码；object_storage 对 mock 端点的错误包装。
2. 真实 MinIO 集成（用用户提供的 key）：`POST /api/storage/test/minio-img` 三步全过；
   对错误 secret 的源返回明确失败信息（贴两次响应）。
3. `GET /api/storage/config` 响应中不出现明文 secret（贴响应）。
4. 全量 pytest 通过。
