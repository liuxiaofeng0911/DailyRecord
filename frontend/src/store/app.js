import { applyTheme, resolveTheme } from '@/theme'

const initialMode = localStorage.getItem('dr:theme') || 'dark'

export default {
  namespaced: true,
  state: () => ({
    themeMode: initialMode,
    dark: resolveTheme(initialMode) === 'dark',
    collapsed: false,
    mobile: window.innerWidth < 768,
  }),
  mutations: {
    setTheme(state, mode) {
      state.themeMode = mode
      state.dark = applyTheme(mode) === 'dark'
    },
    setCollapsed(state, value) {
      state.collapsed = value
    },
    setMobile(state, value) {
      state.mobile = value
    },
  },
}
