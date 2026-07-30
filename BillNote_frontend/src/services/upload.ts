import type { AxiosProgressEvent } from 'axios'
import request from '@/utils/request' // 你项目里封装好的axios或者fetch

export const uploadFile = (
  formData: FormData,
  onUploadProgress?: (event: AxiosProgressEvent) => void,
) => {
  return request.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    // 本地视频可能很大；不要继承全局 API 请求的 10 秒超时。
    timeout: 0,
    onUploadProgress,
  })
}
