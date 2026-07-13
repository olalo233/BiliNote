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

export const getStorageConfig = async (): Promise<StorageConfig> =>
  request.get('/storage/config', { suppressToast: true })
