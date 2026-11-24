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

      <section class="surface">
        <div class="row-between section-head">
          <strong>月度签到率</strong>
        </div>
        <BaseChart
          :option="monthOption"
          :height="280"
          aria-label="月度签到率柱状图，纵轴为 0 到 100%"
          @chart-click="onMonthClick"
        />
        <a-table
          class="month-table"
          size="small"
          :columns="monthColumns"
          :data-source="monthRows"
          :pagination="false"
          row-key="month"
          :scroll="{ x: 420 }"
        />
      </section>

      <div class="chart-grid">
        <section class="surface">
          <div class="row-between section-head">
            <strong>情绪分布</strong>
            <span class="muted">按记录天数</span>
          </div>
          <BaseChart
            v-if="overview.moods.length"
            :option="moodOption"
            :height="280"
            aria-label="情绪分布环形图"
          />
          <a-empty v-else description="这一年还没有记录情绪" />
        </section>

        <section class="surface">
          <div class="row-between section-head">
            <strong>常用标签</strong>
            <span class="muted">Top 12</span>
          </div>
          <BaseChart
            v-if="overview.topTags.length"
            :option="tagOption"
            :height="280"
            aria-label="常用标签横向条形图"
          />
          <a-empty v-else description="这一年还没有标签" />
        </section>
      </div>

      <section class="surface">
        <div class="row-between section-head">
          <strong>近 30 天记录</strong>
          <span class="muted">有记录即打卡</span>
        </div>
        <BaseChart :option="recentOption" :height="220" aria-label="近 30 天记录折线图" />
      </section>
    </a-spin>
  </div>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from 'vuex'

import { statsApi } from '@/api/api'
import BaseChart from '@/components/BaseChart.vue'
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

const PALETTE = ['#2090ff', '#7e57ff', '#46b37c', '#f5a524', '#e5484d', '#00b8d9', '#ff8fa3', '#8f9aab']

function cssVar(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

const themeTick = computed(() => (store.state.app.dark ? 'dark' : 'light'))

const axisStyle = computed(() => {
  themeTick.value
  return {
    text: cssVar('--app-text-2', '#8b93a3'),
    line: cssVar('--app-border', '#e3e7ef'),
    split: cssVar('--app-border', '#e3e7ef'),
    surface: cssVar('--app-bg-container', '#ffffff'),
  }
})

const monthRows = computed(() =>
  (overview.value.months || []).map((item) => ({
    key: item.month,
    month: `${item.month} 月`,
    days: item.days,
    daysInMonth: item.daysInMonth,
    rate: `${Math.round((item.rate || 0) * 100)}%`,
  })),
)

const monthColumns = [
  { title: '月份', dataIndex: 'month', key: 'month', width: 90 },
  { title: '记录天数', dataIndex: 'days', key: 'days', width: 100 },
  { title: '自然天数', dataIndex: 'daysInMonth', key: 'daysInMonth', width: 100 },
  { title: '签到率', dataIndex: 'rate', key: 'rate', width: 90 },
]

const monthOption = computed(() => {
  const style = axisStyle.value
  const months = overview.value.months || []
  return {
    grid: { left: 44, right: 16, top: 36, bottom: 32 },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const item = months[params[0]?.dataIndex ?? 0]
        if (!item) return ''
        return `${item.month} 月<br/>记录 ${item.days} 天 / ${item.daysInMonth} 天<br/>签到率 ${Math.round(item.rate * 100)}%`
      },
    },
    xAxis: {
      type: 'category',
      data: months.map((item) => `${item.month}月`),
      axisLine: { lineStyle: { color: style.line } },
      axisLabel: { color: style.text, fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      interval: 25,
      axisLabel: { color: style.text, fontSize: 11, formatter: '{value}%' },
      splitLine: { lineStyle: { color: style.split, type: 'dashed' } },
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 26,
        data: months.map((item) => Math.round((item.rate || 0) * 1000) / 10),
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: PALETTE[0] },
              { offset: 1, color: PALETTE[1] },
            ],
          },
        },
        label: {
          show: true,
          position: 'top',
          color: style.text,
          fontSize: 10,
          formatter: (params) => {
            const item = months[params.dataIndex]
            return item ? `${item.days} 天 · ${Math.round(item.rate * 100)}%` : ''
          },
        },
      },
    ],
  }
})

const moodOption = computed(() => {
  const style = axisStyle.value
  const moods = overview.value.moods || []
  return {
    color: PALETTE,
    tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 天（{d}%）' },
    legend: { bottom: 0, textStyle: { color: style.text, fontSize: 11 }, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: style.surface, borderWidth: 2 },
        label: { color: style.text, fontSize: 11, formatter: '{b} {c} 天' },
        data: moods.map((item) => ({ name: item.name, value: item.count })),
      },
    ],
  }
})

const tagOption = computed(() => {
  const style = axisStyle.value
  const tags = [...(overview.value.topTags || [])].reverse()
  return {
    grid: { left: 82, right: 40, top: 12, bottom: 24 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'value',
      axisLabel: { color: style.text, fontSize: 11 },
      splitLine: { lineStyle: { color: style.split, type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      data: tags.map((item) => item.name),
      axisLine: { lineStyle: { color: style.line } },
      axisLabel: { color: style.text, fontSize: 11 },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 14,
        data: tags.map((item) => item.count),
        itemStyle: { borderRadius: [0, 6, 6, 0], color: PALETTE[0] },
        label: {
          show: true,
          position: 'right',
          color: style.text,
          fontSize: 11,
          formatter: '{c}',
        },
      },
    ],
  }
})

const recentOption = computed(() => {
  const style = axisStyle.value
  const days = overview.value.recentDays || []
  return {
    grid: { left: 56, right: 16, top: 24, bottom: 32 },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const index = params[0]?.dataIndex ?? 0
        const item = days[index]
        if (!item) return ''
        return `${item.date}<br/>${item.recorded ? '已记录' : '未记录'}`
      },
    },
    xAxis: {
      type: 'category',
      data: days.map((item) => item.date.slice(5)),
      axisLine: { lineStyle: { color: style.line } },
      axisLabel: { color: style.text, fontSize: 10, interval: 4 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
      interval: 1,
      axisLabel: {
        color: style.text,
        fontSize: 11,
        formatter: (value) => (value === 1 ? '记录' : '未记'),
      },
      splitLine: { lineStyle: { color: style.split, type: 'dashed' } },
    },
    series: [
      {
        type: 'line',
        smooth: false,
        symbolSize: 6,
        data: days.map((item) => (item.recorded ? 1 : 0)),
        lineStyle: { width: 2, color: PALETTE[0] },
        itemStyle: { color: PALETTE[0] },
        areaStyle: { color: 'rgba(32, 144, 255, 0.12)' },
        label: {
          show: true,
          color: style.text,
          fontSize: 10,
          formatter: (params) => (params.value === 1 ? '✓' : ''),
        },
      },
    ],
  }
})

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

function onMonthClick(params) {
  const month = Number(params?.dataIndex) + 1
  if (!month) return
  const value = `${year.value}-${String(month).padStart(2, '0')}`
  router.push({ path: '/Main/Timeline', query: { month: value } })
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
  gap: var(--space-5);
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

.month-table {
  margin-top: var(--space-3);
}

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
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
