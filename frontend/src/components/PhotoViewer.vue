<template>
  <Teleport to="body">
    <div v-if="open" class="photo-viewer" @click.self="close">
      <div class="pv-topbar">
        <div class="pv-title">
          <span class="pv-name">{{ title }}</span>
          <span v-if="photos.length > 1" class="pv-count">{{ index + 1 }} / {{ photos.length }}</span>
        </div>
        <button type="button" class="pv-icon" aria-label="关闭" @click="close">
          <AppIcon name="lucide:x" :size="20" />
        </button>
      </div>

      <div
        class="pv-stage"
        :class="{ video: isVideo }"
        @click.self="close"
        @pointerdown="onPointerDown"
        @wheel.prevent="onWheel"
        @dblclick="toggleZoom"
      >
        <button
          v-if="multiple"
          type="button"
          class="pv-nav prev"
          aria-label="上一张"
          @click.stop="go(-1)"
        >
          <AppIcon name="lucide:chevron-left" :size="26" />
        </button>

        <div v-if="loading" class="pv-loading">加载中…</div>
        <div v-if="failed" class="pv-error">图片加载失败，可能已被删除</div>
        <video
          v-if="current && isVideo"
          :key="current.id"
          :src="src"
          class="pv-media"
          controls
          autoplay
          playsinline
        />
        <img
          v-else-if="current"
          :key="current.id"
          :src="src"
          class="pv-media"
          :class="{ dragging }"
          :style="mediaStyle"
          :alt="current.caption || '照片'"
          draggable="false"
          @load="onLoaded"
          @error="onLoadError"
        />

        <button
          v-if="multiple"
          type="button"
          class="pv-nav next"
          aria-label="下一张"
          @click.stop="go(1)"
        >
          <AppIcon name="lucide:chevron-right" :size="26" />
        </button>
      </div>

      <div class="pv-toolbar">
        <template v-if="!isVideo">
          <a-tooltip title="缩小">
            <button type="button" class="pv-icon" aria-label="缩小" @click="zoomBy(-0.25)">
              <AppIcon name="lucide:zoom-out" :size="18" />
            </button>
          </a-tooltip>
          <span class="pv-scale">{{ Math.round(scale * 100) }}%</span>
          <a-tooltip title="放大">
            <button type="button" class="pv-icon" aria-label="放大" @click="zoomBy(0.25)">
              <AppIcon name="lucide:zoom-in" :size="18" />
            </button>
          </a-tooltip>
          <span class="pv-divider" />
          <a-tooltip title="向左旋转">
            <button type="button" class="pv-icon" aria-label="向左旋转" @click="rotateBy(-90)">
              <AppIcon name="lucide:rotate-ccw" :size="18" />
            </button>
          </a-tooltip>
          <a-tooltip title="向右旋转">
            <button type="button" class="pv-icon" aria-label="向右旋转" @click="rotateBy(90)">
              <AppIcon name="lucide:rotate-cw" :size="18" />
            </button>
          </a-tooltip>
          <span class="pv-divider" />
          <button type="button" class="pv-text-btn" @click="resetTransform">还原</button>
        </template>
        <span v-else class="pv-hint">视频不支持旋转缩放，可用两侧按钮切换</span>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'

import { photoApi } from '@/api/api'
import AppIcon from '@/components/AppIcon.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  photos: { type: Array, default: () => [] },
  startIndex: { type: Number, default: 0 },
})
const emit = defineEmits(['update:open'])

const MIN_SCALE = 0.3
const MAX_SCALE = 6
const STEP = 0.25

const index = ref(0)
const scale = ref(1)
const rotate = ref(0)
const offset = reactive({ x: 0, y: 0 })
const dragging = ref(false)
const loading = ref(false)
const failed = ref(false)

const current = computed(() => props.photos[index.value] || null)
const isVideo = computed(() => current.value?.mediaType === 'VIDEO')
const src = computed(() => (current.value ? photoApi.original(current.value.id) : ''))
const title = computed(() => current.value?.caption || '照片预览')
const multiple = computed(() => props.photos.length > 1)
const mediaStyle = computed(() => ({
  transform: `translate3d(${offset.x}px, ${offset.y}px, 0) rotate(${rotate.value}deg) scale(${scale.value})`,
}))

const pointers = new Map()
let dragOrigin = null
let pinchStart = null
let lastOverflow = ''

function clamp(value) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value))
}

function pointerDistance() {
  const list = [...pointers.values()]
  if (list.length < 2) return 0
  return Math.hypot(list[0].x - list[1].x, list[0].y - list[1].y)
}

function resetTransform() {
  scale.value = 1
  rotate.value = 0
  offset.x = 0
  offset.y = 0
}

function close() {
  emit('update:open', false)
}

function go(step) {
  if (props.photos.length < 2) return
  index.value = (index.value + step + props.photos.length) % props.photos.length
}

function zoomBy(delta) {
  if (isVideo.value) return
  scale.value = clamp(scale.value + delta)
}

function rotateBy(deg) {
  if (isVideo.value) return
  rotate.value += deg
}

function toggleZoom() {
  if (isVideo.value) return
  scale.value = scale.value > 1.2 ? 1 : 2
}

function onWheel(event) {
  if (isVideo.value) return
  const delta = event.deltaY > 0 ? -STEP : STEP
  zoomBy(delta)
}

function onPointerDown(event) {
  if (isVideo.value || (event.button && event.button !== 0)) return
  if (event.target?.closest?.('button')) return
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pointers.size === 1) {
    dragging.value = true
    dragOrigin = { x: offset.x, y: offset.y, sx: event.clientX, sy: event.clientY }
  } else if (pointers.size === 2) {
    dragOrigin = null
    pinchStart = { distance: pointerDistance(), scale: scale.value }
  }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', endPointer)
  window.addEventListener('pointercancel', endPointer)
}

function onPointerMove(event) {
  if (!pointers.has(event.pointerId)) return
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  if (pointers.size === 2 && pinchStart) {
    const distance = pointerDistance()
    if (pinchStart.distance > 0) {
      scale.value = clamp(pinchStart.scale * (distance / pinchStart.distance))
    }
    return
  }
  if (dragOrigin) {
    offset.x = dragOrigin.x + (event.clientX - dragOrigin.sx)
    offset.y = dragOrigin.y + (event.clientY - dragOrigin.sy)
  }
}

function endPointer(event) {
  pointers.delete(event.pointerId)
  if (pointers.size < 2) pinchStart = null
  if (pointers.size === 0) {
    dragOrigin = null
    dragging.value = false
    removePointerListeners()
  }
}

function removePointerListeners() {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', endPointer)
  window.removeEventListener('pointercancel', endPointer)
}

function onLoaded() {
  loading.value = false
}

function onLoadError() {
  loading.value = false
  failed.value = true
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    close()
  } else if (event.key === 'ArrowLeft') {
    go(-1)
  } else if (event.key === 'ArrowRight') {
    go(1)
  } else if (event.key === '+' || event.key === '=') {
    zoomBy(STEP)
  } else if (event.key === '-') {
    zoomBy(-STEP)
  }
}

function bindKeys() {
  window.addEventListener('keydown', onKeydown)
}

function unbindKeys() {
  window.removeEventListener('keydown', onKeydown)
}

watch(
  () => props.open,
  (value) => {
    if (value) {
      index.value = Math.min(Math.max(props.startIndex, 0), Math.max(props.photos.length - 1, 0))
      resetTransform()
      failed.value = false
      loading.value = !isVideo.value
      lastOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      bindKeys()
    } else {
      document.body.style.overflow = lastOverflow
      unbindKeys()
      removePointerListeners()
      pointers.clear()
      dragOrigin = null
      pinchStart = null
    }
  },
)

watch(
  () => props.startIndex,
  (value) => {
    if (props.open) {
      index.value = Math.min(Math.max(value, 0), Math.max(props.photos.length - 1, 0))
    }
  },
)

watch(current, () => {
  resetTransform()
  failed.value = false
  loading.value = !isVideo.value
})

onBeforeUnmount(() => {
  document.body.style.overflow = lastOverflow
  unbindKeys()
  removePointerListeners()
})
</script>

<style scoped lang="less">
.photo-viewer {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  flex-direction: column;
  background: rgba(15, 17, 21, 0.78);
  backdrop-filter: blur(4px);
  color: #fff;
  animation: pv-fade 0.18s ease;
}

.pv-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
}

.pv-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.pv-name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pv-count {
  flex: none;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
}

.pv-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  touch-action: none;
  user-select: none;
  cursor: grab;

  &.video {
    cursor: default;
  }
}

.pv-media {
  max-width: 92vw;
  max-height: calc(100vh - 180px);
  object-fit: contain;
  transition: transform 0.18s ease;
  will-change: transform;

  &.dragging {
    transition: none;
    cursor: grabbing;
  }
}

.pv-nav {
  position: absolute;
  top: 50%;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  margin-top: -21px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.35);
  color: #fff;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: rgba(0, 0, 0, 0.6);
  }

  &.prev {
    left: 14px;
  }

  &.next {
    right: 14px;
  }
}

.pv-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 14px 18px;
}

.pv-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.22);
  }
}

.pv-scale {
  min-width: 48px;
  text-align: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}

.pv-divider {
  width: 1px;
  height: 18px;
  margin: 0 6px;
  background: rgba(255, 255, 255, 0.18);
}

.pv-text-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 12px;
  cursor: pointer;

  &:hover {
    background: rgba(255, 255, 255, 0.22);
  }
}

.pv-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.pv-loading,
.pv-error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 13px;
  color: rgba(255, 255, 255, 0.75);
}

@keyframes pv-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (max-width: 768px) {
  .pv-nav {
    width: 36px;
    height: 36px;
    margin-top: -18px;

    &.prev {
      left: 8px;
    }

    &.next {
      right: 8px;
    }
  }

  .pv-media {
    max-width: 100vw;
    max-height: calc(100vh - 150px);
  }
}
</style>
