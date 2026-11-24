import axios from 'axios'
import { message } from 'antdv-next'

const TOKEN_KEY = 'dr:token'

let expiring = false

function handleLoginExpired() {
  if (expiring) return
  expiring = true
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('dr:user')
  window.dispatchEvent(new CustomEvent('dr-login-expired'))
  setTimeout(() => {
    expiring = false
    if (!window.location.hash.startsWith('#/Login')) {
      window.location.hash = '#/Login'
    }
  }, 300)
}

const service = axios.create({ baseURL: '/api', timeout: 30000 })

service.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = token
  return config
})

service.interceptors.response.use(
  (response) => {
    const renewed = response.headers?.token
    if (renewed) localStorage.setItem(TOKEN_KEY, renewed)
    const data = response.data
    if (data && typeof data === 'object' && 'code' in data) {
      if (data.code === 200) return data.data
      if (data.code === 401 || data.code === 1003) {
        message.error(data.message || '登录已失效，请重新登录')
        handleLoginExpired()
      } else if (!response.config?.silent) {
        message.error(data.message || '操作失败')
      }
      return Promise.reject(Object.assign(new Error(data.message || '操作失败'), data))
    }
    return data
  },
  (error) => {
    const status = error.response?.status
    if (status === 401 || status === 403) {
      handleLoginExpired()
    }
    if (!error.config?.silent) {
      const text = error.response?.data?.message || error.message || '网络异常，请稍后重试'
      message.error(text)
    }
    return Promise.reject(error)
  },
)

export function Post(url, data = {}, config = {}) {
  return service.post(url, data, config)
}

export function Get(url, config = {}) {
  return service.get(url, config)
}

export function Upload(url, formData, config = {}) {
  return service.post(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
    ...config,
  })
}

export { TOKEN_KEY }
export default service
