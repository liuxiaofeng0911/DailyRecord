import { Get, Post, Upload } from './axios'

export const authApi = {
  publicKey: () => Get('/auth/publicKey'),
  register: (payload) => Post('/auth/register', payload, { silent: true }),
  login: (payload) => Post('/auth/login', payload, { silent: true }),
  logout: () => Post('/auth/logout'),
  me: () => Post('/auth/me'),
  changePassword: (payload) => Post('/auth/changePassword', payload),
  sessions: () => Post('/auth/session/list'),
  revokeSession: (id) => Post('/auth/session/revoke', { id }),
  revokeAll: () => Post('/auth/session/revokeAll'),
}

export const entryApi = {
  list: (payload) => Post('/entry/list', payload),
  get: (date) => Post('/entry/get', { date }),
  save: (payload) => Post('/entry/save', payload),
  remove: (entryDate) => Post('/entry/delete', { entryDate }),
  calendar: (payload) => Post('/entry/calendar', payload),
  history: (payload) => Post('/entry/history', payload),
}

export const photoApi = {
  upload: (formData, config) => Upload('/photo/upload', formData, config),
  list: (payload) => Post('/photo/list', payload),
  update: (payload) => Post('/photo/update', payload),
  remove: (id) => Post('/photo/delete', { id }),
  describe: (id) => Post('/photo/describe', { id }),
  trashList: (payload = {}) => Post('/photo/trash/list', payload),
  trashRestore: (ids) => Post('/photo/trash/restore', { ids }),
  trashPurge: (ids) => Post('/photo/trash/purge', { ids }),
  thumbnail: (id) => `/api/photo/thumbnail/${id}`,
  original: (id) => `/api/photo/original/${id}`,
}

export const immichApi = {
  status: () => Post('/immich/status'),
  credentialGet: () => Post('/immich/credential/get'),
  credentialRetry: () => Post('/immich/credential/retry'),
  assets: (date) => Post('/immich/assets', { date }),
  import: (payload) => Post('/immich/import', payload),
}

export const statsApi = {
  overview: (year) => Post('/stats/overview', { year }),
}

export const tagApi = {
  list: () => Post('/tag/list'),
  suggest: () => Post('/tag/suggest'),
  save: (payload) => Post('/tag/save', payload),
}

export const exportApi = {
  run: (payload) => Post('/export', payload),
}

export const searchApi = {
  run: (payload) => Post('/search', payload),
}

export const systemApi = {
  userList: (payload) => Post('/system/user/list', payload),
  userGet: (id) => Post('/system/user/get', { id }),
  userSave: (payload) => Post('/system/user/save', payload),
  userResetPassword: (payload) => Post('/system/user/resetPassword', payload),
  userDelete: (id) => Post('/system/user/delete', { id }),
  roleList: () => Post('/system/role/list', {}),
  roleSave: (payload) => Post('/system/role/save', payload),
  roleMenus: (roleId) => Post('/system/role/menus', { roleId }),
  roleMenusSave: (payload) => Post('/system/role/menus/save', payload),
  orgTree: () => Post('/system/org/tree'),
  orgSave: (payload) => Post('/system/org/save', payload),
  orgDelete: (id) => Post('/system/org/delete', { id }),
  orgMembers: (id) => Post('/system/org/members', { id }),
  orgMembersSave: (payload) => Post('/system/org/members/save', payload),
  orgShareSwitch: (payload) => Post('/system/org/shareSwitch', payload),
  menuTree: () => Post('/system/menu/tree'),
  menuSave: (payload) => Post('/system/menu/save', payload),
  menuDelete: (id) => Post('/system/menu/delete', { id }),
  dictList: (codeid) => Post('/system/dict/list', { codeid }),
  dictSave: (payload) => Post('/system/dict/save', payload),
  switchGet: () => Post('/system/switch/get'),
  switchSave: (payload) => Post('/system/switch/save', payload),
  inviteList: () => Post('/system/invite/list'),
  inviteCreate: (payload) => Post('/system/invite/create', payload),
}

export const orgShareApi = {
  members: (payload) => Post('/org-share/members', payload),
  entries: (payload) => Post('/org-share/entries', payload),
  myOrgs: () => Post('/org-share/my/orgs'),
  myConfig: (orgId) => Post('/org-share/my/config/get', orgId ? { orgId } : {}),
  myConfigSave: (payload) => Post('/org-share/my/config/save', payload),
  myEntries: (payload) => Post('/org-share/my/entries', payload),
}
