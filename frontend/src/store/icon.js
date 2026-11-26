/**
 * 图标自动匹配：导航固定 → 情绪字典 → 标签关键词 → 类型默认 → 稳定哈希回退。
 * 纯函数，不请求后端，保证同一名称每次得到同一图标。
 */

export const NAV_ICONS = {
  '/Main/Today': 'lucide:calendar-heart',
  '/Main/Timeline': 'lucide:history',
  '/Main/Stats': 'lucide:chart-column',
  '/System/Account': 'lucide:user-round',
  '/System/Settings': 'lucide:settings',
  '/System/User': 'lucide:users',
  '/System/Role': 'lucide:shield-check',
  '/System/Organization': 'lucide:building-2',
  '/System/Menu': 'lucide:list-tree',
  '/System/BaseCode': 'lucide:book-open',
}

const MOOD_ICONS = {
  开心: 'lucide:smile',
  兴奋: 'lucide:sparkles',
  愉悦: 'lucide:laugh',
  平静: 'lucide:waves',
  复杂: 'lucide:circle-help',
  放松: 'lucide:sofa',
  疲惫: 'lucide:battery-low',
  麻木: 'lucide:meh',
  低落: 'lucide:cloud-rain',
  怅然: 'lucide:cloud-drizzle',
  委屈: 'lucide:frown',
  烦躁: 'lucide:flame',
  焦虑: 'lucide:activity',
}

const TAG_KEYWORDS = [
  [/散步|走路|步行|徒步/, 'lucide:footprints'],
  [/美食|吃|饭|早餐|午餐|晚餐|夜宵/, 'lucide:utensils'],
  [/旅行|旅游|出游|出差/, 'lucide:plane'],
  [/阅读|读书|看书|书/, 'lucide:book-open'],
  [/运动|跑步|健身|锻炼|瑜伽/, 'lucide:dumbbell'],
  [/家人|家庭|父母|孩子|宝宝/, 'lucide:users'],
  [/工作|加班|上班|会议/, 'lucide:briefcase'],
  [/音乐|唱歌|演出/, 'lucide:music'],
  [/电影|影片|观影/, 'lucide:film'],
  [/天气|下雨|晴天|雨天/, 'lucide:cloud-sun'],
  [/咖啡|下午茶|喝茶/, 'lucide:coffee'],
  [/购物|买/, 'lucide:shopping-bag'],
  [/宠物|猫|狗/, 'lucide:cat'],
  [/写|记录|日记/, 'lucide:pen-line'],
]

const FALLBACK_ICONS = [
  'lucide:sparkles',
  'lucide:sun',
  'lucide:star',
  'lucide:leaf',
  'lucide:cloud',
  'lucide:heart',
  'lucide:map-pin',
  'lucide:clock',
  'lucide:camera',
  'lucide:flower-2',
  'lucide:compass',
  'lucide:moon',
]

export function stableHash(value = '') {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  }
  return hash
}

export function resolveNavIcon(path) {
  return NAV_ICONS[path] || 'lucide:sparkles'
}

export function resolveMoodIcon(name) {
  if (!name) return 'lucide:smile'
  return MOOD_ICONS[name] || 'lucide:smile'
}

export function resolveTagIcon(name, override) {
  if (override) return override
  const text = (name || '').trim()
  for (const [pattern, icon] of TAG_KEYWORDS) {
    if (pattern.test(text)) return icon
  }
  return FALLBACK_ICONS[stableHash(text) % FALLBACK_ICONS.length]
}

export const TAG_ICON_OPTIONS = [
  'lucide:footprints',
  'lucide:utensils',
  'lucide:plane',
  'lucide:book-open',
  'lucide:dumbbell',
  'lucide:users',
  'lucide:briefcase',
  'lucide:music',
  'lucide:film',
  'lucide:cloud-sun',
  'lucide:coffee',
  'lucide:shopping-bag',
  'lucide:cat',
  'lucide:pen-line',
  'lucide:leaf',
  'lucide:heart',
]
