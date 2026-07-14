# T3 — 存储设置补「删除供应商」按钮

## 背景（已定位，纯前端补按钮）

后端 `DELETE /api/storage/source/{name}` **已存在**（`storage.py`，被功能引用时返回 400 提示），
前端 service `deleteStorageSource`（`services/storage.ts`）**也已存在**——只是
`StorageSources.tsx` 里**没有接删除按钮**。执行者当初铺好了管道没接水龙头。

## 需求

- `BillNote_frontend/src/pages/SettingPage/StorageSources.tsx`：源列表每项加删除按钮
  （trash 图标，风格跟随现有列表项/shadcn）。
- 点击 → 二次确认 → 调 `deleteStorageSource(name)`：
  - 成功：从列表移除 + toast「已删除」；若删的是当前选中源，清空选中态；
  - 后端返回 400（被 image_bed/assets 引用中）：toast 显示后端返回的提示，不移除。
- 与「新建源」入口视觉协调；被引用的源可考虑禁用删除按钮并给 tooltip 说明（可选优化）。

## 验收标准

1. `pnpm dev` 实操：新建一个未被任何功能引用的源 → 删除成功、列表移除、刷新后确实没了（截图序列）。
2. 把某源绑定到 image_bed 功能后尝试删除 → 前端弹出后端的"被引用"提示、源仍在（截图 + network 响应）。
3. `pnpm lint`（改动文件无新增 error）+ `pnpm build`。
