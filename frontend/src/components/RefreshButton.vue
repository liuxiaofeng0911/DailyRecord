<template>
  <button
    type="button"
    class="refresh-button"
    :aria-label="'刷新数据'"
    :disabled="loading"
    @click="$emit('refresh')"
  >
    <span class="refresh-icon" :class="{ spinning: loading }" aria-hidden="true">↻</span>
    <span class="refresh-label">刷新</span>
    <span v-if="updatedText" class="refresh-time">{{ updatedText }}</span>
  </button>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed } from 'vue'

const props = defineProps({
  lastUpdated: { type: Date, default: null },
  loading: { type: Boolean, default: false },
})
defineEmits(['refresh'])

const updatedText = computed(() =>
  props.lastUpdated ? `更新于 ${dayjs(props.lastUpdated).format('HH:mm')}` : '',
)
</script>

<style scoped lang="less">
.refresh-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--app-border);
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--app-text-2);
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;

  &:hover:not(:disabled) {
    border-color: var(--app-primary);
    color: var(--app-primary);
  }

  &:disabled {
    cursor: default;
    opacity: 0.7;
  }
}

.refresh-icon {
  display: inline-flex;
  font-size: 14px;
  line-height: 1;

  &.spinning {
    animation: spin 0.9s linear infinite;
  }
}

.refresh-time {
  color: var(--app-text-3);
  font-size: 11px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
