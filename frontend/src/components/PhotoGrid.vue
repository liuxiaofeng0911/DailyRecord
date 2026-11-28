<template>
  <div class="photo-grid" :class="{ compact }">
    <div
      v-for="(photo, index) in photos"
      :key="photo.id"
      class="photo-item"
      :class="{ cover: photo.isCover }"
      role="button"
      tabindex="0"
      :title="photo.mediaType === 'VIDEO' ? '点击播放视频' : '点击查看大图'"
      :aria-label="photo.mediaType === 'VIDEO' ? '播放视频' : '查看大图'"
      @click="openViewer(index)"
      @keydown.enter.self="openViewer(index)"
    >
      <div v-if="isLocalVideo(photo)" class="video-placeholder">
        <span class="video-mark" />
        <span>视频</span>
      </div>
      <img v-else :src="thumbUrl(photo)" :alt="photo.caption || '照片'" loading="lazy" />
      <div v-if="photo.mediaType === 'VIDEO'" class="badge">视频</div>
      <div v-if="photo.isCover" class="badge cover-badge">封面</div>
      <div v-if="editable" class="photo-actions">
        <a-tooltip title="设为封面">
          <button type="button" aria-label="设为封面" @click.stop="$emit('cover', photo)">
            <AppIcon name="lucide:star" :size="15" />
          </button>
        </a-tooltip>
        <a-tooltip title="删除引用">
          <button type="button" aria-label="删除引用" class="danger" @click.stop="$emit('remove', photo)">
            <AppIcon name="lucide:trash-2" :size="15" />
          </button>
        </a-tooltip>
      </div>
      <p v-if="photo.caption || photo.aiKeywords?.length" class="caption">
        <span v-if="photo.caption" class="text">{{ photo.caption }}</span>
        <span v-if="photo.aiKeywords?.length" class="keywords">
          #{{ photo.aiKeywords.join(' #') }}
        </span>
      </p>
    </div>
    <slot />
    <PhotoViewer v-model:open="viewerOpen" :photos="photos" :start-index="viewerIndex" />
  </div>
</template>

<script setup>
import { ref } from 'vue'

import { photoApi } from '@/api/api'
import AppIcon from '@/components/AppIcon.vue'
import PhotoViewer from '@/components/PhotoViewer.vue'

defineProps({
  photos: { type: Array, default: () => [] },
  editable: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})
defineEmits(['cover', 'remove'])

const viewerOpen = ref(false)
const viewerIndex = ref(0)

function thumbUrl(photo) {
  return `${photoApi.thumbnail(photo.id)}?v=${photo.version || 0}`
}

function isLocalVideo(photo) {
  return photo.mediaType === 'VIDEO' && photo.storageKind !== 'immich'
}

function openViewer(index) {
  viewerIndex.value = index
  viewerOpen.value = true
}
</script>

<style scoped lang="less">
.photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}

.photo-item {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: var(--app-bg-elevated);
  border: 1px solid var(--app-border);
  aspect-ratio: 4 / 3;
  cursor: zoom-in;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.25s ease;
  }

  &:hover img {
    transform: scale(1.03);
  }

  &.cover {
    border-color: var(--app-primary);
    box-shadow: 0 0 0 2px var(--app-primary-weak);
  }
}

.badge {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 11px;
}

.video-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--app-text-3);
  font-size: 12px;
  background: linear-gradient(135deg, var(--app-bg-elevated), var(--app-bg-body));
}

.video-mark {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 2px solid currentColor;
  position: relative;

  &::after {
    content: '';
    position: absolute;
    left: 13px;
    top: 9px;
    border-left: 9px solid currentColor;
    border-top: 6px solid transparent;
    border-bottom: 6px solid transparent;
  }
}

.cover-badge {
  left: auto;
  right: 8px;
  background: var(--app-primary);
}

.photo-actions {
  position: absolute;
  right: 6px;
  bottom: 6px;
  display: flex;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.2s;

  button {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    border: none;
    background: rgba(0, 0, 0, 0.6);
    color: #fff;
    font-size: 12px;
    cursor: pointer;

    &.danger {
      background: rgba(229, 72, 77, 0.85);
    }
  }
}

.photo-item:hover .photo-actions {
  opacity: 1;
}

/* 触屏设备没有 hover，操作按钮需常驻显示，并放大点击区域 */
@media (hover: none), (pointer: coarse) {
  .photo-actions {
    opacity: 1;

    button {
      width: 34px;
      height: 34px;
    }
  }
}

@media (max-width: 768px) {
  .photo-grid {
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 10px;
  }
}

/* 共享记录等只读场景使用更紧凑的方格 */
.photo-grid.compact {
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 8px;
}

.photo-grid.compact .photo-item {
  aspect-ratio: 1;
}

@media (max-width: 768px) {
  .photo-grid.compact {
    grid-template-columns: repeat(auto-fill, minmax(76px, 1fr));
  }
}

.caption {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  margin: 0;
  padding: 18px 10px 8px;
  font-size: 12px;
  color: #fff;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.65));

  .text {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
  }

  .keywords {
    display: block;
    margin-top: 3px;
    font-size: 11px;
    opacity: 0.82;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

@media (max-width: 768px) {
  .caption {
    padding: 14px 8px 6px;
    font-size: 11px;
  }
}
</style>
