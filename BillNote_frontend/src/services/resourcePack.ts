import request from '@/utils/request'

export type ResourceKind = 'video' | 'audio' | 'subtitle' | 'transcript' | 'images'

export interface ResourceItem {
  kind: ResourceKind
  archived: boolean
  local: boolean
  size: number
  key?: string | null
  count?: number
  keys?: string[]
  languages?: string[]
  archive_status?: {
    state: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
    error?: string
    updated_at: string
  }
}

export interface ResourcePack {
  platform: string
  video_id: string
  items: ResourceItem[]
}

export interface ResourceArchivePayload {
  platform: string
  video_id: string
  task_id?: string
  video_url?: string
  archive_video?: boolean
}

export const getResourcePack = (platform: string, videoId: string): Promise<ResourcePack> =>
  request.get(`/resource_pack/${encodeURIComponent(platform)}/${encodeURIComponent(videoId)}`, {
    suppressToast: true,
  })

export const presignResource = (
  key: string
): Promise<{ key: string; url: string; expires_in: number }> =>
  request.get('/resource_pack/presign', {
    params: { key },
    suppressToast: true,
  })

export const deleteResource = (key: string): Promise<{ key: string }> =>
  request.delete('/resource_pack/object', {
    params: { key },
    suppressToast: true,
  })

export const archiveResource = (
  payload: ResourceArchivePayload
): Promise<{ task_id: string; queued: boolean }> =>
  request.post('/resource_pack/archive', payload, { suppressToast: true })

export const subtitleVttUrl = (platform: string, videoId: string, lang: string): string => {
  const apiBase = String(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
  return `${apiBase}/resource_pack/subtitle_vtt/${encodeURIComponent(platform)}/${encodeURIComponent(videoId)}/${encodeURIComponent(lang)}`
}
