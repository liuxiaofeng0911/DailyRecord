<template>
  <a-drawer
    :open="visible"
    title="成员记录共享"
    placement="right"
    :width="'min(820px, 100vw)'"
    @update:open="visible = $event"
  >
    <p class="muted share-hint">
      按组织查看成员的每日记录；所有者不属于组织，组织共享暂停时仍可查看全部成员记录。
    </p>

    <div class="share-filters">
      <a-select
        v-model:value="filters.orgId"
        :options="orgOptions"
        placeholder="全部组织"
        allow-clear
        @change="reload"
      />
      <a-select
        v-model:value="filters.userId"
        :options="memberOptions"
        placeholder="全部成员"
        show-search
        option-filter-prop="label"
        allow-clear
        @change="reload"
      />
      <a-range-picker
        v-model:value="filters.range"
        format="YYYY-MM-DD"
        :placeholder="['开始日期', '结束日期']"
        @change="reload"
      />
      <a-input-search
        v-model:value="filters.keyword"
        placeholder="搜索记录内容"
        allow-clear
        @search="reload"
      />
    </div>

    <a-spin :spinning="loading">
      <div v-if="entries.length" class="share-list">
        <article v-for="item in entries" :key="item.id" class="share-item">
          <header class="share-head">
            <a-avatar :size="26">{{ (item.username || '?').slice(0, 1) }}</a-avatar>
            <strong>{{ item.username || item.userid }}</strong>
            <span class="muted">{{ item.entryDate }}</span>
            <a-tag v-if="item.mood" color="blue">{{ item.mood }}</a-tag>
          </header>
          <p v-if="item.note" class="share-note">{{ item.note }}</p>
          <p v-else class="muted share-note">这天没有文字内容</p>
          <div v-if="item.tags?.length" class="share-tags">
            <a-tag v-for="tag in item.tags" :key="tag.id">#{{ tag.name }}</a-tag>
          </div>
          <PhotoGrid
            v-if="item.photos?.length"
            compact
            :photos="item.photos"
          />
        </article>
      </div>
      <a-empty v-else description="这段时间还没有可共享的记录" />
    </a-spin>

    <div v-if="total > pageSize" class="share-pager">
      <a-pagination
        :current="pageNumber"
        :page-size="pageSize"
        :total="total"
        size="small"
        show-less-items
        @change="onPageChange"
      />
    </div>
  </a-drawer>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, reactive, ref, watch } from 'vue'

import { orgShareApi } from '@/api/api'
import PhotoGrid from '@/components/PhotoGrid.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  orgs: { type: Array, default: () => [] },
  orgId: { type: String, default: '' },
})
const emit = defineEmits(['update:open'])

const visible = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const loading = ref(false)
const entries = ref([])
const members = ref([])
const total = ref(0)
const pageNumber = ref(1)
const pageSize = ref(20)

const filters = reactive({
  orgId: props.orgId || undefined,
  userId: undefined,
  range: null,
  keyword: '',
})

const orgOptions = computed(() => [
  ...props.orgs.map((row) => ({ value: row.id, label: `${row.orgName}（${row.orgCode}）` })),
])

const memberOptions = computed(() =>
  members.value.map((row) => ({ value: row.id, label: `${row.username}（${row.userid}）` })),
)

function buildPayload() {
  const payload = {
    orgId: filters.orgId || undefined,
    userId: filters.userId || undefined,
    includeChildren: true,
    page: { pageNumber: pageNumber.value, pageSize: pageSize.value },
  }
  if (filters.range?.length === 2) {
    payload.start = filters.range[0].format('YYYY-MM-DD')
    payload.end = filters.range[1].format('YYYY-MM-DD')
  }
  if (filters.keyword.trim()) payload.keyword = filters.keyword.trim()
  return payload
}

async function loadMembers() {
  try {
    members.value =
      (await orgShareApi.members({
        orgId: filters.orgId || undefined,
        includeChildren: true,
      })) || []
    if (filters.userId && !members.value.some((row) => row.id === filters.userId)) {
      filters.userId = undefined
    }
  } catch {
    members.value = []
  }
}

async function loadEntries() {
  loading.value = true
  try {
    const data = await orgShareApi.entries(buildPayload())
    entries.value = data.list || []
    total.value = data.totalRow || 0
  } finally {
    loading.value = false
  }
}

function reload() {
  pageNumber.value = 1
  loadMembers()
  loadEntries()
}

function onPageChange(next) {
  pageNumber.value = next
  loadEntries()
}

watch(
  () => props.open,
  (open) => {
    if (!open) return
    filters.orgId = props.orgId || undefined
    filters.userId = undefined
    filters.keyword = ''
    filters.range = [dayjs().subtract(29, 'day'), dayjs()]
    pageNumber.value = 1
    loadMembers()
    loadEntries()
  },
)

watch(
  () => props.orgId,
  (value) => {
    if (!props.open) return
    filters.orgId = value || undefined
    reload()
  },
)
</script>

<style scoped lang="less">
.share-hint {
  margin: 0 0 var(--space-3);
  font-size: 12px;
  line-height: 1.7;
}

.share-filters {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.share-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.share-item {
  padding: var(--space-3);
  border: 1px solid var(--app-border);
  border-radius: var(--radius-control);
  background: var(--app-bg-elevated);
}

.share-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  margin-bottom: var(--space-2);
}

.share-note {
  margin: 0 0 var(--space-2);
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--app-text-1);
}

.share-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--space-2);
}

.share-pager {
  display: flex;
  justify-content: center;
  margin-top: var(--space-4);
}

@media (max-width: 720px) {
  .share-filters {
    grid-template-columns: 1fr;
  }
}
</style>
