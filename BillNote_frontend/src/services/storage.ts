import request from '@/utils/request'

export interface StorageSource {
  type: 's3'
  endpoint: string
  access_key: string
  secret_key: string
  bucket: string
  path_style: boolean
  use_ssl: boolean
}

export interface StorageConfig {
  sources: Record<string, StorageSource>
  image_bed: {
    enabled: boolean
    source: string
    public_base_url: string
    path_prefix: string
  }
  assets: {
    enabled: boolean
    source: string
  }
}

export type StorageFeature = 'image_bed' | 'assets'

export interface StorageSourcePayload {
  name: string
  type: 's3'
  endpoint: string
  access_key: string
  secret_key: string
  bucket: string
  path_style: boolean
  use_ssl: boolean
}

export interface StorageFeaturePayload {
  feature: StorageFeature
  enabled: boolean
  source: string
  public_base_url?: string
  path_prefix?: string
}

export interface StorageTestStep {
  ok: boolean
  key?: string
  status_code?: number
  content_type?: string
  message?: string
  cleanup?: boolean
}

export interface StorageTestResult {
  put: StorageTestStep
  get: StorageTestStep
  delete: StorageTestStep
  public_get?: StorageTestStep
}

export interface StorageUsageMetric {
  object_count: number
  total_size: number
  latest_upload: string | null
}

export interface StorageUsage extends StorageUsageMetric {
  feature: StorageFeature
  source: string
  prefix: string
  details?: Record<'video' | 'audio' | 'text', StorageUsageMetric>
}

export const getStorageConfig = async (): Promise<StorageConfig> =>
  request.get('/storage/config', { suppressToast: true })

export const saveStorageSource = (payload: StorageSourcePayload) =>
  request.post('/storage/source', payload, { suppressToast: true })

export const deleteStorageSource = (name: string) =>
  request.delete(`/storage/source/${encodeURIComponent(name)}`, { suppressToast: true })

export const saveStorageFeature = (payload: StorageFeaturePayload) =>
  request.post('/storage/feature', payload, { suppressToast: true })

export const testStorageSource = (name: string): Promise<StorageTestResult> =>
  request.post(`/storage/test/${encodeURIComponent(name)}`, undefined, { suppressToast: true })

export const getStorageUsage = (feature: StorageFeature, refresh = false): Promise<StorageUsage> =>
  request.get(`/storage/usage/${feature}`, {
    params: refresh ? { refresh: 1 } : undefined,
    suppressToast: true,
  })
