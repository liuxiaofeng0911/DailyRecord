<template>
  <a-drawer
    :open="visible"
    title="修改记录"
    placement="right"
    :width="'min(420px, 100vw)'"
    @update:open="visible = $event"
  >
    <div class="history-head">
      <span class="muted">{{ date }} · 按时间倒序</span>
      <a-button size="small" type="link" :loading="loading" @click="load(page)">刷新</a-button>
    </div>

    <a-spin :spinning="loading">
      <div v-if="items.length" class="history-list">
        <article v-for="item in items" :key="item.id" class="history-item">
          <div class="history-meta">
            <span class="operator">{{ item.operatorName || '我' }}</span>
            <a-tag :color="actionColor(item.action)" class="action-tag">
              {{ actionLabel(item.action) }}
            </a-tag>
            <span class="time">{{ item.createdAt }}</span>
          </div>
          <ul class="change-list">
            <li v-for="(change, index) in item.changes" :key="index">
              <template v-if="change.field === 'note'">
                <span class="field">文字</span>
                <span v-if="change.added" class="add">＋{{ change.added }}</span>
                <span v-if="change.removed" class="remove">－{{ change.removed }}</span>
                <span v-if="change.beforeLength !== undefined" class="muted">
                  {{ change.beforeLength }} → {{ change.afterLength }} 字
                </span>
              </template>
              <template v-else-if="change.field === 'tags'">
                <span class="field">标签</span>
                <span v-if="change.added?.length" class="add">＋{{ change.added.join('、') }}</span>
                <span v-if="change.removed?.length" class="remove">
                  －{{ change.removed.join('、') }}
                </span>
              </template>
              <template v-else-if="change.field === 'mood'">
                <span class="field">情绪</span>
                <span class="muted">{{ change.before || '无' }} → {{ change.after || '无' }}</span>
              </template>
              <template v-else-if="change.field === 'cover'">
                <span class="field">封面</span>
                <span class="muted">{{ change.after ? '已设置' : '已取消' }}</span>
              </template>
              <template v-else-if="change.field === 'photos'">
                <span class="field">照片</span>
                <span v-if="change.added?.length" class="add">＋{{ change.added.length }} 张</span>
                <span v-if="change.removed?.length" class="remove">
                  －{{ change.removed.length }} 张
                </span>
              </template>
              <template v-else-if="change.before !== undefined || change.after !== undefined">
                <span class="field">{{ fieldLabel(change.field) }}</span>
                <span v-if="change.after !== undefined" class="muted">→ {{ change.after ?? '无' }}</span>
                <span v-if="change.before !== undefined" class="muted">
                  （原 {{ change.before ?? '无' }}）
                </span>
              </template>
              <template v-else>
                <span class="field">{{ fieldLabel(change.field) }}</span>
                <span class="muted">{{ changeText(change) }}</span>
              </template>
              <span v-if="change.mediaType" class="muted">（{{ change.mediaType }}）</span>
            </li>
          </ul>
        </article>
      </div>
      <a-empty v-else description="这一天还没有修改记录" />
    </a-spin>

    <div v-if="total > pageSize" class="history-pager">
      <a-pagination
        :current="page"
        :page-size="pageSize"
        :total="total"
        size="small"
        show-less-items
        @change="load"
      />
    </div>
  </a-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { entryApi } from '@/api/api'

const props = defineProps({
  open: { type: Boolean, default: false },
  date: { type: String, default: '' },
})
const emit = defineEmits(['update:open'])

const visible = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const ACTIONS = {
  CREATE: '创建',
  UPDATE: '修改',
  DELETE: '删除',
  TRASH: '移入回收站',
  RESTORE: '恢复',
  PURGE: '彻底删除',
}

function actionLabel(action) {
  return ACTIONS[action] || action
}

function actionColor(action) {
  if (action === 'DELETE' || action === 'PURGE') return 'red'
  if (action === 'CREATE') return 'green'
  if (action === 'TRASH') return 'orange'
  return 'blue'
}

function fieldLabel(field) {
  if (!field) return '内容'
  const labels = {
    note: '文字',
    tags: '标签',
    mood: '情绪',
    cover: '封面',
    photos: '照片',
    entry: '记录',
    photo: '照片',
    caption: '描述',
    takenAt: '拍摄时间',
  }
  return labels[field] || field
}

function changeText(change) {
  if (change.op === 'trash') return '移入回收站'
  if (change.op === 'restore') return '从回收站恢复'
  if (change.op === 'purge') return '彻底删除'
  if (change.op === 'delete') {
    const parts = []
    if (change.noteLength) parts.push(`正文 ${change.noteLength} 字`)
    if (change.tags?.length) parts.push(`${change.tags.length} 个标签`)
    if (change.photoCount) parts.push(`${change.photoCount} 张照片`)
    return parts.join(' · ') || '已删除'
  }
  return ''
}

async function load(nextPage = 1) {
  if (!props.date) return
  page.value = nextPage
  loading.value = true
  try {
    const data = await entryApi.history({
      entryDate: props.date,
      page: { pageNumber: page.value, pageSize: pageSize.value },
    })
    items.value = data.list || []
    total.value = data.totalRow || 0
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.date],
  ([open]) => {
    if (open) load(1)
  },
)
</script>

<style scoped lang="less">
.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
  font-size: 12px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.history-item {
  padding: var(--space-3);
  border: 1px solid var(--app-border);
  border-radius: var(--radius-control);
  background: var(--app-bg-elevated);
}

.history-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  font-size: 12px;
}

.operator {
  font-weight: 600;
  color: var(--app-text-1);
}

.action-tag {
  margin: 0;
}

.time {
  color: var(--app-text-3);
  margin-left: auto;
}

.change-list {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  line-height: 1.6;
}

.field {
  display: inline-block;
  min-width: 52px;
  color: var(--app-text-3);
}

.add {
  color: var(--app-success);
  margin-right: var(--space-1);
  word-break: break-all;
}

.remove {
  color: var(--app-danger);
  margin-right: var(--space-1);
  word-break: break-all;
  text-decoration: line-through;
}

.history-pager {
  display: flex;
  justify-content: center;
  margin-top: var(--space-4);
}
</style>
