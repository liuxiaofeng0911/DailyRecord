import dayjs from 'dayjs'

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
