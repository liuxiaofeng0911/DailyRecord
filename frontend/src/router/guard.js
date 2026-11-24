import { message } from 'antdv-next'

import store from '@/store'

const LOGIN_PATH = '/Login'
const HOME_PATH = '/Main/Today'
const PUBLIC_PATHS = ['/', '/Login', '/Register', '/404']

export function setupGuard(router) {
  router.beforeEach(async (to) => {
    document.title = to.meta?.title ? `${to.meta.title} · 每日照片记录` : '每日照片记录'
    const token = localStorage.getItem('dr:token')

    if (PUBLIC_PATHS.includes(to.path)) {
      if (token && (to.path === '/Login' || to.path === '/Register')) {
        return HOME_PATH
      }
      return true
    }

    if (!token) {
      return { path: LOGIN_PATH, query: { redirect: to.fullPath } }
    }

    if (!store.state.auth.userInfo) {
      try {
        await store.dispatch('auth/fetchMe')
        store.dispatch('dict/load')
      } catch {
        store.dispatch('auth/clear')
        return { path: LOGIN_PATH }
      }
    }

    if (to.meta?.owner && !store.getters['auth/isOwner']) {
      message.error('无权限访问该页面')
      return HOME_PATH
    }
    return true
  })
}

export { HOME_PATH, LOGIN_PATH, PUBLIC_PATHS }
