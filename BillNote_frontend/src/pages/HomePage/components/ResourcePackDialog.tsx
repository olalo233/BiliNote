import { useCallback, useEffect, useMemo, useState } from 'react'
import { Archive, Download, Eye, Loader2, Play, RefreshCw, Trash2, Upload } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { getStorageConfig } from '@/services/storage'
import {
  ResourceItem,
  ResourceKind,
  archiveResource,
  deleteResource,
  getResourcePack,
  presignResource,
  subtitleVttUrl,
} from '@/services/resourcePack'

interface ResourcePackDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  platform: string
  videoId: string
  taskId: string
  videoUrl?: string
}

const labels: Record<ResourceKind, string> = {
  video: '原始视频',
  audio: '音频',
  subtitle: '字幕',
  transcript: '转写结果',
  images: '笔记截图',
}

function formatSize(size: number) {
  if (!size) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function ResourcePackDialog({
  open,
  onOpenChange,
  platform,
  videoId,
  taskId,
  videoUrl,
}: ResourcePackDialogProps) {
  const [items, setItems] = useState<ResourceItem[]>([])
  const [loading, setLoading] = useState(false)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [playUrl, setPlayUrl] = useState<string | null>(null)
  const [playLanguages, setPlayLanguages] = useState<string[]>([])
  const [imageBaseUrl, setImageBaseUrl] = useState('')

  const loadPack = useCallback(async () => {
    if (!platform || !videoId) return
    setLoading(true)
    try {
      const [pack, storage] = await Promise.all([
        getResourcePack(platform, videoId),
        getStorageConfig(),
      ])
      setItems(pack.items)
      setImageBaseUrl(storage.image_bed?.public_base_url?.replace(/\/$/, '') || '')
    } catch {
      toast.error('资源包加载失败')
    } finally {
      setLoading(false)
    }
  }, [platform, videoId])

  useEffect(() => {
    if (!open) return
    setPlayUrl(null)
    setPlayLanguages([])
    void loadPack()
  }, [open, loadPack])

  const itemsByKind = useMemo(() => new Map(items.map(item => [item.kind, item])), [items])

  const hasRunningArchive = items.some(item =>
    item.archive_status?.state === 'pending' || item.archive_status?.state === 'running'
  )

  useEffect(() => {
    if (!open || !hasRunningArchive) return
    const timer = window.setTimeout(() => void loadPack(), 5000)
    return () => window.clearTimeout(timer)
  }, [open, hasRunningArchive, loadPack])

  const getUrl = async (key: string, forPlayback = false, languages: string[] = []) => {
    setBusyKey(key)
    try {
      const result = await presignResource(key)
      if (forPlayback) {
        setPlayUrl(result.url)
        setPlayLanguages(languages)
      } else {
        window.open(result.url, '_blank', 'noopener,noreferrer')
      }
    } catch {
      toast.error('资产链接获取失败')
    } finally {
      setBusyKey(null)
    }
  }

  const remove = async (item: ResourceItem) => {
    if (!item.key || !window.confirm(`确认删除${labels[item.kind]}的对象存储副本吗？`)) return
    setBusyKey(item.key)
    try {
      await deleteResource(item.key)
      toast.success('已删除对象存储副本')
      await loadPack()
      if (item.kind === 'video') setPlayUrl(null)
    } catch {
      toast.error('删除失败')
    } finally {
      setBusyKey(null)
    }
  }

  const archive = async (item: ResourceItem) => {
    if (!['video', 'audio', 'subtitle', 'transcript'].includes(item.kind)) return
    setBusyKey(item.kind)
    try {
      await archiveResource({
        platform,
        video_id: videoId,
        task_id: taskId,
        video_url: videoUrl,
        archive_video: item.kind === 'video',
      })
      toast.success('已触发归档，稍后刷新状态')
      await new Promise(resolve => window.setTimeout(resolve, 800))
      await loadPack()
    } catch {
      toast.error('归档触发失败')
    } finally {
      setBusyKey(null)
    }
  }

  const renderActions = (item: ResourceItem) => {
    if (item.kind === 'images') {
      return item.archived ? (
        <div className="flex items-center gap-2">
          {imageBaseUrl &&
            item.keys?.slice(0, 3).map(key => (
              <a key={key} href={`${imageBaseUrl}/${key}`} target="_blank" rel="noreferrer">
                <img
                  className="h-8 w-8 rounded object-cover"
                  src={`${imageBaseUrl}/${key}`}
                  alt="笔记截图"
                />
              </a>
            ))}
          <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
            <Eye className="h-3.5 w-3.5" /> {item.count || 0} 张
          </span>
        </div>
      ) : null
    }

    const actions = []
    const archiveState = item.archive_status?.state
    const isArchiving = archiveState === 'pending' || archiveState === 'running'
    const isFailed = archiveState === 'failed'
    if (isFailed) {
      actions.push(
        <Button
          key="retry"
          variant="outline"
          size="sm"
          onClick={() => void archive(item)}
          disabled={busyKey === item.kind}
        >
          {busyKey === item.kind ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="mr-1 h-3.5 w-3.5" />
          )}
          重试
        </Button>
      )
    }
    if (!isArchiving && item.archived && item.key) {
      if (item.kind === 'video') {
        actions.push(
          <Button
            key="play"
            variant="ghost"
            size="sm"
            onClick={() =>
              void getUrl(item.key!, true, itemsByKind.get('subtitle')?.languages || [])
            }
            disabled={busyKey === item.key}
          >
            <Play className="mr-1 h-3.5 w-3.5" />
            播放
          </Button>
        )
      }
      actions.push(
        <Button
          key="download"
          variant="ghost"
          size="sm"
          onClick={() => void getUrl(item.key!)}
          disabled={busyKey === item.key}
        >
          <Download className="mr-1 h-3.5 w-3.5" />
          下载
        </Button>
      )
      if (item.kind === 'video' || item.kind === 'audio') {
        actions.push(
          <Button
            key="delete"
            variant="ghost"
            size="sm"
            className="text-red-600 hover:text-red-700"
            onClick={() => void remove(item)}
            disabled={busyKey === item.key}
          >
            <Trash2 className="mr-1 h-3.5 w-3.5" />
            删除
          </Button>
        )
      }
    } else if (!isArchiving && item.local && (item.kind === 'video' || item.kind === 'audio')) {
      actions.push(
        <Button
          key="upload"
          variant="outline"
          size="sm"
          onClick={() => void archive(item)}
          disabled={busyKey === item.kind}
        >
          {busyKey === item.kind ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Upload className="mr-1 h-3.5 w-3.5" />
          )}
          上传到对象存储
        </Button>
      )
    }
    return actions
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Archive className="h-5 w-5" />
            资源包
          </DialogTitle>
          <DialogDescription>
            {platform} / {videoId}
          </DialogDescription>
        </DialogHeader>

        <div className="flex justify-end">
          <Button variant="ghost" size="sm" onClick={() => void loadPack()} disabled={loading}>
            <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>

        {loading && items.length === 0 ? (
          <div className="text-muted-foreground flex items-center justify-center py-10 text-sm">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            正在读取资源包…
          </div>
        ) : (
          <div className="divide-y rounded-md border">
            {(['video', 'audio', 'subtitle', 'transcript', 'images'] as ResourceKind[]).map(
              kind => {
                const item = itemsByKind.get(kind) || {
                  kind,
                  archived: false,
                  local: false,
                  size: 0,
                }
                const archiveState = item.archive_status?.state
                const archiveError = item.archive_status?.error
                return (
                  <div key={kind} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <div className="min-w-24 font-medium">{labels[kind]}</div>
                    <div className="text-muted-foreground text-sm">
                      {archiveState === 'pending' || archiveState === 'running' ? (
                        <span className="inline-flex items-center gap-1">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          归档中
                        </span>
                      ) : archiveState === 'failed' ? (
                        <span className="text-red-600" title={archiveError}>
                          归档失败{archiveError ? `：${archiveError}` : ''}
                        </span>
                      ) : item.archived
                        ? `已归档 · ${formatSize(item.size)}`
                        : item.local
                          ? '本地可用 · 未归档'
                          : '不可用'}
                      {kind === 'subtitle' && item.count ? ` · ${item.count} 条` : ''}
                      {kind === 'images' && item.count ? ` · ${item.count} 张` : ''}
                    </div>
                    <div className="ml-auto flex flex-wrap items-center gap-1">
                      {renderActions(item)}
                    </div>
                  </div>
                )
              }
            )}
          </div>
        )}

        {playUrl && (
          <div className="space-y-2 rounded-md border bg-slate-50 p-3">
            <div className="text-sm font-medium">原始视频预览</div>
            <video
              className="max-h-80 w-full rounded"
              controls
              crossOrigin="anonymous"
              src={playUrl}
              preload="metadata"
            >
              {playLanguages.map((lang, index) => (
                <track
                  key={lang}
                  kind="subtitles"
                  srcLang={lang}
                  label={lang}
                  src={subtitleVttUrl(platform, videoId, lang)}
                  default={index === 0}
                />
              ))}
            </video>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default ResourcePackDialog
