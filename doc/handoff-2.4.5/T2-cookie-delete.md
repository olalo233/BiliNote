# T2 — Cookie 删除端点 + 前端清除按钮

## 根因（已实证）

- 后端 `backend/app/routers/config.py` 只有 `GET /get_downloader_cookie/{platform}` 和
  `POST /update_downloader_cookie` 两个端点。`CookieConfigManager.delete(platform)`
  （`backend/app/services/cookie_manager.py`）存在但从未暴露成 API。
- 前端 `BillNote_frontend/src/components/Form/DownloaderForm/Form.tsx` 的 zod 校验
  `cookie: z.string().min(10)` 把"保存空值来清除"这条路也堵死了。
- 结果：用户一旦配了 cookie（存于 `backend/config/downloader.json`），从 UI 上永远删不掉。
  本次线上事故中用户误配了 YouTube 登录 cookie（有封号风险），只能进容器手删。

## 改动

### 1. 后端 `app/routers/config.py`

新增删除端点，紧挨现有两个 cookie 端点：

```python
@router.delete("/delete_downloader_cookie/{platform}")
def delete_cookie(platform: str):
    cookie_manager.delete(platform)
    return R.success(msg="Cookie 已删除")
```

说明：`CookieConfigManager.delete` 对不存在的 platform 是幂等 no-op，无需 404 分支。
`CookieConfigManager` 每次调用实时读写 JSON 文件，无缓存，删除即时生效、无需重启。

### 2. 前端

`BillNote_frontend/src/services/downloader.ts` 增加：

```ts
export const deleteDownloaderCookie = async (platform: string) => {
  return await request.delete('/delete_downloader_cookie/' + platform)
}
```

`Form.tsx`（DownloaderForm）：
- 在"保存"按钮旁增加"清除 Cookie"按钮（variant 用 destructive 或 outline，跟现有 shadcn/ui 风格）。
- 点击后调 `deleteDownloaderCookie(id)`，成功则 `form.reset({ cookie: '' })` + `toast.success('Cookie 已清除')`。
- 仅当当前已有 cookie（表单初始值非空）时启用该按钮，避免误导。
- i18n：本组件现有文案是硬编码中文，保持一致即可，不强求接 i18n。

## 验收标准

1. 后端单测或 curl 实测（本地起 backend）：
   - 先 `POST /api/update_downloader_cookie` 写入 `{"platform":"youtube","cookie":"aaaaaaaaaaaa"}`；
   - `GET /api/get_downloader_cookie/youtube` 返回该 cookie；
   - `DELETE /api/delete_downloader_cookie/youtube` 返回成功；
   - 再 `GET` 返回"未找到Cookies"；
   - 重复 `DELETE` 一次仍返回成功（幂等）。
   证据：五次请求的响应体。
2. `backend/config/downloader.json` 中对应 key 确实被移除（贴文件内容）。
3. 前端 `pnpm dev` 起本地页面，设置 → 下载器 → 任一平台：
   - 有 cookie 时"清除"按钮可用，点击后输入框清空、toast 提示、刷新页面后仍为空；
   - 无 cookie 时按钮禁用。
   证据：操作路径描述 + 关键截图（或 DOM 断言）。
4. `pnpm lint` 通过；`pnpm build` 成功。
