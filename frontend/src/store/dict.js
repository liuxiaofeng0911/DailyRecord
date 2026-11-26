import { systemApi } from '@/api/api'

const FALLBACK = {
  MOOD: [
    '开心',
    '兴奋',
    '愉悦',
    '平静',
    '复杂',
    '放松',
    '疲惫',
    '麻木',
    '低落',
    '怅然',
    '委屈',
    '烦躁',
    '焦虑',
  ].map((name) => ({
    code: name,
    name,
  })),
}

export default {
  namespaced: true,
  state: () => ({
    loaded: false,
    groups: {},
  }),
  getters: {
    options: (state) => (codeid) =>
      (state.groups[codeid] || []).map((item) => ({ label: item.name, value: item.code })),
    label: (state) => (codeid, code) => {
      const found = (state.groups[codeid] || []).find((item) => item.code === code)
      return found ? found.name : code
    },
    moods: (state) => (state.groups.MOOD || []).map((item) => item.name),
  },
  mutations: {
    setGroups(state, groups) {
      state.groups = groups
      state.loaded = true
    },
  },
  actions: {
    async load({ state, commit }) {
      if (state.loaded) return
      try {
        const rows = await systemApi.dictList()
        const groups = {}
        rows.forEach((row) => {
          groups[row.codeid] = groups[row.codeid] || []
          groups[row.codeid].push({ code: row.code, name: row.name })
        })
        if (!groups.MOOD) groups.MOOD = FALLBACK.MOOD
        commit('setGroups', groups)
      } catch {
        commit('setGroups', { ...FALLBACK })
      }
    },
  },
}
