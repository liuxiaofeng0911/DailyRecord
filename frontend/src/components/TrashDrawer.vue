<template>
  <a-drawer
    :open="visible"
    title="照片回收站"
    placement="right"
    :width="'min(520px, 100vw)'"
    @update:open="visible = $event"
  >
    <div class="trash-head">
      <span class="muted">删除后保留 {{ keepDays }} 天，到期自动清理；期间可恢复。</span>
      <a-button size="small" type="link" :loading="loading" @click="load">刷新</a-button>
    </div>

    <div v-if="items.length" class="trash-toolbar">
      <a-checkbox
        :checked="allChecked"
        :indeterminate="someChecked"
        @change="toggleAll"
      >
        全选
      </a-checkbox>
      <a-space>
        <a-button size="small" :disabled="!selected.length" @click="restore(selected)">
          恢复所选
        </a-button>
        <a-button size="small" danger :disabled="!selected.length" @click="confirmPurge(selected)">
          彻底删除
        </a-button>
      </a-space>
    </div>

    <a-spin :spinning="loading">
      <div v-if="items.length" class="trash-list">
        <article v-for="item in items" :key="item.id" class="trash-item">
          <a-checkbox
            :checked="selected.includes(item.id)"
            @change="toggleOne(item.id)"
          />
          <div class="thumb">
            <img :src="item.thumbnailUrl" :alt="`回收站照片 ${item.entryDate || ''}`" loading="lazy" />
            <span v-if="item.mediaType === 'VIDEO'" class="video-badge">视频</span>
          </div>
          <div class="trash-body">
            <div class="trash-title">{{ item.entryDate || '未关联日期' }}</div>
            <div class="muted small">
              {{ item.deletedAt }} 删除 · {{ item.deletedBy || '我' }}
            </div>
            <div class="days-left">剩余 {{ item.daysLeft }} 天</div>
            <div class="trash-actions">
              <a-button size="small" type="link" @click="restore([item.id])">恢复</a-button>
              <a-button size="small" type="link" danger @click="confirmPurge([item.id])">
                彻底删除
              </a-button>
            </div>
          </div>
        </article>
      </div>
      <a-empty v-else description="回收站是空的" />
    </a-spin>

    <div v-if="total > pageSize" class="trash-pager">
      <a-pagination
        :current="page"
        :page-size="pageSize"
        :total="total"
        size="small"
        show-less-items
        @change="loadPage"
      />
    </div>
  </a-drawer>
</template>

<script setup>
import { Modal, message } from 'antdv-next'
import { computed, ref, watch } from 'vue'
import { useStore } from 'vuex'

import { photoApi } from '@/api/api'

const store = useStore()
const keepDays = computed(() => store.state.auth.settings?.trashKeepDays || 30)

const props = defineProps({
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['update:open', 'changed'])

const visible = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const loading = ref(false)
const items = ref([])
const selected = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const allChecked = computed(
  () => items.value.length > 0 && selected.value.length === items.value.length,
)
const someChecked = computed(
  () => selected.value.length > 0 && selected.value.length < items.value.length,
)

function toggleAll(event) {
  selected.value = event.target.checked ? items.value.map((item) => item.id) : []
}

function toggleOne(id) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((item) => item !== id)
    : [...selected.value, id]
}

async function load(nextPage = page.value) {
  page.value = nextPage
  loading.value = true
  try {
    const data = await photoApi.trashList({
      page: { pageNumber: page.value, pageSize: pageSize.value },
    })
    items.value = data.list || []
    total.value = data.totalRow || 0
    selected.value = selected.value.filter((id) => items.value.some((item) => item.id === id))
  } finally {
    loading.value = false
  }
}

function loadPage(nextPage) {
  load(nextPage)
}

async function restore(ids) {
  if (!ids.length) return
  const result = await photoApi.trashRestore(ids)
  message.success(`已恢复 ${result.restored} 张照片`)
  selected.value = []
  await load()
  emit('changed')
}

function confirmPurge(ids) {
  if (!ids.length) return
  Modal.confirm({
    title: `彻底删除 ${ids.length} 张照片？`,
    content: '将立即清理文件与引用，无法恢复；从照片库导入的原图不会被删除。',
    okText: '彻底删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      const result = await photoApi.trashPurge(ids)
      message.success(`已彻底删除 ${result.purged} 张照片`)
      selected.value = []
      await load()
      emit('changed')
    },
  })
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      selected.value = []
      load(1)
    }
  },
)
</script>

<style scoped lang="less">
.trash-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
  font-size: 12px;
  margin-bottom: var(--space-3);
}

.trash-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--app-border);
  border-radius: var(--radius-control);
  margin-bottom: var(--space-3);
}

.trash-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.trash-item {
  display: grid;
  grid-template-columns: 24px 92px 1fr;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-2);
  border: 1px solid var(--app-border);
  border-radius: var(--radius-control);
}

.thumb {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  background: var(--app-bg-body);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
}

.video-badge {
  position: absolute;
  left: 6px;
  bottom: 6px;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 10px;
}

.trash-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.trash-title {
  font-weight: 600;
  color: var(--app-text-1);
}

.small {
  font-size: 12px;
}

.days-left {
  display: inline-flex;
  align-self: flex-start;
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  background: var(--app-primary-weak);
  color: var(--app-primary);
  font-size: 11px;
}

.trash-actions {
  display: flex;
  gap: var(--space-1);
  margin-left: -8px;
}

.trash-pager {
  display: flex;
  justify-content: center;
  margin-top: var(--space-4);
}
</style>
