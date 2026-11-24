<template>
  <a-select
    :value="store.state.app.themeMode"
    :options="options"
    size="small"
    style="width: 96px"
    :bordered="false"
    @change="onChange"
  />
</template>

<script setup>
import { useStore } from 'vuex'

import { THEMES } from '@/theme'

const store = useStore()
const options = THEMES.map((item) => ({ label: item.label, value: item.value }))

function onChange(value) {
  store.commit('app/setTheme', value)
}
</script>
