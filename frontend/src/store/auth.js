import { authApi } from '@/api/api'
import { TOKEN_KEY } from '@/api/axios'
import { encrypt } from '@/api/crypto'

const USER_KEY = 'dr:user'

function readUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export default {
  namespaced: true,
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    userInfo: readUser(),
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    isOwner: (state) =>
      state.userInfo?.roleCode === 'OWNER' || state.userInfo?.userType === '2',
  },
  mutations: {
    setToken(state, token) {
      state.token = token || ''
      if (token) localStorage.setItem(TOKEN_KEY, token)
      else localStorage.removeItem(TOKEN_KEY)
    },
    setUserInfo(state, info) {
      state.userInfo = info || null
      if (info) localStorage.setItem(USER_KEY, JSON.stringify(info))
      else localStorage.removeItem(USER_KEY)
    },
  },
  actions: {
    async login({ commit }, { identifier, password, rememberMe }) {
      const encrypted = await encrypt(password)
      const data = await authApi.login({ identifier, password: encrypted, rememberMe })
      commit('setToken', data.token)
      commit('setUserInfo', data.userInfo)
      return data
    },
    async register({ commit }, { userid, username, email, password, inviteCode }) {
      const payload = {
        userid,
        username,
        email,
        password: await encrypt(password),
        confirmPassword: await encrypt(password),
        inviteCode: inviteCode || '',
      }
      const data = await authApi.register(payload)
      commit('setToken', data.token)
      commit('setUserInfo', data.userInfo)
      return data
    },
    async fetchMe({ commit }) {
      const data = await authApi.me()
      commit('setUserInfo', data.userInfo)
      return data
    },
    async logout({ commit }) {
      try {
        await authApi.logout()
      } catch {
        // 忽略退出失败，本地状态仍然清理
      }
      commit('setToken', '')
      commit('setUserInfo', null)
    },
    clear({ commit }) {
      commit('setToken', '')
      commit('setUserInfo', null)
    },
  },
}
