<template>
  <div class="card">
    <h2 class="mb-1">客制化配置</h2>
    <p class="text-sm text-gray-500 mb-5">每个方案拥有独立的合法按键名称与键值映射，激活方案在运行时生效。</p>
    <section class="config-section mb-4">
      <div class="scheme-header">
        <div class="scheme-tabs-wrap">
          <div class="scheme-tabs">
            <button
              v-for="s in schemes"
              :key="s.name"
              :class="['scheme-tab', { 'scheme-tab-selected': s.name === selectedScheme }]"
              @click="selectScheme(s.name)"
            >
              <span class="scheme-tab-name">{{ s.name }}</span>
              <span v-if="s.is_active" class="scheme-active-badge">激活</span>
            </button>
          </div>
          <p v-if="schemes.length === 0" class="text-sm text-gray-400">暂无方案，请新建。</p>
        </div>
        <div class="scheme-btns">
          <button class="btn btn-secondary btn-sm" @click="showCreateModal = true">＋ 新建</button>
          <button class="btn btn-secondary btn-sm" @click="showDuplicateModal = true" :disabled="!selectedScheme">复制</button>
          <button class="btn btn-danger btn-sm" @click="confirmDeleteScheme" :disabled="!selectedScheme || schemes.length <= 1">删除</button>
        </div>
      </div>
      <div v-if="selectedScheme" class="scheme-status-row">
        <span class="text-sm text-gray-500">
          正在编辑：<strong>{{ selectedScheme }}</strong>
        </span>
        <button
          v-if="activeScheme !== selectedScheme"
          class="btn btn-primary btn-sm"
          @click="activateCurrentScheme"
        >
          设为激活方案
        </button>
        <span v-else class="active-hint">✓ 当前已激活</span>
      </div>
    </section>
    <template v-if="selectedScheme">
      <section class="config-section mb-4">
        <div class="section-header">
          <div>
            <h3 class="section-title">合法按键名称</h3>
            <p class="section-desc">Excel 校验及按键监听中允许使用的按键集合。修改后立即生效于后续校验。</p>
          </div>
          <div class="section-actions">
            <button class="btn btn-secondary btn-sm" @click="confirmReset" :disabled="loading">恢复默认</button>
            <button class="btn btn-primary btn-sm" @click="saveKeys" :disabled="loading || !dirty">
              {{ loading ? '保存中…' : '保存更改' }}
            </button>
          </div>
        </div>
        <div v-if="statusMsg" :class="['status-bar', statusType]">{{ statusMsg }}</div>
        <div class="add-row">
          <input
            v-model="newKey"
            class="form-input add-input"
            placeholder="输入新按键名称，如 MY_KEY"
            @keydown.enter.prevent="addKey"
            @input="newKey = newKey.toUpperCase()"
            maxlength="40"
          />
          <button class="btn btn-primary btn-sm" @click="addKey" :disabled="!newKey.trim()">添加</button>
        </div>
        <div v-if="keys.length" class="keys-grid">
          <span
            v-for="key in keys"
            :key="key"
            class="key-tag"
            :class="{ 'key-tag-new': addedKeys.has(key) }"
          >
            {{ key }}
            <button class="tag-remove" @click="removeKey(key)" title="移除">×</button>
          </span>
        </div>
        <p v-else class="text-sm text-gray-400 mt-4">暂无按键，请添加。</p>
        <p class="key-count">共 {{ keys.length }} 个按键</p>
      </section>
      <section class="config-section">
        <div class="section-header">
          <div>
            <h3 class="section-title">按键键值映射</h3>
            <p class="section-desc">定义每个按键名称对应的 ADB keycode 数值。蓝色行为自定义覆盖，其余为系统默认。</p>
          </div>
          <div class="section-actions">
            <button class="btn btn-secondary btn-sm" @click="confirmResetCodes" :disabled="kcLoading">恢复默认</button>
          </div>
        </div>
        <div v-if="kcStatusMsg" :class="['status-bar', kcStatusType]">{{ kcStatusMsg }}</div>
        <div class="add-row mb-4">
          <input
            v-model="kcNewName"
            class="form-input add-input"
            placeholder="按键名，如 MY_KEY"
            @input="kcNewName = kcNewName.toUpperCase()"
            maxlength="40"
          />
          <input
            v-model.number="kcNewCode"
            class="form-input"
            style="width:100px;"
            type="number"
            min="0"
            placeholder="键值"
          />
          <button class="btn btn-primary btn-sm" @click="addKeyCode" :disabled="!kcNewName.trim() || kcNewCode === ''">添加/覆盖</button>
        </div>
        <div class="kc-table-wrap">
          <table class="kc-table">
            <thead>
              <tr>
                <th>按键名称</th>
                <th>键值 (keycode)</th>
                <th>类型</th>
                <th style="width:60px;"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="[name, code] in sortedKeyCodes"
                :key="name"
                :class="{ 'kc-custom': customOverrides[name] !== undefined }"
              >
                <td class="kc-name">{{ name }}</td>
                <td>
                  <span v-if="!editingKey || editingKey !== name" class="kc-code">{{ code }}</span>
                  <input
                    v-else
                    v-model.number="editingCode"
                    class="form-input kc-edit-input"
                    type="number"
                    min="0"
                    @keydown.enter="commitEdit(name)"
                    @keydown.escape="editingKey = null"
                  />
                </td>
                <td>
                  <span v-if="customOverrides[name] !== undefined" class="badge-custom">自定义</span>
                  <span v-else class="badge-default">默认</span>
                </td>
                <td class="kc-actions">
                  <template v-if="!editingKey || editingKey !== name">
                    <button class="act-btn" @click="startEdit(name, code)" title="编辑">✎</button>
                    <button
                      v-if="customOverrides[name] !== undefined"
                      class="act-btn act-del"
                      @click="deleteOverride(name)"
                      title="恢复默认"
                    >↩</button>
                  </template>
                  <template v-else>
                    <button class="act-btn act-ok" @click="commitEdit(name)" title="确认">✓</button>
                    <button class="act-btn" @click="editingKey = null" title="取消">✕</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="key-count">共 {{ sortedKeyCodes.length }} 条映射，{{ Object.keys(customOverrides).length }} 条自定义覆盖</p>
      </section>
    </template>
    <div v-if="showCreateModal" class="modal-backdrop" @click.self="showCreateModal = false">
      <div class="modal-box">
        <h4 class="modal-title">新建方案</h4>
        <input
          v-model="newSchemeName"
          class="form-input mt-3"
          placeholder="方案名称"
          maxlength="30"
          @keydown.enter="doCreateScheme"
          ref="createInput"
        />
        <div v-if="createError" class="status-bar error mt-2">{{ createError }}</div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showCreateModal = false">取消</button>
          <button class="btn btn-primary btn-sm" @click="doCreateScheme" :disabled="!newSchemeName.trim()">创建</button>
        </div>
      </div>
    </div>
    <div v-if="showDuplicateModal" class="modal-backdrop" @click.self="showDuplicateModal = false">
      <div class="modal-box">
        <h4 class="modal-title">复制方案「{{ selectedScheme }}」</h4>
        <input
          v-model="duplicateName"
          class="form-input mt-3"
          placeholder="新方案名称"
          maxlength="30"
          @keydown.enter="doDuplicateScheme"
        />
        <div v-if="duplicateError" class="status-bar error mt-2">{{ duplicateError }}</div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showDuplicateModal = false">取消</button>
          <button class="btn btn-primary btn-sm" @click="doDuplicateScheme" :disabled="!duplicateName.trim()">复制</button>
        </div>
      </div>
    </div>
    <div v-if="showDeleteConfirm" class="modal-backdrop" @click.self="showDeleteConfirm = false">
      <div class="modal-box">
        <h4 class="modal-title">确认删除方案？</h4>
        <p class="modal-body">将永久删除方案「<strong>{{ selectedScheme }}</strong>」及其所有配置，此操作不可撤销。</p>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showDeleteConfirm = false">取消</button>
          <button class="btn btn-danger btn-sm" @click="doDeleteScheme">确认删除</button>
        </div>
      </div>
    </div>
    <div v-if="showResetConfirm" class="modal-backdrop" @click.self="showResetConfirm = false">
      <div class="modal-box">
        <h4 class="modal-title">确认恢复默认？</h4>
        <p class="modal-body">将清除「{{ selectedScheme }}」中的自定义按键并还原为系统默认列表，此操作不可撤销。</p>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showResetConfirm = false">取消</button>
          <button class="btn btn-danger btn-sm" @click="doReset">确认恢复</button>
        </div>
      </div>
    </div>
    <div v-if="showResetCodesConfirm" class="modal-backdrop" @click.self="showResetCodesConfirm = false">
      <div class="modal-box">
        <h4 class="modal-title">确认恢复默认键值？</h4>
        <p class="modal-body">将清除「{{ selectedScheme }}」中的所有自定义键值并还原为系统默认映射表，此操作不可撤销。</p>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showResetCodesConfirm = false">取消</button>
          <button class="btn btn-danger btn-sm" @click="doResetCodes">确认恢复</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'

const schemes = ref([])
const activeScheme = ref('')
const selectedScheme = ref('')
const showCreateModal = ref(false)
const showDuplicateModal = ref(false)
const showDeleteConfirm = ref(false)
const newSchemeName = ref('')
const duplicateName = ref('')
const createError = ref('')
const duplicateError = ref('')
const createInput = ref(null)

async function fetchSchemes() {
  try {
    const res = await fetch('/api/customization/schemes')
    const data = await res.json()
    schemes.value = data.schemes || []
    activeScheme.value = data.active_scheme || ''
    if (!selectedScheme.value || !schemes.value.find(s => s.name === selectedScheme.value)) {
      selectedScheme.value = schemes.value[0]?.name || ''
    }
  } catch { }
}

function selectScheme(name) {
  if (selectedScheme.value === name) return
  selectedScheme.value = name
}

async function activateCurrentScheme() {
  const name = selectedScheme.value
  if (!name) return
  try {
    const res = await fetch(`/api/customization/schemes/${encodeURIComponent(name)}/activate`, { method: 'PUT' })
    if (!res.ok) return
    activeScheme.value = name
    schemes.value = schemes.value.map(s => ({ ...s, is_active: s.name === name }))
  } catch { }
}

async function doCreateScheme() {
  const name = newSchemeName.value.trim()
  if (!name) return
  createError.value = ''
  try {
    const res = await fetch('/api/customization/schemes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })
    const data = await res.json()
    if (!res.ok) { createError.value = data.detail || '创建失败'; return }
    showCreateModal.value = false
    newSchemeName.value = ''
    await fetchSchemes()
    selectedScheme.value = name
  } catch { createError.value = '请求失败' }
}

function confirmDeleteScheme() { showDeleteConfirm.value = true }

async function doDeleteScheme() {
  const name = selectedScheme.value
  showDeleteConfirm.value = false
  try {
    const res = await fetch(`/api/customization/schemes/${encodeURIComponent(name)}`, { method: 'DELETE' })
    const data = await res.json()
    if (!res.ok) return
    activeScheme.value = data.active_scheme || ''
    await fetchSchemes()
  } catch { }
}

async function doDuplicateScheme() {
  const newName = duplicateName.value.trim()
  if (!newName) return
  duplicateError.value = ''
  try {
    const res = await fetch(`/api/customization/schemes/${encodeURIComponent(selectedScheme.value)}/duplicate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName })
    })
    const data = await res.json()
    if (!res.ok) { duplicateError.value = data.detail || '复制失败'; return }
    showDuplicateModal.value = false
    duplicateName.value = ''
    await fetchSchemes()
    selectedScheme.value = newName
  } catch { duplicateError.value = '请求失败' }
}

watch(showCreateModal, async (v) => {
  if (v) { createError.value = ''; newSchemeName.value = ''; await nextTick(); createInput.value?.focus() }
})
watch(showDuplicateModal, (v) => { if (v) { duplicateError.value = ''; duplicateName.value = '' } })

const keys = ref([])
const newKey = ref('')
const loading = ref(false)
const dirty = ref(false)
const statusMsg = ref('')
const statusType = ref('info')
const showResetConfirm = ref(false)
const addedKeys = ref(new Set())
let statusTimer = null

function showStatus(msg, type = 'success') {
  statusMsg.value = msg
  statusType.value = type
  clearTimeout(statusTimer)
  statusTimer = setTimeout(() => { statusMsg.value = '' }, 3000)
}

async function fetchKeys() {
  if (!selectedScheme.value) return
  loading.value = true
  try {
    const res = await fetch(`/api/customization/schemes/${encodeURIComponent(selectedScheme.value)}/valid-keys`)
    const data = await res.json()
    keys.value = data.keys || []
    dirty.value = false
    addedKeys.value = new Set()
  } catch {
    showStatus('加载按键列表失败', 'error')
  } finally {
    loading.value = false
  }
}

function addKey() {
  const k = newKey.value.trim().toUpperCase()
  if (!k) return
  if (keys.value.includes(k)) { showStatus(`"${k}" 已存在`, 'warning'); return }
  keys.value = [...keys.value, k].sort()
  addedKeys.value = new Set([...addedKeys.value, k])
  newKey.value = ''
  dirty.value = true
}

function removeKey(key) {
  keys.value = keys.value.filter(k => k !== key)
  addedKeys.value.delete(key)
  dirty.value = true
}

async function saveKeys() {
  loading.value = true
  try {
    const res = await fetch(`/api/customization/schemes/${encodeURIComponent(selectedScheme.value)}/valid-keys`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keys: keys.value })
    })
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '保存失败') }
    const data = await res.json()
    keys.value = data.keys
    dirty.value = false
    addedKeys.value = new Set()
    showStatus('保存成功')
  } catch (e) {
    showStatus(e.message || '保存失败', 'error')
  } finally {
    loading.value = false
  }
}

function confirmReset() { showResetConfirm.value = true }
async function doReset() {
  showResetConfirm.value = false
  loading.value = true
  try {
    const res = await fetch(`/api/customization/schemes/${encodeURIComponent(selectedScheme.value)}/valid-keys/reset`, { method: 'POST' })
    const data = await res.json()
    keys.value = data.keys
    dirty.value = false
    addedKeys.value = new Set()
    showStatus('已恢复为默认按键列表')
  } catch { showStatus('恢复失败', 'error') } finally { loading.value = false }
}

const keyCodes = ref({})
const customOverrides = ref({})
const kcLoading = ref(false)
const kcStatusMsg = ref('')
const kcStatusType = ref('info')
const showResetCodesConfirm = ref(false)
const kcNewName = ref('')
const kcNewCode = ref('')
const editingKey = ref(null)
const editingCode = ref(0)
let kcTimer = null

function showKcStatus(msg, type = 'success') {
  kcStatusMsg.value = msg
  kcStatusType.value = type
  clearTimeout(kcTimer)
  kcTimer = setTimeout(() => { kcStatusMsg.value = '' }, 3000)
}

const sortedKeyCodes = computed(() =>
  Object.entries(keyCodes.value).sort(([a], [b]) => a.localeCompare(b))
)

async function fetchKeyCodes() {
  if (!selectedScheme.value) return
  kcLoading.value = true
  try {
    const res = await fetch(`/api/customization/schemes/${encodeURIComponent(selectedScheme.value)}/key-codes`)
    const data = await res.json()
    keyCodes.value = data.key_codes || {}
    customOverrides.value = data.custom_overrides || {}
  } catch {
    showKcStatus('加载键值映射失败', 'error')
  } finally {
    kcLoading.value = false
  }
}

async function addKeyCode() {
  const name = kcNewName.value.trim().toUpperCase()
  const code = Number(kcNewCode.value)
  if (!name || isNaN(code) || code < 0) return
  await saveOverride(name, code)
  kcNewName.value = ''
  kcNewCode.value = ''
}

function startEdit(name, code) { editingKey.value = name; editingCode.value = code }

async function commitEdit(name) {
  const code = Number(editingCode.value)
  if (isNaN(code) || code < 0) { showKcStatus('键值必须为非负整数', 'warning'); return }
  editingKey.value = null
  await saveOverride(name, code)
}

async function saveOverride(name, code) {
  const updated = { ...customOverrides.value, [name]: code }
  kcLoading.value = true
  try {
    const res = await fetch(`/api/customization/schemes/${encodeURIComponent(selectedScheme.value)}/key-codes`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key_codes: updated })
    })
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '保存失败') }
    const data = await res.json()
    keyCodes.value = data.key_codes
    customOverrides.value = data.custom_overrides
    showKcStatus('键值已保存')
  } catch (e) {
    showKcStatus(e.message || '保存失败', 'error')
  } finally {
    kcLoading.value = false
  }
}

async function deleteOverride(name) {
  kcLoading.value = true
  try {
    const res = await fetch(
      `/api/customization/schemes/${encodeURIComponent(selectedScheme.value)}/key-codes/${encodeURIComponent(name)}`,
      { method: 'DELETE' }
    )
    const data = await res.json()
    keyCodes.value = data.key_codes
    customOverrides.value = data.custom_overrides
    showKcStatus(`"${name}" 已还原为默认键值`)
  } catch {
    showKcStatus('删除失败', 'error')
  } finally {
    kcLoading.value = false
  }
}

function confirmResetCodes() { showResetCodesConfirm.value = true }
async function doResetCodes() {
  showResetCodesConfirm.value = false
  kcLoading.value = true
  try {
    const res = await fetch(
      `/api/customization/schemes/${encodeURIComponent(selectedScheme.value)}/key-codes/reset`,
      { method: 'POST' }
    )
    const data = await res.json()
    keyCodes.value = data.key_codes
    customOverrides.value = data.custom_overrides
    showKcStatus('已恢复为全部默认键值')
  } catch { showKcStatus('恢复失败', 'error') } finally { kcLoading.value = false }
}

watch(selectedScheme, (name) => {
  if (!name) return
  statusMsg.value = ''
  kcStatusMsg.value = ''
  dirty.value = false
  editingKey.value = null
  fetchKeys()
  fetchKeyCodes()
})

onMounted(async () => {
  await fetchSchemes()
  if (selectedScheme.value) {
    fetchKeys()
    fetchKeyCodes()
  }
})
</script>

<style scoped>
.scheme-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.scheme-tabs-wrap { flex: 1; min-width: 0; }
.scheme-tabs { display: flex; flex-wrap: wrap; gap: 6px; }
.scheme-tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 14px; border-radius: 9999px;
  border: 1px solid #e2e8f0; background: #f8fafc;
  font-size: 0.83rem; font-weight: 500; color: #475569;
  cursor: pointer; transition: all 0.15s;
}
.scheme-tab:hover { border-color: #94a3b8; background: #f1f5f9; }
.scheme-tab-selected { border-color: #0071e3; background: rgba(0,113,227,0.07); color: #0071e3; font-weight: 600; }
.scheme-active-badge {
  display: inline-block; padding: 1px 6px;
  background: #dcfce7; color: #15803d;
  border-radius: 9999px; font-size: 0.68rem; font-weight: 700;
}
.scheme-btns { display: flex; gap: 6px; flex-shrink: 0; }
.scheme-status-row {
  display: flex; align-items: center; gap: 12px;
  margin-top: 12px; padding-top: 10px;
  border-top: 1px solid rgba(226,232,240,0.7);
}
.active-hint { font-size: 0.8rem; color: #16a34a; font-weight: 600; }
.config-section {
  background: rgba(255,255,255,0.55);
  border: 1px solid rgba(226,232,240,0.85);
  border-radius: 20px; padding: 18px 20px 14px;
}
.section-header {
  display: flex; align-items: flex-start;
  justify-content: space-between; gap: 16px;
  margin-bottom: 16px; flex-wrap: wrap;
}
.section-title { font-size: 1rem; font-weight: 600; margin: 0 0 4px; }
.section-desc  { font-size: 0.82rem; color: #6b7280; margin: 0; }
.section-actions { display: flex; gap: 8px; flex-shrink: 0; }
.btn-sm { padding: 5px 14px; font-size: 0.82rem; }
.status-bar { padding: 7px 12px; border-radius: 6px; font-size: 0.83rem; margin-bottom: 12px; }
.status-bar.success { background: #ecfdf5; color: #065f46; }
.status-bar.error   { background: #fef2f2; color: #991b1b; }
.status-bar.warning { background: #fffbeb; color: #92400e; }
.status-bar.info    { background: #eff6ff; color: #1e40af; }
.add-row { display: flex; gap: 8px; margin-bottom: 16px; }
.add-input { flex: 1; max-width: 300px; font-family: 'Courier New', monospace; text-transform: uppercase; }
.keys-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.key-tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px 3px 12px;
  background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 9999px;
  font-size: 0.8rem; font-family: 'Courier New', monospace; font-weight: 600; color: #1e293b;
}
.key-tag-new { border-color: #6366f1; background: #eef2ff; color: #3730a3; }
.tag-remove { background: none; border: none; cursor: pointer; color: #94a3b8; font-size: 1rem; line-height: 1; padding: 0 2px; }
.tag-remove:hover { color: #ef4444; }
.key-count { margin-top: 10px; font-size: 0.78rem; color: #9ca3af; }
.kc-table-wrap { overflow-x: auto; border-radius: 12px; border: 1px solid rgba(226,232,240,0.8); }
.kc-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.kc-table th {
  text-align: left; padding: 9px 14px;
  background: rgba(241,245,249,0.8);
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; color: #64748b;
  border-bottom: 1px solid rgba(226,232,240,0.8);
}
.kc-table td { padding: 7px 14px; border-bottom: 1px solid rgba(241,245,249,0.9); vertical-align: middle; }
.kc-table tr:last-child td { border-bottom: none; }
.kc-table tr.kc-custom td { background: rgba(238,242,255,0.55); }
.kc-name { font-family: 'Courier New', monospace; font-weight: 600; color: #1e293b; }
.kc-code {
  font-family: 'Courier New', monospace;
  background: rgba(241,245,249,0.9); border: 1px solid #e2e8f0;
  border-radius: 6px; padding: 1px 8px; font-size: 0.82rem;
}
.kc-edit-input { width: 90px !important; padding: 4px 8px !important; font-size: 0.82rem !important; border-radius: 8px !important; }
.badge-custom { display: inline-block; padding: 1px 8px; background: #eef2ff; color: #4f46e5; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
.badge-default { display: inline-block; padding: 1px 8px; background: #f1f5f9; color: #94a3b8; border-radius: 9999px; font-size: 0.75rem; }
.kc-actions { display: flex; gap: 4px; }
.act-btn { background: none; border: none; cursor: pointer; font-size: 0.88rem; color: #94a3b8; padding: 2px 5px; border-radius: 6px; transition: background 0.12s, color 0.12s; }
.act-btn:hover { background: #f1f5f9; color: #334155; }
.act-del:hover { color: #f59e0b; }
.act-ok:hover  { color: #22c55e; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal-box { background: #fff; border-radius: 16px; padding: 28px 32px; min-width: 320px; max-width: 440px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.18); }
.modal-title { font-size: 1rem; font-weight: 700; margin: 0 0 4px; }
.modal-body  { font-size: 0.88rem; color: #4b5563; margin: 10px 0 0; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
</style>
