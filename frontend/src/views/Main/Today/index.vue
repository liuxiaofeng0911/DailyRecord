<template>
  <div class="page today-page">
    <header class="today-header">
      <div class="date-block">
        <a-date-picker
          :value="dateValue"
          :allow-clear="false"
          format="YYYY-MM-DD"
          @change="onDateChange"
        />
        <span class="relative">{{ relativeDay(date) }}</span>
        <span v-if="streak > 0" class="chip">连续记录 {{ streak }} 天</span>
      </div>
      <div class="header-actions">
        <a-button :disabled="!entry" @click="removeEntry">删除当天</a-button>
        <a-button type="primary" :loading="saving" @click="save">保存</a-button>
      </div>
    </header>

    <a-spin :spinning="loading">
      <section class="surface note-card">
        <a-textarea
          v-model:value="note"
          class="note-input"
          placeholder="今天想记住什么？"
          :auto-size="{ minRows: 6, maxRows: 16 }"
          :maxlength="5000"
          show-count
        />
      </section>

      <section class="surface meta-card">
        <div class="meta-item">
          <span class="meta-label">心情</span>
          <a-select
            v-model:value="mood"
            :options="moodOptions"
            placeholder="今天的心情"
            allow-clear
            style="min-width: 160px"
          />
        </div>
        <div class="meta-item grow">
          <span class="meta-label">标签</span>
          <a-select
            v-model:value="tags"
            mode="tags"
            :token-separators="[',', '，', ' ']"
            placeholder="输入后回车，例如：散步、江边"
            style="width: 100%"
            :max-tag-count="8"
          />
        </div>
      </section>

      <section class="surface photo-card">
        <div class="row-between">
          <div>
            <strong>照片与视频</strong>
            <span class="muted photo-hint">共 {{ photos.length }} 个素材</span>
          </div>
          <div class="photo-actions">
            <a-button :loading="uploading" @click="triggerUpload">上传</a-button>
            <a-button @click="openImmich">从 Immich 导入</a-button>
          </div>
        </div>
        <p class="muted paste-hint">支持 JPG/PNG/WebP/GIF/HEIC/AVIF 与常见视频；可直接 Ctrl/Cmd+V 粘贴截图</p>
        <div v-if="uploading" class="upload-progress">
          <a-progress :percent="uploadPercent" size="small" />
        </div>

        <PhotoGrid
          v-if="photos.length"
          :photos="photos"
          editable
          class="photo-grid-block"
          @cover="setCover"
          @remove="removePhoto"
        />
        <a-empty v-else description="还没有照片，先记录一下今天吧" />

        <input
          ref="fileInput"
          type="file"
          accept="image/*,video/*,.heic,.heif,.avif,.mp4,.mov,.m4v,.webm,.mkv,.avi,.3gp"
          multiple
          hidden
          @change="onFilesSelected"
        />
      </section>
    </a-spin>

    <a-modal
      v-model:open="immichOpen"
      title="从 Immich 选择照片"
      width="760px"
      :footer="null"
    >
      <a-spin :spinning="immichLoading">
        <a-alert
          v-if="immichMessage"
          :message="immichMessage"
          type="info"
          show-icon
          style="margin-bottom: 12px"
        />
        <div v-if="immichAssets.length" class="immich-grid">
          <label
            v-for="asset in immichAssets"
            :key="asset.id"
            class="immich-item"
            :class="{ selected: selectedAssets.includes(asset.id), imported: asset.imported }"
          >
            <input
              v-model="selectedAssets"
              type="checkbox"
              :value="asset.id"
              :disabled="asset.imported"
            />
            <div class="immich-thumb">
              <img :src="immichThumb(asset.id)" :alt="asset.originalFileName" loading="lazy" />
            </div>
            <span class="immich-name">{{ asset.originalFileName || asset.id.slice(0, 8) }}</span>
            <span v-if="asset.imported" class="immich-flag">已导入</span>
          </label>
        </div>
        <a-empty v-else description="这一天在 Immich 里没有找到照片" />
        <div class="row-between" style="margin-top: 16px">
          <span class="muted">已选 {{ selectedAssets.length }} 张</span>
          <a-button
            type="primary"
            :disabled="!selectedAssets.length"
            :loading="immichImporting"
            @click="importSelected"
          >
            导入所选
          </a-button>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup>
import { Modal, message } from 'antdv-next'
import dayjs from 'dayjs'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'

import { entryApi, immichApi, photoApi } from '@/api/api'
import PhotoGrid from '@/components/PhotoGrid.vue'
import { draftKey, relativeDay, today } from '@/utils'

const route = useRoute()
const router = useRouter()
const store = useStore()

const date = ref(route.query.date || today())
const entry = ref(null)
const photos = ref([])
const note = ref('')
const mood = ref(null)
const tags = ref([])
const streak = ref(0)
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const uploadPercent = ref(0)
const fileInput = ref(null)
const dirty = ref(false)

const immichOpen = ref(false)
const immichLoading = ref(false)
const immichImporting = ref(false)
const immichMessage = ref('')
const immichAssets = ref([])
const selectedAssets = ref([])

const dateValue = computed(() => dayjs(date.value))
const moodOptions = computed(() =>
  (store.state.dict.groups.MOOD || []).map((item) => ({ label: item.name, value: item.name })),
)

watch([note, mood, tags], () => {
  saveDraft()
  dirty.value = true
})

watch(
  () => route.query.date,
  (value) => {
    if (value && value !== date.value) {
      date.value = value
      load()
    }
  },
)

function saveDraft() {
  const user = store.state.auth.userInfo
  if (!user) return
  localStorage.setItem(
    draftKey(user.id, date.value),
    JSON.stringify({ note: note.value, mood: mood.value, tags: tags.value }),
  )
}

function clearDraft() {
  const user = store.state.auth.userInfo
  if (user) localStorage.removeItem(draftKey(user.id, date.value))
}

function readDraft() {
  const user = store.state.auth.userInfo
  if (!user) return null
  try {
    return JSON.parse(localStorage.getItem(draftKey(user.id, date.value)) || 'null')
  } catch {
    return null
  }
}

async function load() {
  loading.value = true
  dirty.value = false
  try {
    const [entryData, unattached] = await Promise.all([
      entryApi.get(date.value),
      photoApi.list({ start: date.value, end: date.value, unattached: true }),
    ])
    entry.value = entryData || null
    note.value = entryData?.note || ''
    mood.value = entryData?.mood || null
    tags.value = (entryData?.tags || []).map((tag) => tag.name)

    const attached = entryData?.photos || []
    const map = new Map()
    ;[...attached, ...(unattached || [])].forEach((photo) => map.set(photo.id, photo))
    photos.value = [...map.values()]

    const draft = readDraft()
    if (draft && !entryData?.note && draft.note) {
      note.value = draft.note
      mood.value = draft.mood || mood.value
      tags.value = draft.tags?.length ? draft.tags : tags.value
      message.info('已恢复上次未保存的草稿')
    }

    const year = Number(date.value.slice(0, 4))
    try {
      const calendar = await entryApi.calendar({ year })
      streak.value = calendar.totals.currentStreak || 0
    } catch {
      streak.value = 0
    }
    dirty.value = false
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const payload = {
      entryDate: date.value,
      note: note.value,
      mood: mood.value || null,
      tags: tags.value,
      photoIds: photos.value.map((photo) => photo.id),
      coverPhotoId: photos.value.find((photo) => photo.isCover)?.id || null,
      version: entry.value?.version,
    }
    const saved = await entryApi.save(payload)
    entry.value = saved
    photos.value = (saved.photos || []).concat(
      photos.value.filter((photo) => !saved.photos?.some((item) => item.id === photo.id)),
    )
    clearDraft()
    dirty.value = false
    message.success('已保存今天的记录')
  } catch (error) {
    if (error?.code === 1009) {
      message.warning('记录已在别处修改，已为你刷新')
      await load()
    }
  } finally {
    saving.value = false
  }
}

function onDateChange(value) {
  if (!value) return
  const next = value.format('YYYY-MM-DD')
  date.value = next
  router.replace({ path: route.path, query: { date: next } })
  load()
}

function triggerUpload() {
  fileInput.value?.click()
}

async function onFilesSelected(event) {
  const files = [...(event.target.files || [])]
  event.target.value = ''
  await uploadFiles(files)
}

function clipboardFileName(file, fallbackExt = 'png') {
  if (file.name && file.name !== 'image.png') return file.name
  const ext = (file.type.split('/')[1] || fallbackExt).replace('jpeg', 'jpg')
  return `截图-${dayjs().format('YYYYMMDD-HHmmss')}.${ext}`
}

async function uploadFiles(files) {
  if (!files.length || uploading.value) return
  uploading.value = true
  uploadPercent.value = 0
  try {
    const form = new FormData()
    files.forEach((file) => form.append('files[]', file))
    form.append('entryDate', date.value)
    const result = await photoApi.upload(form, {
      onUploadProgress: (event) => {
        if (event.total) uploadPercent.value = Math.round((event.loaded / event.total) * 100)
      },
    })
    if (result.errors?.length) {
      message.warning(result.errors.map((item) => `${item.filename}: ${item.reason}`).join('；'))
    }
    message.success(`已上传 ${result.photos.length} 个文件`)
    await load()
  } finally {
    uploading.value = false
    uploadPercent.value = 0
  }
}

function onPaste(event) {
  const items = event.clipboardData?.items || []
  const files = []
  for (const item of items) {
    if (item.kind !== 'file' || !item.type.startsWith('image/')) continue
    const file = item.getAsFile()
    if (!file) continue
    files.push(
      new File([file], clipboardFileName(file), {
        type: file.type || 'image/png',
        lastModified: Date.now(),
      }),
    )
  }
  if (!files.length) return
  event.preventDefault()
  uploadFiles(files)
}

function setCover(photo) {
  photoApi.update({ id: photo.id, isCover: true }).then(() => {
    photos.value = photos.value.map((item) => ({ ...item, isCover: item.id === photo.id }))
    if (entry.value) {
      entry.value.photos = (entry.value.photos || []).map((item) => ({
        ...item,
        isCover: item.id === photo.id,
      }))
    }
    message.success('已设为封面')
  })
}

function removePhoto(photo) {
  Modal.confirm({
    title: '删除这张照片？',
    content: '只移除日记中的引用，不会删除 Immich 里的原文件。',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await photoApi.remove(photo.id)
      photos.value = photos.value.filter((item) => item.id !== photo.id)
      if (entry.value) {
        entry.value.photos = (entry.value.photos || []).filter((item) => item.id !== photo.id)
      }
      message.success('已移除')
    },
  })
}

function removeEntry() {
  Modal.confirm({
    title: '删除这一天的记录？',
    content: '文字、标签与封面会删除，照片引用会保留。',
    okText: '删除',
    okType: 'danger',
    onOk: async () => {
      await entryApi.remove(date.value)
      message.success('记录已删除')
      await load()
    },
  })
}

async function openImmich() {
  immichOpen.value = true
  immichLoading.value = true
  selectedAssets.value = []
  immichMessage.value = ''
  try {
    const status = await immichApi.status()
    if (!status.enabled) {
      immichMessage.value = 'Immich 未配置，无法导入照片。'
      immichAssets.value = []
      return
    }
    if (!status.available) {
      immichMessage.value = status.message || 'Immich 暂时不可用，请稍后重试。'
    }
    immichAssets.value = await immichApi.assets(date.value)
  } catch (error) {
    immichMessage.value = error?.message || '读取 Immich 失败'
  } finally {
    immichLoading.value = false
  }
}

function immichThumb(assetId) {
  return `/immich/api/assets/${assetId}/thumbnail?size=thumbnail`
}

async function importSelected() {
  immichImporting.value = true
  try {
    const result = await immichApi.import({ date: date.value, assetIds: selectedAssets.value })
    message.success(`已导入 ${result.imported} 张照片`)
    immichOpen.value = false
    await load()
  } finally {
    immichImporting.value = false
  }
}

function onKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault()
    save()
  }
}

function onBeforeUnload(event) {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}

onBeforeRouteLeave(() => {
  if (!dirty.value) return true
  return window.confirm('有未保存的修改，确定离开吗？')
})

onMounted(() => {
  load()
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('beforeunload', onBeforeUnload)
  window.addEventListener('paste', onPaste)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('beforeunload', onBeforeUnload)
  window.removeEventListener('paste', onPaste)
})
</script>

<style scoped lang="less">
.today-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.today-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.date-block {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.relative {
  color: var(--app-text-2);
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.note-input {
  font-size: 16px;
  line-height: 1.8;
  resize: none;
}

.meta-card {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 10px;

  &.grow {
    flex: 1;
    min-width: 240px;
  }
}

.meta-label {
  color: var(--app-text-3);
  font-size: 13px;
  white-space: nowrap;
}

.photo-hint {
  margin-left: 8px;
  font-size: 12px;
}

.paste-hint {
  margin: 10px 0 0;
  font-size: 12px;
}

.photo-actions {
  display: flex;
  gap: 8px;
}

.upload-progress {
  margin-top: 12px;
}

.photo-grid-block {
  margin-top: 16px;
}

.immich-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  max-height: 56vh;
  overflow: auto;
}

.immich-item {
  position: relative;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  padding: 6px;
  cursor: pointer;
  background: var(--app-bg-elevated);

  &.selected {
    border-color: var(--app-primary);
    box-shadow: 0 0 0 2px var(--app-primary-weak);
  }

  &.imported {
    opacity: 0.55;
    cursor: not-allowed;
  }

  input {
    position: absolute;
    top: 10px;
    left: 10px;
    z-index: 1;
  }
}

.immich-thumb {
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: var(--app-bg-body);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.immich-name {
  display: block;
  font-size: 11px;
  color: var(--app-text-3);
  margin-top: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.immich-flag {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--app-primary);
  color: #fff;
}

@media (max-width: 768px) {
  .meta-card {
    flex-direction: column;
    gap: 12px;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
