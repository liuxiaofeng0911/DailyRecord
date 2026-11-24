<template>
  <div class="page timeline-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">时间线</h2>
        <p class="page-subtitle">按月回看每一天的照片与记忆点。</p>
      </div>
      <div class="head-actions">
        <RefreshButton :last-updated="lastUpdated" :loading="refreshing" @refresh="run(false)" />
        <a-button type="primary" @click="$router.push('/Main/Today')">记今天</a-button>
      </div>
    </div>

    <section class="surface filter-card">
      <div class="filter-row">
        <a-input-search
          v-model:value="filters.keyword"
          placeholder="搜索记录文字"
          allow-clear
          style="max-width: 240px"
          @search="applyFilters"
        />
        <a-select
          v-model:value="filters.mood"
          :options="moodOptions"
          placeholder="情绪"
          allow-clear
          style="width: 140px"
        />
        <a-input
          v-model:value="filters.tag"
          placeholder="标签，如 散步"
          allow-clear
          style="width: 160px"
          @press-enter="applyFilters"
        />
        <a-range-picker v-model:value="filters.range" format="YYYY-MM-DD" />
        <a-button type="primary" @click="applyFilters">筛选</a-button>
        <a-button @click="resetFilters">重置</a-button>
      </div>
      <div class="preset-row">
        <a-button v-for="preset in presets" :key="preset.label" size="small" @click="applyPreset(preset)">
          {{ preset.label }}
        </a-button>
      </div>
    </section>

    <a-spin :spinning="loading">
      <div v-if="groups.length" class="timeline-list">
        <div v-for="group in groups" :key="group.month" class="month-group">
          <h3 class="month-title">{{ group.month }}</h3>
          <div
            v-for="item in group.items"
            :key="item.id"
            class="entry-row"
            role="button"
            tabindex="0"
            @click="openDay(item.entryDate)"
            @keydown.enter="openDay(item.entryDate)"
          >
            <div class="entry-date">
              <strong>{{ dayOfMonth(item.entryDate) }}</strong>
              <span>{{ weekday(item.entryDate) }}</span>
            </div>
            <div class="entry-cover">
              <img
                v-if="coverOf(item)"
                :src="coverOf(item)"
                :alt="item.note || '封面'"
                loading="lazy"
              />
              <div v-else class="cover-placeholder">无照片</div>
            </div>
            <div class="entry-body">
              <p class="entry-note">{{ item.note || '这一天没有留下文字' }}</p>
              <div class="entry-meta">
                <a-tag v-if="item.mood" color="blue">
                  <span class="meta-icon"><AppIcon :name="resolveMoodIcon(item.mood)" :size="13" /></span>
                  {{ item.mood }}
                </a-tag>
                <a-tag v-for="tag in item.tags" :key="tag.id">
                  <span class="meta-icon">
                    <AppIcon :name="resolveTagIcon(tag.name, tag.icon)" :size="13" />
                  </span>
                  {{ tag.name }}
                </a-tag>
                <span class="muted">{{ item.photos.length }} 个素材</span>
                <a-button
                  size="small"
                  type="link"
                  class="history-link"
                  @click.stop="openHistory(item.entryDate)"
                >
                  修改历史
                </a-button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <a-empty v-else description="还没有记录，去写下今天吧" />
    </a-spin>

    <div v-if="total > pageSize" class="pagination-row">
      <a-pagination
        :current="pageNumber"
        :page-size="pageSize"
        :total="total"
        show-less-items
        @change="onPageChange"
      />
    </div>

    <HistoryDrawer v-model:open="historyOpen" :date="historyDate" />
  </div>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onActivated, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'

import { entryApi, photoApi } from '@/api/api'
import AppIcon from '@/components/AppIcon.vue'
import HistoryDrawer from '@/components/HistoryDrawer.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import { resolveMoodIcon, resolveTagIcon } from '@/store/icon'
import { useAutoRefresh } from '@/utils'

defineOptions({ name: 'Timeline' })

const route = useRoute()
const router = useRouter()
const store = useStore()

const loading = ref(false)
const entries = ref([])
const total = ref(0)
const pageNumber = ref(Number(route.query.page) || 1)
const pageSize = ref(20)
const renderedVersion = ref(-1)
const historyOpen = ref(false)
const historyDate = ref('')

const filters = reactive({
  keyword: route.query.keyword || '',
  mood: route.query.mood || undefined,
  tag: route.query.tag || '',
  range: route.query.month ? monthRange(route.query.month) : null,
})
const monthFilter = ref(route.query.month || '')

function monthRange(value) {
  const start = dayjs(`${value}-01`)
  return [start.startOf('month'), start.endOf('month')]
}

const presets = [
  { label: '本月', start: dayjs().startOf('month'), end: dayjs().endOf('month') },
  { label: '今年', start: dayjs().startOf('year'), end: dayjs().endOf('year') },
  {
    label: '近 30 天',
    start: dayjs().subtract(29, 'day'),
    end: dayjs(),
  },
]

const moodOptions = computed(() =>
  (store.state.dict.groups.MOOD || []).map((item) => ({ label: item.name, value: item.name })),
)

const groups = computed(() => {
  const map = new Map()
  entries.value.forEach((item) => {
    const month = item.entryDate.slice(0, 7)
    if (!map.has(month)) map.set(month, [])
    map.get(month).push(item)
  })
  return [...map.entries()].map(([month, items]) => ({ month, items }))
})

function dayOfMonth(value) {
  return String(Number(value.slice(8, 10)))
}

function weekday(value) {
  return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][dayjs(value).day()]
}

function coverOf(item) {
  const cover = item.photos.find((photo) => photo.isCover) || item.photos[0]
  return cover ? `${photoApi.thumbnail(cover.id)}?v=${cover.version || 0}` : ''
}

function buildWheres() {
  const wheres = []
  if (filters.range?.length === 2) {
    wheres.push({ column: 'entry_date', condition: 'ge', v1: filters.range[0].format('YYYY-MM-DD') })
    wheres.push({ column: 'entry_date', condition: 'le', v1: filters.range[1].format('YYYY-MM-DD') })
  }
  if (filters.keyword.trim()) {
    wheres.push({ column: 'note', condition: 'andLike', v1: filters.keyword.trim() })
  }
  if (filters.mood) wheres.push({ column: 'mood', condition: 'eq', v1: filters.mood })
  if (filters.tag.trim()) {
    wheres.push({ column: 'tag', condition: 'eq', v1: filters.tag.trim() })
  }
  return wheres
}

async function load({ silent = false } = {}) {
  if (!silent) loading.value = true
  try {
    const data = await entryApi.list({
      page: { pageNumber: pageNumber.value, pageSize: pageSize.value },
      wheres: buildWheres(),
      orderBys: [{ column: 'entry_date', condition: 'desc' }],
    })
    entries.value = data.list || []
    total.value = data.totalRow || 0
    renderedVersion.value = store.state.app.dataVersion.entries
  } finally {
    if (!silent) loading.value = false
  }
}

const { lastUpdated, refreshing, run } = useAutoRefresh(load)

function syncQuery() {
  router.replace({
    path: route.path,
    query: {
      keyword: filters.keyword || undefined,
      mood: filters.mood || undefined,
      tag: filters.tag || undefined,
      month: monthFilter.value || undefined,
      page: pageNumber.value > 1 ? pageNumber.value : undefined,
    },
  })
}

function applyFilters() {
  monthFilter.value = ''
  pageNumber.value = 1
  syncQuery()
  run(false)
}

function resetFilters() {
  filters.keyword = ''
  filters.mood = undefined
  filters.tag = ''
  filters.range = null
  monthFilter.value = ''
  applyFilters()
}

function applyPreset(preset) {
  monthFilter.value = ''
  filters.range = [preset.start, preset.end]
  applyFilters()
}

function onPageChange(page) {
  pageNumber.value = page
  syncQuery()
  run(false)
}

function openDay(date) {
  router.push({ path: '/Main/Today', query: { date } })
}

function openHistory(date) {
  historyDate.value = date
  historyOpen.value = true
}

watch(
  () => route.query,
  (query) => {
    const nextMonth = query.month || ''
    if (nextMonth !== monthFilter.value) {
      monthFilter.value = nextMonth
      filters.range = nextMonth ? monthRange(nextMonth) : null
      pageNumber.value = 1
      run(false)
      return
    }
    if ((query.keyword || '') !== filters.keyword || (query.mood || '') !== (filters.mood || '')) {
      filters.keyword = query.keyword || ''
      filters.mood = query.mood || undefined
      filters.tag = query.tag || ''
      pageNumber.value = Number(query.page) || 1
      run(false)
    }
  },
)

onMounted(() => run(false))

onActivated(() => {
  if (renderedVersion.value !== store.state.app.dataVersion.entries) run(true)
})
</script>

<style scoped lang="less">
.timeline-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-7);
}

.filter-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.filter-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.preset-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.month-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.month-title {
  position: sticky;
  top: 0;
  z-index: 2;
  margin: 0;
  padding: 8px 2px;
  font-size: 13px;
  letter-spacing: 1px;
  color: var(--app-text-3);
  background: var(--app-bg-body);
}

.entry-row {
  display: grid;
  grid-template-columns: 64px 132px 1fr;
  gap: 14px;
  padding: 12px;
  background: var(--app-bg-container);
  border: 1px solid var(--app-border);
  border-radius: 14px;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s;

  &:hover {
    border-color: var(--app-primary);
    transform: translateY(-1px);
  }
}

.entry-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--app-text-2);
  font-size: 12px;

  strong {
    font-size: 24px;
    color: var(--app-text-1);
  }
}

.entry-cover {
  aspect-ratio: 4 / 3;
  border-radius: 10px;
  overflow: hidden;
  background: var(--app-bg-elevated);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.cover-placeholder {
  height: 100%;
  display: grid;
  place-items: center;
  font-size: 12px;
  color: var(--app-text-3);
}

.entry-body {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
}

.entry-note {
  margin: 0;
  color: var(--app-text-1);
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.entry-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
}

.history-link {
  margin-left: auto;
  padding: 0;
  font-size: 12px;
}

.meta-icon {
  display: inline-flex;
  align-items: center;
  margin-right: 2px;
  vertical-align: -2px;
}

.pagination-row {
  display: flex;
  justify-content: center;
}

@media (max-width: 768px) {
  .entry-row {
    grid-template-columns: 48px 86px 1fr;
    gap: 10px;
  }

  .entry-date strong {
    font-size: 20px;
  }
}
</style>
