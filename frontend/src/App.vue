<template>
  <a-config-provider :theme="themeConfig" :locale="zhCN">
    <router-view />
  </a-config-provider>
</template>

<script setup>
import { theme } from 'antdv-next'
import zhCN from 'antdv-next/locale/zh_CN'
import { computed } from 'vue'
import { useStore } from 'vuex'

const store = useStore()
const themeConfig = computed(() => ({
  algorithm: store.state.app.dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
  token: {
    colorPrimary: '#2090ff',
    borderRadius: 10,
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
}))
</script>
