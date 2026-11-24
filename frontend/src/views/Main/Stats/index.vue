<template>
  <div class="page stats-page">
    <div class="row-between page-head">
      <div>
        <h2 class="page-title">统计</h2>
        <p class="page-subtitle">记录密度、连续天数与常用标签。</p>
      </div>
      <div class="head-actions">
        <RefreshButton :last-updated="lastUpdated" :loading="refreshing" @refresh="run(false)" />
        <a-select v-model:value="year" :options="yearOptions" style="width: 120px" @change="run(false)" />
      </div>
    </div>

    <a-spin :spinning="loading">
      <div class="metric-grid">
        <div class="surface metric">
          <span>记录天数</span>
          <strong>{{ overview.totals.days }}</strong>
        </div>
        <div class="surface metric">
          <span>照片数量</span>
          <strong>{{ overview.totals.photos }}</strong>
        </div>
        <div class="surface metric">
          <span>当前连续</span>
          <strong>{{ overview.totals.currentStreak }} 天</strong>
        </div>
        <div class="surface metric">
          <span>最长连续</span>
          <strong>{{ overview.totals.longestStreak }} 天</strong>
        </div>
      </div>

      <section class="surface">
        <div class="row-between section-head">
          <strong>{{ year }} 年记录热力图</strong>
          <span class="muted">点击方块进入当天</span>
        </div>
        <Heatmap :year="year" :days="overview.days" @select="openDay" />
      </section>

      <div class="chart-grid">
        <section class="surface">
          <div class="row-between section-head">
            <strong>月度分布</strong>
            <span class="muted">每月记录天数</span>
          </div>
          <div class="bars">
            <div v-for="month in overview.months" :key="month.month" class="bar-item">
              <div class="bar-track">
                <div class="bar-fill" :style="{ height: barHeight(month.days) }" />
              </div>
              <span>{{ month.month }}月</span>
            </div>
          </div>
        </section>

        <section class="surface">
          <div class="row-between section-head">
            <strong>常用标签</strong>
            <span class="muted">Top 12</span>
          </div>
          <div v-if="overview.topTags.length" class="tag-list">
            <div v-for="tag in overview.topTags" :key="tag.name" class="tag-row">
              <span>{{ tag.name }}</span>
              <div class="tag-bar">
                <i :style="{ width: tagWidth(tag.count) }" />
              </div>
              <span class="muted">{{ tag.count }}</span>
            </div>
          </div>
          <a-empty v-else description="这一年还没有标签" />
        </section>
      </div>
    </a-spin>
  </div>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onActivated, onMounted, ref } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'

import { statsApi } from '@/api/api'
import Heatmap from '@/components/Heatmap.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import { useAutoRefresh } from '@/utils'

defineOptions({ name: 'Stats' })

const router = useRouter()
const store = useStore()
const nowYear = dayjs().year()
const year = ref(nowYear)
const loading = ref(false)
const renderedVersion = ref(-1)
const overview = ref({
  totals: { days: 0, photos: 0, currentStreak: 0, longestStreak: 0 },
  months: [],
  days: [],
  topTags: [],
  moods: [],
  recentDays: [],
})

const yearOptions = Array.from({ length: 8 }, (_, index) => {
  const value = nowYear - index
  return { label: `${value} 年`, value }
})

const maxDays = computed(() =>
  Math.max(1, ...(overview.value.months || []).map((item) => item.days)),
)
const maxTag = computed(() => Math.max(1, ...(overview.value.topTags || []).map((item) => item.count)))

function barHeight(days) {
  return `${Math.max(2, (days / maxDays.value) * 100)}%`
}

function tagWidth(count) {
  return `${Math.max(6, (count / maxTag.value) * 100)}%`
}

async function load({ silent = false } = {}) {
  if (!silent) loading.value = true
  try {
    overview.value = await statsApi.overview(year.value)
    renderedVersion.value = store.state.app.dataVersion.stats
  } finally {
    if (!silent) loading.value = false
  }
}

const { lastUpdated, refreshing, run } = useAutoRefresh(load)

function openDay(date) {
  router.push({ path: '/Main/Today', query: { date } })
}

onMounted(() => run(false))

onActivated(() => {
  if (renderedVersion.value !== store.state.app.dataVersion.stats) run(true)
})
</script>

<style scoped lang="less">
.stats-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 6px;

  span {
    font-size: 12px;
    color: var(--app-text-3);
  }

  strong {
    font-size: 24px;
    color: var(--app-text-1);
  }
}

.section-head {
  margin-bottom: 14px;
}

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.bars {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 180px;
}

.bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--app-text-3);
  height: 100%;
}

.bar-track {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  background: var(--app-bg-body);
  border-radius: 6px;
  overflow: hidden;
}

.bar-fill {
  width: 100%;
  background: linear-gradient(180deg, var(--app-primary), #7e57ff);
  border-radius: 6px 6px 0 0;
  transition: height 0.4s ease;
}

.tag-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tag-row {
  display: grid;
  grid-template-columns: 90px 1fr 40px;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.tag-bar {
  height: 8px;
  border-radius: 999px;
  background: var(--app-bg-body);
  overflow: hidden;

  i {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: var(--app-primary);
  }
}

@media (max-width: 768px) {
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
