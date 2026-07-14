import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button.tsx'
import { HomePage } from '@/pages/HomePage/Home.tsx'
import { get_task_status } from '@/services/note.ts'
import { useTaskStore, type HydrateTaskPayload } from '@/store/taskStore'

type LoadState = 'loading' | 'ready' | 'missing'

export default function NotePage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const setCurrentTask = useTaskStore(state => state.setCurrentTask)
  const hydrateTask = useTaskStore(state => state.hydrateTask)

  useEffect(() => {
    if (!taskId) {
      setLoadState('missing')
      return
    }

    let cancelled = false
    const localTask = useTaskStore.getState().tasks.find(task => task.id === taskId)
    if (localTask) {
      setCurrentTask(taskId)
      setLoadState('ready')
      return () => {
        cancelled = true
      }
    }

    setLoadState('loading')
    get_task_status(taskId)
      .then(payload => {
        if (cancelled) return
        if (!payload?.status) throw new Error('笔记状态无效')
        hydrateTask(taskId, payload as HydrateTaskPayload)
        setCurrentTask(taskId)
        setLoadState('ready')
      })
      .catch(error => {
        if (cancelled) return
        console.warn('深链笔记加载失败：', error)
        setLoadState('missing')
      })

    return () => {
      cancelled = true
    }
  }, [hydrateTask, setCurrentTask, taskId])

  if (loadState === 'loading') {
    return <div className="flex h-screen items-center justify-center text-muted-foreground">正在加载笔记…</div>
  }

  if (loadState === 'missing') {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 text-center">
        <h1 className="text-xl font-semibold">笔记不存在或已删除</h1>
        <p className="text-sm text-muted-foreground">请返回首页重新生成或打开其他笔记。</p>
        <Button type="button" onClick={() => navigate('/')}>回到首页</Button>
      </div>
    )
  }

  return <HomePage />
}
