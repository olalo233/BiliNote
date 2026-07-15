import request from '@/utils/request'

export interface PromptTemplate {
  name: string
  content: string
}

export const getPrompts = (): Promise<PromptTemplate[]> =>
  request.get('/prompts', { suppressToast: true })

export const savePrompt = (prompt: PromptTemplate): Promise<PromptTemplate> =>
  request.post('/prompts', prompt, { suppressToast: true })

export const deletePrompt = (name: string): Promise<void> =>
  request.delete(`/prompts/${encodeURIComponent(name)}`, { suppressToast: true })
