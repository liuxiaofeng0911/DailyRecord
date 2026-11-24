<template>
  <div class="heatmap-wrap">
    <div class="heatmap">
      <div v-for="(week, index) in weeks" :key="index" class="week">
        <a-tooltip
          v-for="cell in week"
          :key="cell.date"
          :title="cell.title"
          placement="top"
        >
          <button
            type="button"
            class="cell"
            :class="[`level-${cell.level}`, { empty: !cell.inYear, today: cell.isToday }]"
            :aria-label="cell.title"
            @click="cell.inYear && $emit('select', cell.date)"
          />
        </a-tooltip>
      </div>
    </div>
    <div class="legend">
      <span class="muted">少</span>
      <i class="cell level-0" />
      <i class="cell level-1" />
      <i class="cell level-2" />
      <i class="cell level-3" />
      <span class="muted">多</span>
    </div>
  </div>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed } from 'vue'

const props = defineProps({
  year: { type: Number, required: true },
  days: { type: Array, default: () => [] },
})
defineEmits(['select'])

const weeks = computed(() => {
  const dayMap = new Map(props.days.map((item) => [item.date, item]))
  const first = dayjs(`${props.year}-01-01`)
  const last = dayjs(`${props.year}-12-31`)
  const start = first.subtract((first.day() + 6) % 7, 'day')
  const end = last.add((7 - ((last.day() + 6) % 7) - 1 + 7) % 7, 'day')
  const todayStr = dayjs().format('YYYY-MM-DD')

  const result = []
  let cursor = start
  let currentWeek = []
  while (cursor.isBefore(end) || cursor.isSame(end, 'day')) {
    const dateStr = cursor.format('YYYY-MM-DD')
    const inYear = cursor.year() === props.year
    const record = dayMap.get(dateStr)
    const photos = record?.photos || 0
    let level = 0
    if (photos >= 3) level = 3
    else if (photos === 2) level = 2
    else if (photos === 1) level = 1
    currentWeek.push({
      date: dateStr,
      inYear,
      level,
      isToday: dateStr === todayStr,
      title: inYear
        ? `${dateStr}${record ? ` · ${photos} 张照片${record.mood ? ` · ${record.mood}` : ''}` : ' · 无记录'}`
        : '',
    })
    if (currentWeek.length === 7) {
      result.push(currentWeek)
      currentWeek = []
    }
    cursor = cursor.add(1, 'day')
  }
  if (currentWeek.length) result.push(currentWeek)
  return result
})
</script>

<style scoped lang="less">
.heatmap-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 6px;
}

.heatmap {
  display: flex;
  gap: 4px;
}

.week {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cell {
  width: 13px;
  height: 13px;
  border-radius: 3px;
  border: none;
  padding: 0;
  background: var(--app-bg-body);
  cursor: pointer;
}

.cell.empty {
  visibility: hidden;
  cursor: default;
}

.cell.level-0 {
  background: color-mix(in srgb, var(--app-border) 65%, transparent);
}

.cell.level-1 {
  background: color-mix(in srgb, var(--app-primary) 35%, transparent);
}

.cell.level-2 {
  background: color-mix(in srgb, var(--app-primary) 65%, transparent);
}

.cell.level-3 {
  background: var(--app-primary);
}

.cell.today {
  outline: 1px solid var(--app-text-1);
  outline-offset: 1px;
}

.legend {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
}

.legend .cell {
  display: inline-block;
  cursor: default;
}
</style>
