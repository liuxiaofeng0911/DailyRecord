<template>
  <div class="photo-grid">
    <div v-for="photo in photos" :key="photo.id" class="photo-item" :class="{ cover: photo.isCover }">
      <div v-if="isLocalVideo(photo)" class="video-placeholder">
        <span class="video-mark" />
        <span>视频</span>
      </div>
      <img v-else :src="thumbUrl(photo)" :alt="photo.caption || '照片'" loading="lazy" />
      <div v-if="photo.mediaType === 'VIDEO'" class="badge">视频</div>
      <div v-if="photo.isCover" class="badge cover-badge">封面</div>
      <div v-if="editable" class="photo-actions">
        <a-tooltip title="设为封面">
          <button type="button" aria-label="设为封面" @click="$emit('cover', photo)">
            <AppIcon name="lucide:star" :size="15" />
          </button>
        </a-tooltip>
        <a-tooltip title="删除引用">
          <button type="button" aria-label="删除引用" class="danger" @click="$emit('remove', photo)">
            <AppIcon name="lucide:trash-2" :size="15" />
          </button>
        </a-tooltip>
      </div>
      <p v-if="photo.caption" class="caption">{{ photo.caption }}</p>
    </div>
    <slot />
  </div>
</template>

<script setup>
import { photoApi } from '@/api/api'
import AppIcon from '@/components/AppIcon.vue'

defineProps({
  photos: { type: Array, default: () => [] },
  editable: { type: Boolean, default: false },
})
defineEmits(['cover', 'remove'])

function thumbUrl(photo) {
  return `${photoApi.thumbnail(photo.id)}?v=${photo.version || 0}`
}

function isLocalVideo(photo) {
  return photo.mediaType === 'VIDEO' && photo.storageKind !== 'immich'
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

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
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
}
</style>
