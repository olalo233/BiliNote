import { useState } from 'react'
import { ArrowLeft, Loader2, Save } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  saveStorageSource,
  StorageFeature,
  StorageSourcePayload,
} from '@/services/storage'

interface StorageSourceFormProps {
  feature: StorageFeature
}

interface SourceDraft {
  name: string
  type: StorageSourcePayload['type']
  endpoint: string
  access_key: string
  secret_key: string
  bucket: string
  path_style: boolean
  use_ssl: boolean
}

const emptySource: SourceDraft = {
  name: '',
  type: 'minio',
  endpoint: '',
  access_key: '',
  secret_key: '',
  bucket: '',
  path_style: true,
  use_ssl: false,
}

const featureLabels: Record<StorageFeature, string> = {
  image_bed: '图床',
  assets: '资产',
}

function featurePath(feature: StorageFeature) {
  return feature === 'image_bed' ? '/settings/image-bed' : '/settings/assets'
}

export default function StorageSourceForm({ feature }: StorageSourceFormProps) {
  const navigate = useNavigate()
  const [draft, setDraft] = useState<SourceDraft>(emptySource)
  const [saving, setSaving] = useState(false)
  const title = featureLabels[feature]
  const basePath = featurePath(feature)

  const update = <K extends keyof SourceDraft>(key: K, value: SourceDraft[K]) => {
    setDraft(current => ({ ...current, [key]: value }))
  }

  const handleSave = async () => {
    if (!draft.name.trim() || !draft.endpoint.trim() || !draft.bucket.trim()) {
      toast.error('请填写名称、Endpoint 和桶名')
      return
    }
    if (draft.name.includes('/')) {
      toast.error('供应商名称不能包含 /')
      return
    }
    if (!draft.access_key.trim() || !draft.secret_key.trim()) {
      toast.error('请填写 Access key 和 Secret key')
      return
    }

    setSaving(true)
    try {
      await saveStorageSource({
        ...draft,
        name: draft.name.trim(),
        endpoint: draft.endpoint.trim(),
        bucket: draft.bucket.trim(),
        feature,
      })
      toast.success(`${title}供应商已保存`)
      navigate(`${basePath}/${encodeURIComponent(draft.name.trim())}`)
    } catch {
      toast.error(`${title}供应商保存失败`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl space-y-6">
        <Button type="button" variant="ghost" onClick={() => navigate(basePath)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          返回{title}供应商列表
        </Button>
        <div>
          <h1 className="text-2xl font-bold">添加{title}供应商</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            对象存储兼容 MinIO 和 S3。保存后点击左侧供应商进入{title}功能配置。
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>供应商信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="block space-y-2 text-sm font-medium">
              <span>名称</span>
              <Input
                placeholder="例如 minio-img"
                value={draft.name}
                onChange={event => update('name', event.target.value)}
              />
            </label>

            <label className="block space-y-2 text-sm font-medium">
              <span>类型</span>
              <select
                className="border-input bg-background flex h-9 w-full rounded-md border px-3 text-sm"
                value={draft.type}
                onChange={event => update('type', event.target.value as SourceDraft['type'])}
              >
                <option value="minio">MinIO</option>
                <option value="s3">S3</option>
              </select>
            </label>

            <label className="block space-y-2 text-sm font-medium">
              <span>Endpoint</span>
              <Input
                placeholder="例如 img.example.com:9000"
                value={draft.endpoint}
                onChange={event => update('endpoint', event.target.value)}
              />
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-2 text-sm font-medium">
                <span>Access key</span>
                <Input
                  value={draft.access_key}
                  onChange={event => update('access_key', event.target.value)}
                />
              </label>
              <label className="block space-y-2 text-sm font-medium">
                <span>Secret key</span>
                <Input
                  type="password"
                  value={draft.secret_key}
                  onChange={event => update('secret_key', event.target.value)}
                />
              </label>
            </div>

            <label className="block space-y-2 text-sm font-medium">
              <span>桶名</span>
              <Input
                placeholder={feature === 'image_bed' ? 'img' : 'bilinote-assets'}
                value={draft.bucket}
                onChange={event => update('bucket', event.target.value)}
              />
            </label>

            <div className="flex flex-wrap gap-5 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={draft.path_style}
                  onChange={event => update('path_style', event.target.checked)}
                />
                Path style
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={draft.use_ssl}
                  onChange={event => update('use_ssl', event.target.checked)}
                />
                HTTPS
              </label>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => navigate(basePath)}>
                取消
              </Button>
              <Button type="button" onClick={() => void handleSave()} disabled={saving}>
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                保存供应商
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
