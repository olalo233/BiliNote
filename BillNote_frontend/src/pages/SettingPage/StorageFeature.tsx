import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Archive, CheckCircle2, Database, Image as ImageIcon, Loader2, RefreshCw, Save, XCircle } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
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
  StorageConfig,
  StorageFeature as StorageFeatureName,
  StorageSource,
  StorageTestResult,
  StorageUsage,
  testStorageSource,
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

const sourceTypeLabels: Record<StorageSource['type'], string> = {
  minio: 'MinIO',
  s3: 'S3',
}

function featurePath(feature: StorageFeatureName) {
  return feature === 'image_bed' ? '/settings/image-bed' : '/settings/assets'
}

function decodeSourceName(value: string | undefined) {
  if (!value) return ''
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
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
            启用功能并绑定存储供应商后显示用量
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
                  视频 {usage.details.video.object_count} · {formatSize(usage.details.video.total_size)}
                </Badge>
                <Badge variant="secondary">
                  音频 {usage.details.audio.object_count} · {formatSize(usage.details.audio.total_size)}
                </Badge>
                <Badge variant="secondary">
                  字幕/转写 {usage.details.text.object_count} · {formatSize(usage.details.text.total_size)}
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
  const { sourceName: sourceNameParam } = useParams()
  const sourceName = decodeSourceName(sourceNameParam)
  const metadata = featureLabels[feature]
  const basePath = featurePath(feature)
  const [config, setConfig] = useState<StorageConfig | null>(null)
  const [featureForm, setFeatureForm] = useState<FeatureForm>({
    enabled: false,
    source: sourceName,
    public_base_url: '',
    path_prefix: '',
  })
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
      const nextFeature = nextConfig[feature]
      const selectedSource = sourceName || nextFeature.source
      setConfig(nextConfig)
      setFeatureForm({
        enabled: nextFeature.enabled && nextFeature.source === selectedSource,
        source: selectedSource,
        public_base_url: feature === 'image_bed' ? nextFeature.public_base_url : '',
        path_prefix: feature === 'image_bed' ? nextFeature.path_prefix : '',
      })
    } catch {
      toast.error('对象存储配置加载失败')
    } finally {
      setLoading(false)
    }
  }, [feature, sourceName])

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

  const source = config?.sources[sourceName]

  const handleSaveFeature = async () => {
    if (!featureForm.source) {
      toast.error('当前供应商不存在，请返回列表重新选择')
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
      toast.error('当前供应商不存在，请返回列表重新选择')
      return
    }
    setTesting(true)
    try {
      setTestResult(
        await testStorageSource(
          featureForm.source,
          feature === 'image_bed' ? featureForm.path_prefix : ''
        )
      )
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
            <Link to={basePath} className="mb-4 inline-flex items-center text-sm text-blue-600 hover:underline">
              <ArrowLeft className="mr-1 h-4 w-4" />
              返回{metadata.title}供应商列表
            </Link>
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
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Database className="h-5 w-5" />
              当前供应商
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-muted-foreground">加载中…</div>
            ) : source ? (
              <div className="grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <span className="text-muted-foreground">名称：</span>
                  <span className="font-medium">{sourceName}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">类型：</span>
                  <span className="font-medium">{sourceTypeLabels[source.type] || source.type}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Endpoint：</span>
                  <span className="font-medium">{source.endpoint}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">桶：</span>
                  <span className="font-medium">{source.bucket}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Secret key：</span>
                  <span className="font-medium">{source.secret_key || '未设置'}</span>
                </div>
              </div>
            ) : (
              <div className="text-sm text-red-600">供应商不存在，请返回左侧列表重新选择。</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">功能设置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="flex items-center gap-3 text-sm font-medium">
              <Switch
                checked={featureForm.enabled}
                onCheckedChange={enabled => setFeatureForm(form => ({ ...form, enabled }))}
                disabled={!source}
              />
              启用{metadata.title}
            </label>

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
                disabled={testing || !source}
                variant="outline"
              >
                {testing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                测试连接
              </Button>
              <Button onClick={() => void handleSaveFeature()} disabled={saving || loading || !source}>
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
