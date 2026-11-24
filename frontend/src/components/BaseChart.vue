<template>
  <VChart
    class="base-chart"
    :style="{ height: `${height}px` }"
    :option="option"
    :aria-label="ariaLabel"
    autoresize
    @click="$emit('chart-click', $event)"
  />
</template>

<script setup>
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, CanvasRenderer])

defineProps({
  option: { type: Object, required: true },
  height: { type: Number, default: 280 },
  ariaLabel: { type: String, default: '数据图表' },
})
defineEmits(['chart-click'])
</script>

<style scoped lang="less">
.base-chart {
  width: 100%;
}
</style>
