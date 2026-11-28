<template>
  <a-layout class="app-layout">
    <a-layout-sider
      v-if="!mobile"
      v-model:collapsed="collapsed"
      :width="220"
      :collapsed-width="64"
      collapsible
      :trigger="null"
      class="app-sider"
    >
      <div class="brand">
        <span class="brand-mark"><AppIcon name="lucide:calendar-heart" :size="17" /></span>
        <span v-if="!collapsed" class="brand-name">每日记录</span>
      </div>
      <a-menu
        :selected-keys="selectedKeys"
        mode="inline"
        :items="menuItems"
        :inline-collapsed="collapsed"
        @click="onMenuClick"
      />
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="app-header">
        <div class="header-left">
          <button
            v-if="!mobile"
            type="button"
            class="icon-button"
            aria-label="折叠菜单"
            @click="toggleCollapse"
          >
            ☰
          </button>
          <strong class="header-title">{{ pageTitle }}</strong>
        </div>
        <div class="header-right">
          <a-tooltip title="功能清单与使用说明">
            <button
              type="button"
              class="icon-button help-entry"
              aria-label="功能清单"
              @click="helpOpen = true"
            >
              <AppIcon name="lucide:circle-help" :size="18" />
            </button>
          </a-tooltip>
          <ThemeSelect />
          <a-dropdown :menu="userMenu" trigger="click">
            <button type="button" class="user-button" :aria-label="`${username} 的菜单`">
              <span class="avatar" role="img" :aria-label="`${username}头像`">
                <img v-if="avatarUrl" :src="avatarUrl" alt="" />
                <template v-else>{{ initial }}</template>
              </span>
              <span v-if="!mobile" class="user-name">{{ username }}</span>
            </button>
          </a-dropdown>
        </div>
      </a-layout-header>

      <a-layout-content class="app-content">
        <router-view v-slot="{ Component }">
          <keep-alive :max="5">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </a-layout-content>
    </a-layout>

    <a-modal
      v-model:open="helpOpen"
      title="功能清单"
      :footer="null"
      :width="mobile ? '92%' : 640"
    >
      <div class="help-list">
        <section v-for="group in helpSections" :key="group.title" class="help-group">
          <h4>{{ group.title }}</h4>
          <ul>
            <li v-for="line in group.items" :key="line">{{ line }}</li>
          </ul>
        </section>
      </div>
    </a-modal>

    <nav v-if="mobile" class="mobile-tabs">
      <button
        v-for="item in mobileTabs"
        :key="item.key"
        type="button"
        :class="{ active: selectedKeys.includes(item.key) }"
        @click="router.push(item.path)"
      >
        <AppIcon :name="item.icon" :size="18" />
        {{ item.label }}
      </button>
    </nav>
  </a-layout>
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'

import AppIcon from '@/components/AppIcon.vue'
import ThemeSelect from '@/components/ThemeSelect.vue'
import { resolveNavIcon } from '@/store/icon'

const store = useStore()
const router = useRouter()
const route = useRoute()
const helpOpen = ref(false)

const helpSections = [
  {
    title: '今天',
    items: [
      '写正文、选心情、加标签，保存后成为这一天的一条记录。',
      '「上传」支持照片和视频，可多选，也能直接粘贴截图；「拍照」仅手机端显示。',
      '「AI 注释」开启后，新上传的照片/视频会自动生成描述和关键词，并追加到当天正文；关闭后可用时间线的「AI 补注释」补做。',
      '「从照片库导入」用于把 Immich 里已有（如手机自动备份）的当天照片直接加入记录，无需重复上传。',
      '「回收站」保存已删除的照片，可在保留期内恢复或彻底删除。',
    ],
  },
  {
    title: '时间线',
    items: [
      '按月回看每天的记录，点击整行进入当天编辑。',
      '支持关键词、情绪、标签和日期范围筛选，预设按钮可快速切到本月/今年/近 30 天。',
      '「AI 补注释」按日期范围给缺注释的素材补生成描述。',
      '「修改历史」查看这条记录保存后的字段级修改留痕。',
    ],
  },
  {
    title: '统计',
    items: [
      '查看记录天数、照片数量、连续记录天数与年度热力图。',
      '月度签到率、情绪分布、常用标签辅助回顾，点击方块或柱子可跳到对应日期。',
    ],
  },
  {
    title: '共享',
    items: [
      '组织内需要「我允许对方看」和「我想看对方」同时勾选，才会看到彼此的记录。',
      '组织共享开关可被所有者随时暂停，暂停期间配置会保留。',
      '所有者可以直接查看所选组织内全部成员的记录，照片可点开大图。',
    ],
  },
  {
    title: '账户与系统',
    items: [
      '账户设置：修改密码、查看/撤销登录设备、调整标签图标、导出 JSON/Markdown。',
      '系统设置（仅所有者）：注册模式、邀请码、上传大小上限、回收站保留天数与清理时间、AI 总开关。',
      '用户/角色/组织/菜单/字典管理仅所有者可见。',
    ],
  },
]

const collapsed = computed({
  get: () => store.state.app.collapsed,
  set: (value) => store.commit('app/setCollapsed', value),
})
const mobile = computed(() => store.state.app.mobile)
const username = computed(() => store.state.auth.userInfo?.username || '我')
const initial = computed(() => (username.value || '我').slice(0, 1))
const avatarUrl = computed(() => store.state.auth.userInfo?.avatar || '')
const pageTitle = computed(() => route.meta?.title || '今天')

const selectedKeys = computed(() => {
  if (route.path.startsWith('/System')) {
    return [`/System/${route.name === 'Account' ? 'Account' : route.path.split('/').pop()}`]
  }
  return [route.path]
})

const FALLBACK_MENUS = [
  { id: 'f1', name: '今天', path: '/Main/Today', icon: 'lucide:calendar-heart', children: [] },
  { id: 'f2', name: '时间线', path: '/Main/Timeline', icon: 'lucide:history', children: [] },
  { id: 'f3', name: '统计', path: '/Main/Stats', icon: 'lucide:chart-column', children: [] },
  { id: 'f5', name: '共享', path: '/Main/Share', icon: 'lucide:share-2', children: [] },
  {
    id: 'f4',
    name: '账户设置',
    path: '/System/Account',
    icon: 'lucide:user-round',
    children: [],
  },
]

function menuIcon(node) {
  return h(AppIcon, { name: node.icon || resolveNavIcon(node.path), size: 18 })
}

function toMenuItems(nodes) {
  return (nodes || [])
    .filter((node) => node.path || node.children?.length)
    .map((node) => {
      const item = {
        key: node.path || `menu:${node.id}`,
        label: node.name,
        icon: menuIcon(node),
      }
      if (node.children?.length) item.children = toMenuItems(node.children)
      return item
    })
}

const menuItems = computed(() => {
  const menus = store.state.auth.menus
  return toMenuItems(menus.length ? menus : FALLBACK_MENUS)
})

function flattenMenus(nodes) {
  return (nodes || []).flatMap((node) => [
    ...(node.path ? [node] : []),
    ...flattenMenus(node.children),
  ])
}

// 移动端底部导航优先放业务页；账户设置收进右上角头像菜单
const MOBILE_ORDER = ['/Main/Today', '/Main/Timeline', '/Main/Stats', '/Main/Share']
const MOBILE_HIDDEN = new Set(['/System/Account'])

const mobileTabs = computed(() => {
  const menus = store.state.auth.menus
  const leaves = flattenMenus(menus.length ? menus : FALLBACK_MENUS)
  const byPath = new Map(leaves.map((node) => [node.path, node]))
  const ordered = MOBILE_ORDER.filter((path) => byPath.has(path)).map((path) =>
    byPath.get(path),
  )
  const rest = leaves.filter(
    (node) => !MOBILE_ORDER.includes(node.path) && !MOBILE_HIDDEN.has(node.path),
  )
  return [...ordered, ...rest].slice(0, 4).map((node) => ({
    key: node.path,
    label: node.name,
    path: node.path,
    icon: node.icon || resolveNavIcon(node.path),
  }))
})

const userMenu = computed(() => {
  const items = []
  // 手机端侧栏隐藏、底部 Tab 只放 4 个，其余菜单收进头像下拉，保证系统页可达
  if (mobile.value) {
    const tabPaths = new Set(mobileTabs.value.map((item) => item.path))
    const menus = store.state.auth.menus.length ? store.state.auth.menus : FALLBACK_MENUS
    const extra = flattenMenus(menus).filter(
      (node) =>
        node.path && !tabPaths.has(node.path) && !MOBILE_HIDDEN.has(node.path),
    )
    if (extra.length) {
      items.push(
        ...extra.map((node) => ({
          key: node.path,
          label: node.name,
          icon: () => h(AppIcon, { name: node.icon || resolveNavIcon(node.path), size: 16 }),
        })),
        { type: 'divider' },
      )
    }
  }
  items.push(
    { key: 'account', label: '账户设置' },
    { type: 'divider' },
    { key: 'logout', label: '退出登录' },
  )
  return { items, onClick: onUserMenu }
})

function toggleCollapse() {
  store.commit('app/setCollapsed', !store.state.app.collapsed)
}

function onMenuClick({ key }) {
  if (String(key).startsWith('/')) router.push(key)
}

async function onUserMenu({ key }) {
  if (String(key).startsWith('/')) {
    router.push(key)
    return
  }
  if (key === 'account') {
    router.push('/System/Account')
    return
  }
  if (key === 'logout') {
    await store.dispatch('auth/logout')
    router.push('/Login')
  }
}

function syncViewport() {
  store.commit('app/setMobile', window.innerWidth < 768)
}

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
  store.dispatch('dict/load')
  store.dispatch('auth/loadMenus')
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport)
})
</script>

<style scoped lang="less">
.app-layout {
  min-height: 100vh;
  background: var(--app-bg-body);
}

.app-sider {
  border-right: 1px solid var(--app-border);
  background: var(--app-bg-container);
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid var(--app-border);
}

.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #2090ff, #7e57ff);
}

.brand-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--app-text-1);
  white-space: nowrap;
}

.app-header {
  height: 56px;
  line-height: 1;
  padding: 0 16px;
  padding-left: max(16px, env(safe-area-inset-left));
  padding-right: max(16px, env(safe-area-inset-right));
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--app-bg-container);
  border-bottom: 1px solid var(--app-border);
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 15px;
  color: var(--app-text-1);
}

.icon-button {
  border: none;
  background: transparent;
  color: var(--app-text-2);
  font-size: 16px;
  cursor: pointer;
}

.help-entry {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 8px;
  transition: background 0.2s;

  &:hover {
    background: var(--app-bg-elevated);
  }
}

.user-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px 8px;
  border: none;
  border-radius: var(--radius-pill);
  background: transparent;
  cursor: pointer;
  color: var(--app-text-1);
  line-height: 1;
  transition: background 0.2s;

  &:hover {
    background: var(--app-bg-elevated);
  }
}

.avatar {
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  line-height: 1;
  background: linear-gradient(135deg, var(--app-primary), #7e57ff);
  color: #fff;
  font-size: 13px;
  font-weight: 600;

  img {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }
}

.user-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.app-content {
  background: var(--app-bg-body);
  min-height: calc(100vh - 56px);
}

@media (max-width: 768px) {
  .app-content {
    min-height: calc(100dvh - 56px);
  }
}

.help-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-height: 62vh;
  overflow: auto;
}

.help-group {
  h4 {
    margin: 0 0 6px;
    font-size: 13px;
    color: var(--app-text-1);
  }

  ul {
    margin: 0;
    padding-left: 18px;
    color: var(--app-text-2);
    font-size: 13px;
    line-height: 1.8;
  }
}

.mobile-tabs {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: auto;
  min-height: 58px;
  padding-bottom: env(safe-area-inset-bottom);
  display: flex;
  background: var(--app-bg-container);
  border-top: 1px solid var(--app-border);
  z-index: 20;

  button {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    min-height: 56px;
    border: none;
    background: transparent;
    color: var(--app-text-3);
    font-size: 11px;

    &.active {
      color: var(--app-primary);
    }
  }
}
</style>
