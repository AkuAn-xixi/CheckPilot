<template>
  <div class="card">
    <h2 class="mb-1">{{ $t('customization.title') }}</h2>
    <p class="text-sm text-gray-500 mb-5">{{ $t('customization.subtitle') }}</p>
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
              <span v-if="s.is_active" class="scheme-active-badge">{{ $t('customization.activeBadge') }}</span>
            </button>
          </div>
          <p v-if="schemes.length === 0" class="text-sm text-gray-400">{{ $t('customization.noSchemes') }}</p>
        </div>
        <div class="scheme-btns">
          <button class="btn btn-secondary btn-sm" @click="showCreateModal = true">{{ $t('customization.createScheme') }}</button>
          <button class="btn btn-secondary btn-sm" @click="showDuplicateModal = true" :disabled="!selectedScheme">{{ $t('customization.duplicate') }}</button>
          <button
            class="btn btn-secondary btn-sm"
            :disabled="excelImporting"
            @click="triggerExcelImport"
            :title="$t('customization.importFromExcelTitle')"
          >
            {{ excelImporting ? $t('customization.importFromExcelLoading') : $t('customization.importFromExcel') }}
          </button>
          <input
            ref="excelImportInput"
            type="file"
            accept=".xlsx,.xlsm"
            class="hidden"
            @change="onExcelImportFileChange"
          >
          <button class="btn btn-danger btn-sm" @click="confirmDeleteScheme" :disabled="!selectedScheme || schemes.length <= 1">{{ $t('customization.delete') }}</button>
        </div>
      </div>
      <div v-if="selectedScheme" class="scheme-status-row">
        <span class="text-sm text-gray-500">
          {{ $t('customization.editingScheme') }} <strong>{{ selectedScheme }}</strong>
        </span>
        <button
          v-if="activeScheme !== selectedScheme"
          class="btn btn-primary btn-sm"
          @click="activateCurrentScheme"
        >
          {{ $t('customization.setActive') }}
        </button>
        <span v-else class="active-hint">{{ $t('customization.currentActive') }}</span>
      </div>
      <div v-if="excelImportError" class="status-bar error mt-3">{{ excelImportError }}</div>
      <div v-else-if="excelImportMessage" class="status-bar success mt-3">{{ excelImportMessage }}</div>
    </section>

    <section class="config-section mb-4">
      <div class="section-header">
        <div>
          <h3 class="section-title">{{ $t('customization.extraDelay') }}</h3>
          <p class="section-desc">{{ $t('customization.extraDelayDesc') }}</p>
        </div>
        <div class="section-actions">
          <button
            class="btn btn-primary btn-sm"
            :disabled="extraDelayLoading || !extraDelayDirty"
            @click="saveExtraDelay"
          >
            {{ extraDelayLoading ? $t('customization.saving') : $t('customization.saveChanges') }}
          </button>
        </div>
      </div>
      <div v-if="extraDelayStatusMsg" :class="['status-bar', extraDelayStatusType]">{{ extraDelayStatusMsg }}</div>
      <div class="extra-delay-row">
        <input
          v-model.number="extraDelayDraft"
          type="number"
          min="0"
          step="0.5"
          class="form-input"
          style="width: 140px;"
        >
        <span class="text-sm text-gray-500">{{ $t('customization.extraDelaySeconds') }}</span>
        <span class="text-xs text-gray-400 ml-3">{{ $t('customization.extraDelayHint', { example: extraDelayExampleHint }) }}</span>
      </div>
    </section>

    <template v-if="selectedScheme">
      <section class="config-section mb-4">
        <div class="section-header">
          <div>
            <h3 class="section-title">{{ $t('customization.validKeys') }}</h3>
            <p class="section-desc">{{ $t('customization.validKeysDesc') }}</p>
          </div>
          <div class="section-actions">
            <button class="btn btn-secondary btn-sm" @click="confirmReset" :disabled="loading">{{ $t('customization.restoreDefault') }}</button>
            <button class="btn btn-primary btn-sm" @click="saveKeys" :disabled="loading || !dirty">
              {{ loading ? $t('customization.saving') : $t('customization.saveChanges') }}
            </button>
          </div>
        </div>
        <div v-if="statusMsg" :class="['status-bar', statusType]">{{ statusMsg }}</div>
        <div class="add-row">
          <input
            v-model="newKey"
            class="form-input add-input"
            :placeholder="$t('customization.addKeyPlaceholder')"
            @keydown.enter.prevent="addKey"
            @input="newKey = newKey.toUpperCase()"
            maxlength="40"
          />
          <button class="btn btn-primary btn-sm" @click="addKey" :disabled="!newKey.trim()">{{ $t('customization.add') }}</button>
        </div>
        <div v-if="keys.length" class="keys-grid">
          <span
            v-for="key in keys"
            :key="key"
            class="key-tag"
            :class="{ 'key-tag-new': addedKeys.has(key) }"
          >
            {{ key }}
            <button class="tag-remove" @click="removeKey(key)" :title="$t('customization.tooltips.remove')">×</button>
          </span>
        </div>
        <p v-else class="text-sm text-gray-400 mt-4">{{ $t('customization.noKeys') }}</p>
        <p class="key-count">{{ $t('customization.keyCount', { count: keys.length }) }}</p>
      </section>
      <section class="config-section">
        <div class="section-header">
          <div>
            <h3 class="section-title">{{ $t('customization.keyCodeMapping') }}</h3>
            <p class="section-desc">{{ $t('customization.keyCodeDesc') }}</p>
          </div>
          <div class="section-actions">
            <button class="btn btn-secondary btn-sm" @click="confirmResetCodes" :disabled="kcLoading">{{ $t('customization.restoreDefault') }}</button>
          </div>
        </div>
        <div v-if="kcStatusMsg" :class="['status-bar', kcStatusType]">{{ kcStatusMsg }}</div>
        <div class="add-row mb-4">
          <input
            v-model="kcNewName"
            class="form-input add-input"
            :placeholder="$t('customization.keyNamePlaceholder')"
            @input="kcNewName = kcNewName.toUpperCase()"
            maxlength="40"
          />
          <input
            v-model.number="kcNewCode"
            class="form-input"
            style="width:100px;"
            type="number"
            min="0"
            :placeholder="$t('customization.keyCodePlaceholder')"
          />
          <button class="btn btn-primary btn-sm" @click="addKeyCode" :disabled="!kcNewName.trim() || kcNewCode === ''">{{ $t('customization.addOrOverride') }}</button>
        </div>
        <div class="kc-table-wrap">
          <table class="kc-table">
            <thead>
              <tr>
                <th>{{ $t('customization.columns.keyName') }}</th>
                <th>{{ $t('customization.columns.keyCode') }}</th>
                <th>{{ $t('customization.columns.type') }}</th>
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
                  <span v-if="customOverrides[name] !== undefined" class="badge-custom">{{ $t('customization.custom') }}</span>
                  <span v-else class="badge-default">{{ $t('customization.default') }}</span>
                </td>
                <td class="kc-actions">
                  <template v-if="!editingKey || editingKey !== name">
                    <button class="act-btn" @click="startEdit(name, code)" :title="$t('customization.tooltips.edit')">✎</button>
                    <button
                      v-if="customOverrides[name] !== undefined"
                      class="act-btn act-del"
                      @click="deleteOverride(name)"
                      :title="$t('customization.tooltips.restoreDefault')"
                    >↩</button>
                  </template>
                  <template v-else>
                    <button class="act-btn act-ok" @click="commitEdit(name)" :title="$t('customization.tooltips.confirm')">✓</button>
                    <button class="act-btn" @click="editingKey = null" :title="$t('customization.tooltips.cancel')">✕</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="key-count">{{ $t('customization.mappingCount', { total: sortedKeyCodes.length, custom: Object.keys(customOverrides).length }) }}</p>
      </section>
    </template>
    <div v-if="showCreateModal" class="modal-backdrop" @click.self="showCreateModal = false">
      <div class="modal-box">
        <h4 class="modal-title">{{ $t('customization.createModalTitle') }}</h4>
        <input
          v-model="newSchemeName"
          class="form-input mt-3"
          :placeholder="$t('customization.createModalPlaceholder')"
          maxlength="30"
          @keydown.enter="doCreateScheme"
          ref="createInput"
        />
        <div v-if="createError" class="status-bar error mt-2">{{ createError }}</div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showCreateModal = false">{{ $t('common.cancel') }}</button>
          <button class="btn btn-primary btn-sm" @click="doCreateScheme" :disabled="!newSchemeName.trim()">{{ $t('customization.create') }}</button>
        </div>
      </div>
    </div>
    <div v-if="showDuplicateModal" class="modal-backdrop" @click.self="showDuplicateModal = false">
      <div class="modal-box">
        <h4 class="modal-title">{{ $t('customization.duplicateModalTitle', { name: selectedScheme }) }}</h4>
        <input
          v-model="duplicateName"
          class="form-input mt-3"
          :placeholder="$t('customization.duplicateModalPlaceholder')"
          maxlength="30"
          @keydown.enter="doDuplicateScheme"
        />
        <div v-if="duplicateError" class="status-bar error mt-2">{{ duplicateError }}</div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showDuplicateModal = false">{{ $t('common.cancel') }}</button>
          <button class="btn btn-primary btn-sm" @click="doDuplicateScheme" :disabled="!duplicateName.trim()">{{ $t('customization.duplicate') }}</button>
        </div>
      </div>
    </div>
    <div v-if="showDeleteConfirm" class="modal-backdrop" @click.self="showDeleteConfirm = false">
      <div class="modal-box">
        <h4 class="modal-title">{{ $t('customization.deleteModalTitle') }}</h4>
        <p class="modal-body">{{ $t('customization.deleteModalBody', { name: selectedScheme }) }}</p>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showDeleteConfirm = false">{{ $t('common.cancel') }}</button>
          <button class="btn btn-danger btn-sm" @click="doDeleteScheme">{{ $t('customization.confirmDelete') }}</button>
        </div>
      </div>
    </div>
    <div v-if="showResetConfirm" class="modal-backdrop" @click.self="showResetConfirm = false">
      <div class="modal-box">
        <h4 class="modal-title">{{ $t('customization.resetKeysTitle') }}</h4>
        <p class="modal-body">{{ $t('customization.resetKeysBody', { name: selectedScheme }) }}</p>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showResetConfirm = false">{{ $t('common.cancel') }}</button>
          <button class="btn btn-danger btn-sm" @click="doReset">{{ $t('customization.confirmRestore') }}</button>
        </div>
      </div>
    </div>
    <div v-if="showResetCodesConfirm" class="modal-backdrop" @click.self="showResetCodesConfirm = false">
      <div class="modal-box">
        <h4 class="modal-title">{{ $t('customization.resetCodesTitle') }}</h4>
        <p class="modal-body">{{ $t('customization.resetCodesBody', { name: selectedScheme }) }}</p>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" @click="showResetCodesConfirm = false">{{ $t('common.cancel') }}</button>
          <button class="btn btn-danger btn-sm" @click="doResetCodes">{{ $t('customization.confirmRestore') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })

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

// Excel 导入状态
const excelImportInput = ref(null)
const excelImporting = ref(false)
const excelImportError = ref('')
const excelImportMessage = ref('')
let excelImportMessageTimer = null

// 全局命令延迟增量（秒）
const extraDelaySaved = ref(0)
const extraDelayDraft = ref(0)
const extraDelayLoading = ref(false)
const extraDelayStatusMsg = ref('')
const extraDelayStatusType = ref('info')
let extraDelayStatusTimer = null

const extraDelayDirty = computed(() => {
  const draft = Number(extraDelayDraft.value)
  if (Number.isNaN(draft)) return false
  return Math.abs(draft - extraDelaySaved.value) > 1e-9
})
const extraDelayExampleHint = computed(() => {
  const draft = Number(extraDelayDraft.value)
  if (!Number.isFinite(draft) || draft <= 0) return '0'
  // 给用户一个直观例子：2 + draft
  return (2 + draft).toFixed(draft % 1 === 0 ? 0 : 1)
})

function showExtraDelayStatus(msg, type = 'success') {
  extraDelayStatusMsg.value = msg
  extraDelayStatusType.value = type
  if (extraDelayStatusTimer) {
    clearTimeout(extraDelayStatusTimer)
  }
  extraDelayStatusTimer = setTimeout(() => {
    extraDelayStatusMsg.value = ''
  }, 3000)
}

async function fetchExtraDelay() {
  try {
    const res = await fetch('/api/customization/extra-command-delay')
    if (!res.ok) return
    const data = await res.json()
    const value = Number(data?.extra_command_delay) || 0
    extraDelaySaved.value = value
    extraDelayDraft.value = value
  } catch {}
}

async function saveExtraDelay() {
  let next = Number(extraDelayDraft.value)
  if (!Number.isFinite(next) || next < 0) {
    next = 0
  }
  extraDelayLoading.value = true
  try {
    const res = await fetch('/api/customization/extra-command-delay', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ extra_command_delay: next })
    })
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      throw new Error(e.detail || t('customization.status.saveFailed'))
    }
    const data = await res.json()
    const saved = Number(data?.extra_command_delay) || 0
    extraDelaySaved.value = saved
    extraDelayDraft.value = saved
    showExtraDelayStatus(t('customization.status.saveSuccess'), 'success')
  } catch (error) {
    showExtraDelayStatus(error?.message || t('customization.status.saveFailed'), 'error')
  } finally {
    extraDelayLoading.value = false
  }
}

function showExcelImportSuccess(message) {
  excelImportError.value = ''
  excelImportMessage.value = message
  if (excelImportMessageTimer) {
    clearTimeout(excelImportMessageTimer)
  }
  excelImportMessageTimer = setTimeout(() => {
    excelImportMessage.value = ''
  }, 5000)
}

function triggerExcelImport() {
  excelImportError.value = ''
  excelImportMessage.value = ''
  if (excelImportInput.value) {
    excelImportInput.value.value = ''
  }
  excelImportInput.value?.click()
}

async function onExcelImportFileChange(event) {
  const file = event?.target?.files?.[0]
  if (!file) return
  excelImporting.value = true
  excelImportError.value = ''
  excelImportMessage.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('conflict', 'rename')
    const res = await fetch('/api/customization/schemes/import-excel', {
      method: 'POST',
      body: formData,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(data?.detail || t('customization.importFromExcelFailed'))
    }
    await fetchSchemes()
    if (data.imported_scheme) {
      selectedScheme.value = data.imported_scheme
    }
    let message = ''
    if (data.skipped) {
      message = t('customization.importExcelSkipped', { count: data.key_codes_count })
    } else if (data.renamed_from) {
      message = t('customization.importExcelRenamed', {
        original: data.renamed_from,
        saved_as: data.imported_scheme,
        count: data.key_codes_count,
      })
    } else {
      message = t('customization.importExcelSuccess', {
        name: data.imported_scheme,
        count: data.key_codes_count,
      })
    }
    showExcelImportSuccess(message)
  } catch (error) {
    excelImportError.value = error?.message || t('customization.importFromExcelFailed')
  } finally {
    excelImporting.value = false
  }
}

async function fetchSchemes() {
  try {
    const res = await fetch('/api/customization/schemes')
    const data = await res.json()
    schemes.value = data.schemes || []
    activeScheme.value = data.active_scheme || ''
    if (!selectedScheme.value || !schemes.value.find(s => s.name === selectedScheme.value)) {
      selectedScheme.value = activeScheme.value || schemes.value[0]?.name || ''
    }
  } catch { }
}

function selectScheme(name) {
  if (selectedScheme.value === name) return
  if (!confirmDiscardUnsavedChanges()) return
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
    if (!res.ok) { createError.value = data.detail || t('customization.status.createFailed'); return }
    showCreateModal.value = false
    newSchemeName.value = ''
    await fetchSchemes()
    selectedScheme.value = name
  } catch { createError.value = t('customization.status.requestFailed') }
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
    if (!res.ok) { duplicateError.value = data.detail || t('customization.status.duplicateFailed'); return }
    showDuplicateModal.value = false
    duplicateName.value = ''
    await fetchSchemes()
    selectedScheme.value = newName
  } catch { duplicateError.value = t('customization.status.requestFailed') }
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
    showStatus(t('customization.status.loadKeysFailed'), 'error')
  } finally {
    loading.value = false
  }
}

function addKey() {
  const k = newKey.value.trim().toUpperCase()
  if (!k) return
  if (keys.value.includes(k)) { showStatus(t('customization.status.keyExists', { name: k }), 'warning'); return }
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
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || t('customization.status.saveFailed')) }
    const data = await res.json()
    keys.value = data.keys
    dirty.value = false
    addedKeys.value = new Set()
    showStatus(t('customization.status.saveSuccess'))
  } catch (e) {
    showStatus(e.message || t('customization.status.saveFailed'), 'error')
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
    showStatus(t('customization.status.restoreKeysSuccess'))
  } catch { showStatus(t('customization.status.restoreFailed'), 'error') } finally { loading.value = false }
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
const editingOriginalCode = ref(null)
let kcTimer = null

const hasPendingKeyCodeDraft = computed(() => {
  const hasNewKeyNameDraft = kcNewName.value.trim().length > 0
  const hasNewKeyCodeDraft = kcNewCode.value !== '' && kcNewCode.value !== null && kcNewCode.value !== undefined
  const hasInlineEditDraft = editingKey.value !== null && Number(editingCode.value) !== Number(editingOriginalCode.value)
  return hasNewKeyNameDraft || hasNewKeyCodeDraft || hasInlineEditDraft
})

const hasUnsavedChanges = computed(() => dirty.value || hasPendingKeyCodeDraft.value)

function discardUnsavedChanges() {
  dirty.value = false
  addedKeys.value = new Set()
  newKey.value = ''
  kcNewName.value = ''
  kcNewCode.value = ''
  editingKey.value = null
  editingOriginalCode.value = null
}

function confirmDiscardUnsavedChanges() {
  if (!hasUnsavedChanges.value) {
    return true
  }

  const confirmed = window.confirm(t('customization.alerts.unsavedChangesConfirm'))
  if (confirmed) {
    discardUnsavedChanges()
  }
  return confirmed
}

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
    showKcStatus(t('customization.status.loadKeyCodesFailed'), 'error')
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

function startEdit(name, code) {
  editingKey.value = name
  editingCode.value = code
  editingOriginalCode.value = code
}

async function commitEdit(name) {
  const code = Number(editingCode.value)
  if (isNaN(code) || code < 0) { showKcStatus(t('customization.status.nonNegativeCode'), 'warning'); return }
  editingKey.value = null
  editingOriginalCode.value = null
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
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || t('customization.status.saveFailed')) }
    const data = await res.json()
    keyCodes.value = data.key_codes
    customOverrides.value = data.custom_overrides
    showKcStatus(t('customization.status.keyCodeSaved'))
  } catch (e) {
    showKcStatus(e.message || t('customization.status.saveFailed'), 'error')
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
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      throw new Error(e.detail || t('customization.status.deleteFailed'))
    }
    const data = await res.json()
    keyCodes.value = data.key_codes
    customOverrides.value = data.custom_overrides
    showKcStatus(t('customization.status.restoredDefaultKeyCode', { name }))
  } catch (e) {
    showKcStatus(e.message || t('customization.status.deleteFailed'), 'error')
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
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      throw new Error(e.detail || t('customization.status.restoreFailed'))
    }
    const data = await res.json()
    keyCodes.value = data.key_codes
    customOverrides.value = data.custom_overrides
    showKcStatus(t('customization.status.restoreKeyCodeSuccess'))
  } catch (e) { showKcStatus(e.message || t('customization.status.restoreFailed'), 'error') } finally { kcLoading.value = false }
}

watch(selectedScheme, (name) => {
  if (!name) return
  statusMsg.value = ''
  kcStatusMsg.value = ''
  dirty.value = false
  editingKey.value = null
  editingOriginalCode.value = null
  fetchKeys()
  fetchKeyCodes()
})

onMounted(async () => {
  await fetchSchemes()
  if (selectedScheme.value) {
    fetchKeys()
    fetchKeyCodes()
  }
  await fetchExtraDelay()
})

onBeforeRouteLeave((to, from, next) => {
  if (confirmDiscardUnsavedChanges()) {
    next()
    return
  }

  next(false)
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
.extra-delay-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 6px;
}
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
