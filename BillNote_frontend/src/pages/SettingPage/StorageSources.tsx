import { useCallback, useEffect, useMemo, useState } from 'react'
import { Database, Plus } from 'lucide-react'
import { useLocation, useNavigate, useParams, Outlet } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import {
  getStorageConfig,
  saveStorageFeature,
  StorageConfig,
  StorageFeature,
  StorageSource,
} from '@/services/storage'

interface StorageSourcesProps {
  feature: StorageFeature
}

const metadata: Record<StorageFeature, { title: string; listTitle: string; description: string }> = {
  image_bed: {
    title: '图床',
    listTitle: '图床供应商列表',
    description: '选择一个对象存储供应商，将笔记截图上传到可公开访问的图床。',
  },
  assets: {
    title: '资产',
    listTitle: '资产存储供应商列表',
    description: '选择一个对象存储供应商，归档笔记生成所需的音频、字幕和视频资产。',
  },
}

const typeLabels: Record<StorageSource['type'], string> = {
  minio: 'MinIO',
  s3: 'S3',
}

function featurePath(feature: StorageFeature) {
  return feature === 'image_bed' ? '/settings/image-bed' : '/settings/assets'
}

export default function StorageSources({ feature }: StorageSourcesProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { sourceName } = useParams()
  const [config, setConfig] = useState<StorageConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState<string | null>(null)
  const page = metadata[feature]
  const basePath = featurePath(feature)

  const loadConfig = useCallback(async () => {
    setLoading(true)
    try {
      setConfig(await getStorageConfig())
    } catch {
      toast.error('对象存储供应商加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig, location.pathname])

  const configuredSource = config?.[feature]?.source || ''
  const sourceEntries = useMemo(() => {
    const entries = Object.entries(config?.sources || {})
    return entries.filter(([name, source]) => {
      // 新配置以 feature 标记归属；兼容旧配置时只把当前功能已绑定的源展示在本页，
      // 避免图床页和资产页互相展示对方的历史源。
      return source.feature === feature || name === configuredSource || name === sourceName
    })
  }, [config, configuredSource, feature, sourceName])

  const handleToggle = async (name: string, enabled: boolean) => {
    const current = config?.[feature]
    if (!current) return
    setToggling(name)
    try {
      await saveStorageFeature({
        feature,
        enabled,
        source: enabled ? name : current.source,
        ...(feature === 'image_bed'
          ? {
              public_base_url: current.public_base_url,
              path_prefix: current.path_prefix,
            }
          : {}),
      })
      await loadConfig()
      toast.success(enabled ? `${page.title}已启用` : `${page.title}已停用`)
    } catch {
      toast.error(`${page.title}开关保存失败`)
    } finally {
      setToggling(null)
    }
  }

  return (
    <div className="flex h-full min-h-0 bg-white">
      <div className="flex-1/5 min-h-0 overflow-y-auto border-r border-neutral-200 p-2">
        <div className="flex flex-col gap-2">
          <Button type="button" onClick={() => navigate(`${basePath}/new`)} className="w-full">
            <Plus className="mr-2 h-4 w-4" />
            添加{page.title}供应商
          </Button>
          <div className="text-sm font-light">{page.listTitle}</div>
          <div>
            {loading ? (
              <div className="p-3 text-sm text-muted-foreground">加载中…</div>
            ) : sourceEntries.length === 0 ? (
              <div className="rounded border border-dashed p-3 text-sm text-muted-foreground">
                还没有{page.title}供应商，请先添加。
              </div>
            ) : (
              sourceEntries.map(([name, source]) => {
                const active = sourceName === name
                const enabled = config?.[feature]?.enabled && config?.[feature]?.source === name
                return (
                  <div
                    key={name}
                    className={`flex min-h-14 cursor-pointer items-center justify-between rounded border border-[#f3f3f3] p-2 ${active ? 'bg-[#F0F0F0] font-semibold text-blue-600' : ''}`}
                    onClick={() => navigate(`${basePath}/${encodeURIComponent(name)}`)}
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <Database className="h-6 w-6 shrink-0" />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold">{name}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          {typeLabels[source.type] || source.type} · {source.bucket}
                        </div>
                      </div>
                    </div>
                    <div onClick={event => event.stopPropagation()}>
                      <Switch
                        checked={Boolean(enabled)}
                        disabled={toggling === name}
                        onCheckedChange={checked => void handleToggle(name, checked)}
                        aria-label={`启用${name}`}
                      />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>
      <div className="flex-4/5 min-h-0 overflow-y-auto">
        {sourceName || location.pathname.endsWith('/new') ? (
          <Outlet />
        ) : (
          <div className="flex h-full items-center justify-center p-8 text-center text-muted-foreground">
            <div>
              <Database className="mx-auto mb-3 h-10 w-10" />
              <p className="font-medium">{page.title}</p>
              <p className="mt-1 text-sm">{page.description}</p>
              <p className="mt-3 text-sm">从左侧选择供应商，或先添加一个供应商。</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
