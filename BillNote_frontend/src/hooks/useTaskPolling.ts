import { useEffect, useRef } from 'react'
import { useTaskStore } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'
import toast from 'react-hot-toast'

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)

  const tasksRef = useRef(tasks)

  // 每次 tasks 更新，把最新的 tasks 同步进去
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  useEffect(() => {
    const timer = setInterval(async () => {
      const pendingTasks = tasksRef.current.filter(
        task => task.status != 'SUCCESS' && task.status != 'FAILED'
      )

      // 无活跃任务时跳过轮询
      if (pendingTasks.length === 0) return

      for (const task of pendingTasks) {
        try {
          const res = await get_task_status(task.id)
          const { status } = res

          if (status && status !== task.status) {
            if (status === 'SUCCESS') {
              const { markdown, transcript, audio_meta } = res.result
              toast.success('笔记生成成功')
              updateTaskContent(task.id, {
                status,
                markdown,
                transcript,
                audioMeta: audio_meta,
              })
            } else if (status === 'FAILED') {
              const message = String(res.message || '任务失败')
              updateTaskContent(task.id, {
                status,
                error: message,
              })
              toast.error(`笔记生成失败：${message.slice(0, 200)}`)
              console.warn(`⚠️ 任务 ${task.id} 失败：${message}`)
            } else {
              updateTaskContent(task.id, { status })
            }
          }
        } catch (e: unknown) {
          console.error('❌ 任务轮询失败：', e)
          const error = e as { msg?: unknown; message?: unknown }
          const message = String(error.msg || error.message || '任务轮询失败')
          updateTaskContent(task.id, {
            status: 'FAILED',
            error: message,
          })
          toast.error(`笔记生成失败：${message.slice(0, 200)}`)
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval])
}
