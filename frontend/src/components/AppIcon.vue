<template>
  <Icon
    class="app-icon"
    :icon="resolved"
    :width="size"
    :height="size"
    :style="color ? { color } : undefined"
    aria-hidden="true"
  />
</template>

<script setup>
import { Icon, getIcon } from '@iconify/vue'
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, default: 'lucide:sparkles' },
  size: { type: [Number, String], default: 18 },
  color: { type: String, default: '' },
})

const resolved = computed(() => {
  const name = props.name || 'lucide:sparkles'
  return getIcon(name) ? name : 'lucide:sparkles'
})
</script>

<style scoped lang="less">
.app-icon {
  display: inline-block;
  flex: none;
  vertical-align: -0.125em;
}
</style>
