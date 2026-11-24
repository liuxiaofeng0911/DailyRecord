import dayjs from 'dayjs'
import { onBeforeUnmount, onMounted, ref } from 'vue'

export const DATE_FMT = 'YYYY-MM-DD'

export function today() {
  return dayjs().format(DATE_FMT)
}

export function formatDate(value) {
  return value ? dayjs(value).format(DATE_FMT) : ''
}

export function relativeDay(value) {
  const target = dayjs(value)
  const diff = dayjs().startOf('day').diff(target.startOf('day'), 'day')
  if (diff === 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff === 2) return '前天'
  return target.format('M 月 D 日')
}

export function downloadText(filename, content, mime = 'text/plain') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function draftKey(userId, date) {
  return `dr:draft:${userId}:${date}`
}

export function debounce(fn, wait = 300) {
  let timer = null
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), wait)
  }
}

/**
 * 页面数据刷新：可见时定时静默刷新、隐藏时暂停、恢复可见立即刷新一次。
 * loader 接收 { silent }，自行决定是否展示 loading。
 */
export function useAutoRefresh(loader, { interval = 60000 } = {}) {
  const lastUpdated = ref(null)
  const refreshing = ref(false)
  let inFlight = false
  let timer = null

  async function run(silent = true) {
    if (inFlight) return
    inFlight = true
    if (!silent) refreshing.value = true
    try {
      await loader({ silent })
      lastUpdated.value = new Date()
    } catch {
      // 静默刷新失败不打断页面，保留旧数据
    } finally {
      inFlight = false
      refreshing.value = false
    }
  }

  function startTimer() {
    stopTimer()
    timer = setInterval(() => {
      if (document.visibilityState === 'visible') run(true)
    }, interval)
  }

  function stopTimer() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function onVisibilityChange() {
    if (document.visibilityState === 'visible') {
      run(true)
      startTimer()
    } else {
      stopTimer()
    }
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibilityChange)
    if (document.visibilityState === 'visible') startTimer()
  })

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    stopTimer()
  })

  return { lastUpdated, refreshing, run, refresh: () => run(false) }
}
