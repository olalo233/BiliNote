import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Archive,
  CheckCircle2,
  Database,
  Image as ImageIcon,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Server,
  Trash2,
  XCircle,
} from 'lucide-react'
import { toast } from 'react-hot-toast'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  getStorageConfig,
  getStorageUsage,
  saveStorageFeature,
  saveStorageSource,
  testStorageSource,
  deleteStorageSource,
  StorageConfig,
  StorageFeature as StorageFeatureName,
  StorageTestResult,
  StorageUsage,
} from '@/services/storage'

interface StorageFeatureProps {
  feature: StorageFeatureName
}

interface FeatureForm {
  enabled: boolean
  source: string
  public_base_url: string
  path_prefix: string
}

interface SourceDraft {
  name: string
  endpoint: string
  access_key: string
  secret_key: string
  bucket: string
  path_style: boolean
  use_ssl: boolean
}

const emptySource: SourceDraft = {
  name: '',
  endpoint: '',
  access_key: '',
  secret_key: '',
  bucket: '',
  path_style: true,
  use_ssl: false,
}

const featureLabels: Record<StorageFeatureName, { title: string; description: string }> = {
  image_bed: {
    title: '图床',
    description: '把笔记截图上传到可公开访问的对象存储，并替换 Markdown 图片地址。',
  },
  assets: {
    title: '资产',
    description: '归档转写、字幕、音频和按次选择的原始视频，供资源包恢复使用。',
  },
}

const testStepLabels: Record<string, string> = {
  put: '上传测试对象',
  get: '读取测试对象',
  public_get: '公网读取',
  delete: '删除测试对象',
}

function formatSize(size: number) {
  if (!size) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function UsageCard({
  usage,
  loading,
  onRefresh,
}: {
  usage: StorageUsage | null
  loading: boolean
  onRefresh: () => void
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-lg">存储用量</CardTitle>
          <p className="text-muted-foreground mt-1 text-sm">与对象存储实时列表汇总一致</p>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
          {loading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          刷新
        </Button>
      </CardHeader>
      <CardContent>
        {!usage ? (
          <div className="text-muted-foreground rounded-md border border-dashed p-6 text-center text-sm">
            启用功能并绑定存储源后显示用量
          </div>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-md bg-slate-50 p-4">
                <div className="text-muted-foreground text-xs">对象数</div>
                <div className="mt-1 text-2xl font-semibold">{usage.object_count}</div>
              </div>
              <div className="rounded-md bg-slate-50 p-4">
                <div className="text-muted-foreground text-xs">总大小</div>
                <div className="mt-1 text-2xl font-semibold">{formatSize(usage.total_size)}</div>
              </div>
              <div className="rounded-md bg-slate-50 p-4">
                <div className="text-muted-foreground text-xs">最近上传</div>
                <div className="mt-1 text-sm font-medium">
                  {usage.latest_upload
                    ? new Date(usage.latest_upload).toLocaleString('zh-CN')
                    : '暂无'}
                </div>
              </div>
            </div>
            {usage.details && (
              <div className="mt-4 flex flex-wrap gap-2 text-sm">
                <Badge variant="secondary">
                  视频 {usage.details.video.object_count} ·{' '}
                  {formatSize(usage.details.video.total_size)}
                </Badge>
                <Badge variant="secondary">
                  音频 {usage.details.audio.object_count} ·{' '}
                  {formatSize(usage.details.audio.total_size)}
                </Badge>
                <Badge variant="secondary">
                  字幕/转写 {usage.details.text.object_count} ·{' '}
                  {formatSize(usage.details.text.total_size)}
                </Badge>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function TestResult({ result }: { result: StorageTestResult | null }) {
  if (!result) return null
  const steps = Object.entries(result).filter(([, step]) => step)
  return (
    <div className="rounded-md border bg-slate-50 p-4">
      <div className="mb-2 text-sm font-medium">连接测试结果</div>
      <div className="grid gap-2 sm:grid-cols-2">
        {steps.map(([name, step]) => (
          <div key={name} className="flex items-center gap-2 text-sm">
            {step.ok ? (
              <CheckCircle2 className="h-4 w-4 text-green-600" />
            ) : (
              <XCircle className="h-4 w-4 text-red-600" />
            )}
            <span>{testStepLabels[name] || name}</span>
            {!step.ok && <span className="text-xs text-red-600">{step.message || '失败'}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function StorageFeature({ feature }: StorageFeatureProps) {
  const metadata = featureLabels[feature]
  const [config, setConfig] = useState<StorageConfig | null>(null)
  const [featureForm, setFeatureForm] = useState<FeatureForm>({
    enabled: false,
    source: '',
    public_base_url: '',
    path_prefix: '',
  })
  const [sourceDraft, setSourceDraft] = useState<SourceDraft>(emptySource)
  const [showSourceForm, setShowSourceForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<StorageTestResult | null>(null)
  const [usage, setUsage] = useState<StorageUsage | null>(null)
  const [usageLoading, setUsageLoading] = useState(false)

  const loadConfig = useCallback(async () => {
    setLoading(true)
    try {
      const nextConfig = await getStorageConfig()
      setConfig(nextConfig)
      const nextFeature = nextConfig[feature]
      setFeatureForm({
        enabled: nextFeature.enabled,
        source: nextFeature.source,
        public_base_url: feature === 'image_bed' ? nextFeature.public_base_url : '',
        path_prefix: feature === 'image_bed' ? nextFeature.path_prefix : '',
      })
    } catch {
      toast.error('对象存储配置加载失败')
    } finally {
      setLoading(false)
    }
  }, [feature])

  const loadUsage = useCallback(
    async (refresh = false) => {
      if (!featureForm.enabled || !featureForm.source) {
        setUsage(null)
        return
      }
      setUsageLoading(true)
      try {
        setUsage(await getStorageUsage(feature, refresh))
      } catch {
        setUsage(null)
      } finally {
        setUsageLoading(false)
      }
    },
    [feature, featureForm.enabled, featureForm.source]
  )

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  useEffect(() => {
    void loadUsage()
  }, [loadUsage])

  const sourceEntries = useMemo(() => Object.entries(config?.sources || {}), [config])

  const handleCreateSource = async () => {
    if (!sourceDraft.name || !sourceDraft.endpoint || !sourceDraft.bucket) {
      toast.error('请填写源名称、Endpoint 和桶名')
      return
    }
    setSaving(true)
    try {
      await saveStorageSource({ type: 's3', ...sourceDraft })
      toast.success('存储源已保存')
      setSourceDraft(emptySource)
      setShowSourceForm(false)
      await loadConfig()
    } catch {
      toast.error('存储源保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteSource = async (name: string) => {
    if (!window.confirm(`确认删除存储源「${name}」吗？`)) return
    try {
      await deleteStorageSource(name)
      toast.success('存储源已删除')
      await loadConfig()
    } catch {
      toast.error('存储源删除失败，请确认它没有被功能引用')
    }
  }

  const handleSaveFeature = async () => {
    if (featureForm.enabled && !featureForm.source) {
      toast.error('启用功能前请选择存储源')
      return
    }
    setSaving(true)
    try {
      await saveStorageFeature({
        feature,
        enabled: featureForm.enabled,
        source: featureForm.source,
        ...(feature === 'image_bed'
          ? {
              public_base_url: featureForm.public_base_url,
              path_prefix: featureForm.path_prefix,
            }
          : {}),
      })
      toast.success(`${metadata.title}配置已保存`)
      await loadConfig()
      await loadUsage(true)
    } catch {
      toast.error(`${metadata.title}配置保存失败`)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!featureForm.source) {
      toast.error('请先选择存储源')
      return
    }
    setTesting(true)
    try {
      setTestResult(await testStorageSource(featureForm.source))
    } catch {
      setTestResult(null)
      toast.error('连接测试失败')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-white">
      <div className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-3 flex items-center gap-2 text-sm">
              <Link
                className={`rounded-md px-3 py-1.5 ${feature === 'image_bed' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}
                to="/settings/image-bed"
              >
                图床
              </Link>
              <Link
                className={`rounded-md px-3 py-1.5 ${feature === 'assets' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}
                to="/settings/assets"
              >
                资产
              </Link>
            </div>
            <div className="flex items-center gap-3">
              {feature === 'image_bed' ? (
                <ImageIcon className="h-7 w-7 text-blue-600" />
              ) : (
                <Archive className="h-7 w-7 text-violet-600" />
              )}
              <div>
                <h1 className="text-2xl font-bold">{metadata.title}</h1>
                <p className="text-muted-foreground mt-1 text-sm">{metadata.description}</p>
              </div>
            </div>
          </div>
          <Badge variant={featureForm.enabled ? 'default' : 'secondary'}>
            {featureForm.enabled ? '已启用' : '未启用'}
          </Badge>
        </div>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Server className="h-5 w-5" />
              存储源
            </CardTitle>
            <Button variant="outline" size="sm" onClick={() => setShowSourceForm(value => !value)}>
              <Plus className="mr-2 h-4 w-4" />
              新建源
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
              <label className="space-y-2 text-sm font-medium">
                <span>当前绑定源</span>
                <select
                  className="border-input bg-background flex h-9 w-full rounded-md border px-3 text-sm"
                  value={featureForm.source}
                  onChange={event =>
                    setFeatureForm(form => ({ ...form, source: event.target.value }))
                  }
                  disabled={loading}
                >
                  <option value="">请选择存储源</option>
                  {sourceEntries.map(([name]) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex h-9 items-center gap-3 text-sm font-medium">
                <Switch
                  checked={featureForm.enabled}
                  onCheckedChange={enabled => setFeatureForm(form => ({ ...form, enabled }))}
                />
                启用{metadata.title}
              </label>
            </div>

            {sourceEntries.length > 0 && (
              <div className="divide-y rounded-md border">
                {sourceEntries.map(([name, source]) => (
                  <div key={name} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
                    <Database className="text-muted-foreground h-4 w-4" />
                    <span className="font-medium">{name}</span>
                    <span className="text-muted-foreground">
                      {source.endpoint} / {source.bucket}
                    </span>
                    <span className="text-muted-foreground ml-auto">
                      密钥：{source.secret_key || '未设置'}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600"
                      onClick={() => void handleDeleteSource(name)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            {showSourceForm && (
              <div className="grid gap-3 rounded-md border bg-slate-50 p-4 md:grid-cols-2">
                <Input
                  placeholder="源名称"
                  value={sourceDraft.name}
                  onChange={event =>
                    setSourceDraft(form => ({ ...form, name: event.target.value }))
                  }
                />
                <Input
                  placeholder="Endpoint，例如 img.example:9000"
                  value={sourceDraft.endpoint}
                  onChange={event =>
                    setSourceDraft(form => ({ ...form, endpoint: event.target.value }))
                  }
                />
                <Input
                  placeholder="Access key"
                  value={sourceDraft.access_key}
                  onChange={event =>
                    setSourceDraft(form => ({ ...form, access_key: event.target.value }))
                  }
                />
                <Input
                  type="password"
                  placeholder="Secret key"
                  value={sourceDraft.secret_key}
                  onChange={event =>
                    setSourceDraft(form => ({ ...form, secret_key: event.target.value }))
                  }
                />
                <Input
                  placeholder="桶名"
                  value={sourceDraft.bucket}
                  onChange={event =>
                    setSourceDraft(form => ({ ...form, bucket: event.target.value }))
                  }
                />
                <div className="flex items-center gap-4 text-sm">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={sourceDraft.path_style}
                      onChange={event =>
                        setSourceDraft(form => ({ ...form, path_style: event.target.checked }))
                      }
                    />
                    Path style
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={sourceDraft.use_ssl}
                      onChange={event =>
                        setSourceDraft(form => ({ ...form, use_ssl: event.target.checked }))
                      }
                    />
                    HTTPS
                  </label>
                  <Button
                    className="ml-auto"
                    size="sm"
                    onClick={() => void handleCreateSource()}
                    disabled={saving}
                  >
                    <Save className="mr-2 h-4 w-4" />
                    保存源
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">功能设置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {feature === 'image_bed' ? (
              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2 text-sm font-medium">
                  <span>公网基础 URL</span>
                  <Input
                    placeholder="http://img.example:9000/img"
                    value={featureForm.public_base_url}
                    onChange={event =>
                      setFeatureForm(form => ({ ...form, public_base_url: event.target.value }))
                    }
                  />
                </label>
                <label className="space-y-2 text-sm font-medium">
                  <span>对象 key 前缀</span>
                  <Input
                    placeholder="bilinote"
                    value={featureForm.path_prefix}
                    onChange={event =>
                      setFeatureForm(form => ({ ...form, path_prefix: event.target.value }))
                    }
                  />
                </label>
              </div>
            ) : (
              <p className="text-muted-foreground rounded-md bg-slate-50 p-4 text-sm">
                资产功能启用后，笔记成功保存时会自动异步归档转写、字幕和音频；原始视频由每次生成请求单独选择。
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={() => void handleTest()}
                disabled={testing || !featureForm.source}
                variant="outline"
              >
                {testing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                测试连接
              </Button>
              <Button onClick={() => void handleSaveFeature()} disabled={saving || loading}>
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                保存
              </Button>
            </div>
            <TestResult result={testResult} />
          </CardContent>
        </Card>

        <UsageCard usage={usage} loading={usageLoading} onRefresh={() => void loadUsage(true)} />
      </div>
    </div>
  )
}
