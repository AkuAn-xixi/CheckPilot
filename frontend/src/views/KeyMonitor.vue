<template>
  <div class="card">
    <h2 class="mb-4">按键监听</h2>
    <div v-if="!selectedDevice" class="bg-yellow-50 p-4 rounded-lg mb-6">
      <p class="text-warning mb-2">请先在设备管理页面选择一个ADB设备</p>
      <router-link to="/devices" class="btn btn-primary">
        前往设备管理
      </router-link>
    </div>
    <div v-else>
      <div class="bg-white border rounded-lg p-4 mb-4 w-full max-w-screen-lg mx-auto">
        <input
          id="keymonitor-excel-upload"
          ref="excelUploadInput"
          type="file"
          class="hidden"
          accept=".xlsx,.xls"
          @change="uploadExcelFile"
        >
        <div class="flex flex-wrap gap-3 mb-3">
          <button 
            v-if="!keyMonitorActive"
            @click="startKeyMonitor"
            class="btn btn-secondary"
          >
            开始监听
          </button>
          <button 
            v-else
            @click="stopKeyMonitor"
            class="btn btn-danger"
          >
            停止监听
          </button>
          <button 
            @click="copySequence"
            class="btn btn-primary"
            :disabled="!workingSequence || keyMonitorActive || isStarting"
            title="监听未进行时才可复制"
          >
            复制序列
          </button>
        </div>
        <div class="mb-4 rounded-xl border border-slate-200 bg-slate-50/80 p-4">
          <div class="flex flex-wrap items-center gap-2 mb-3">
            <div class="text-sm font-medium text-gray-700">Excel 文件</div>
            <button class="btn btn-secondary btn-sm" @click="loadExcelFiles" :disabled="excelLoadingFiles || excelUploading">
              {{ excelLoadingFiles ? '刷新中…' : '刷新文件列表' }}
            </button>
            <label for="keymonitor-excel-upload" class="btn btn-secondary btn-sm cursor-pointer" :class="{ 'opacity-60 pointer-events-none': excelUploading }">
              {{ excelUploading ? '上传中…' : '上传 Excel' }}
            </label>
          </div>
          <div class="grid gap-3">
            <select
              v-model="selectedExcelFile"
              class="form-select"
              :disabled="excelLoadingFiles || excelUploading"
              @change="handleExcelFileChange"
            >
              <option value="">选择 Excel 文件</option>
              <option v-for="file in excelFiles" :key="file" :value="file">{{ file }}</option>
            </select>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <button
              class="btn btn-secondary btn-sm"
              @click="saveSequenceToExcel"
              :disabled="!selectedExcelFile || !workingSequence || keyMonitorActive || isStarting || excelLoadingRows || excelUploading || excelSavingSequence"
            >
              {{ excelSavingSequence ? '写入中…' : '写入 preScript 最新空白行' }}
            </button>
          </div>
          <div class="text-sm text-gray-500 mt-2">
            可选择 Excel 文件，并将当前监听/编辑后的序列写回到 preScript 最新空白行。
          </div>
          <div v-if="selectedExcelFile && !excelLoadingRows && excelRows.length === 0" class="mt-2 text-sm text-gray-500">
            该文件当前未解析出可用命令行，但仍可将当前序列写入 preScript 最新空白行。
          </div>
          <div v-if="excelImportError" class="text-sm text-danger mt-2">
            {{ excelImportError }}
          </div>
          <div v-else-if="excelImportMessage" class="text-sm text-green-600 mt-2">
            {{ excelImportMessage }}
          </div>
        </div>
        <div v-if="keyMonitorActive || isStarting" class="border rounded p-3 bg-gray-50 min-h-[120px] font-mono text-sm whitespace-pre-wrap w-full overflow-auto">
          <template v-if="displayParts.length > 0">
            <template v-for="(part, idx) in displayParts" :key="idx">
              <span>
                <template v-for="(seg, sIdx) in splitPart(part)" :key="sIdx">
                  <span v-if="sIdx === 2 && seg === '*'" class="text-gray-400">*</span>
                  <span v-else>{{ seg }}</span>
                  <span v-if="sIdx < 2">/</span>
                </template>
              </span>
              <span v-if="idx < displayParts.length - 1">,</span>
            </template>
          </template>
          <template v-else>
            <span class="text-gray-400">监听到的按键序列会显示在这里，格式为 KEY/次数/延迟,KEY/次数/延迟</span>
          </template>
        </div>
        <textarea
          v-else
          v-model="editableSequence"
          @input="handleEditableSequenceInput"
          class="form-input min-h-[120px] font-mono text-sm w-full"
          placeholder="监听结束后，可直接在这里修正错误指令或延迟"
        ></textarea>
        <div class="text-sm text-gray-500 mt-2" v-if="keyMonitorActive && !keyMonitorSequence">
          正在监听，请在设备上按键…
        </div>
        <div class="text-sm text-danger mt-2" v-if="keyMonitorError">
          {{ keyMonitorError }}
        </div>
        <div v-if="!keyMonitorActive && !isStarting" class="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <div class="text-sm text-gray-700">
            本次结果仍可直接在上方文本框手改。如果你已经确认某个错误指令对应哪个正确按键，请先把规则保存在这里；保存后，下次监听会直接输出修正后的指令。
          </div>
          <div class="flex flex-wrap gap-2 items-center mt-2">
            <input
              v-model="replaceSourceKey"
              type="text"
              list="monitor-source-commands"
              class="form-input min-w-[180px]"
              placeholder="输入或选择待纠正指令，如 LIBRARY"
            >
            <datalist id="monitor-source-commands">
              <option v-for="cmd in correctionSourceOptions" :key="cmd" :value="cmd"></option>
            </datalist>
            <input
              v-model="replaceTargetKey"
              type="text"
              list="valid-monitor-keys"
              class="form-input min-w-[180px]"
              placeholder="替换为正确指令，如 SETTING"
            >
            <datalist id="valid-monitor-keys">
              <option v-for="cmd in validMonitorTargets" :key="cmd" :value="cmd"></option>
            </datalist>
            <button class="btn btn-primary btn-sm" @click="saveCorrectionRule" :disabled="!replaceSourceKey || !replaceTargetKey.trim() || savingMapping">
              {{ savingMapping ? '保存中…' : '保存规则并应用当前结果' }}
            </button>
            <button class="btn btn-secondary btn-sm" @click="restoreCapturedSequence" :disabled="!sequenceDirty">
              恢复原始序列
            </button>
          </div>
          <div v-if="detectedInvalidCommands.length > 0" class="text-sm text-yellow-700 mt-2">
            本次监听检测到疑似错误指令：{{ detectedInvalidCommands.join(',') }}
          </div>
          <div v-else class="text-sm text-gray-600 mt-2">
            本次监听没有发现新的未知指令。你也可以直接维护下面已保存的纠正规则。
          </div>
          <div v-if="mappingError" class="text-sm text-danger mt-2">
            {{ mappingError }}
          </div>
          <div v-if="savedMappingsList.length > 0" class="mt-3">
            <div class="text-sm text-gray-700 mb-2">已保存的自动纠正规则：</div>
            <div class="flex flex-col gap-2">
              <div v-for="mapping in savedMappingsList" :key="mapping.source" class="flex flex-wrap items-center gap-2 text-sm bg-white border rounded px-3 py-2">
                <span class="font-mono">{{ mapping.source }}</span>
                <span>→</span>
                <span class="font-mono text-primary">{{ mapping.target }}</span>
                <button class="btn btn-secondary btn-sm ml-auto" @click="removeCorrectionRule(mapping.source)">
                  删除规则
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'

const VALID_MONITOR_KEYS = new Set([
  'OK', 'HOME', 'BACK', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'MENU', 'SETTING',
  'DIGITAL0', 'DIGITAL1', 'DIGITAL2', 'DIGITAL3', 'DIGITAL4', 'DIGITAL5', 'DIGITAL6', 'DIGITAL7', 'DIGITAL8', 'DIGITAL9',
  'APPS', 'POWER', 'SOURCE', 'CHUP', 'CHDOWN', 'EXIT', 'LIBRARY', 'TV_AV', 'VOLUMEUP', 'VOLUMEDOWN',
  'NETFLIX', 'YOUTUBE', 'PRIME_VIDEO', 'PRIME_VII', 'ACTION3', 'ACTIONS', 'FILES', 'RED', 'GREEN', 'YELLOW', 'BLUE',
  'INFORMATION', 'MUTE'
])
const defaultValidMonitorKeys = Array.from(VALID_MONITOR_KEYS)
  .filter(key => !['PRIME_VII', 'ACTIONS'].includes(key))
  .sort()

const selectedDevice = ref('')
const keyMonitorActive = ref(false)
const keyMonitorSequence = ref('')
const editableSequence = ref('')
const keyMonitorError = ref('')
let statusTimer = null
const apiUnavailable = ref(false)
const isStarting = ref(false)
const replaceSourceKey = ref('')
const replaceTargetKey = ref('')
const sequenceDirty = ref(false)
const savedMappings = ref({})
const savingMapping = ref(false)
const mappingError = ref('')
const validMonitorTargets = ref(defaultValidMonitorKeys)
const excelFiles = ref([])
const selectedExcelFile = ref('')
const excelRows = ref([])
const excelLoadingFiles = ref(false)
const excelLoadingRows = ref(false)
const excelUploading = ref(false)
const excelSavingSequence = ref(false)
const excelImportError = ref('')
const excelImportMessage = ref('')
const displayParts = computed(() => {
  const s = keyMonitorSequence.value || ''
  return s.split(',').map(i => i.trim()).filter(Boolean)
})
const workingSequence = computed(() => {
  return (keyMonitorActive.value || isStarting.value)
    ? keyMonitorSequence.value
    : editableSequence.value
})
const detectedInvalidCommands = computed(() => {
  if (keyMonitorActive.value || isStarting.value) {
    return []
  }
  const validTargetSet = new Set(validMonitorTargets.value.map(key => String(key).trim().toUpperCase()))
  const parts = (keyMonitorSequence.value || '').split(',').map(item => item.trim()).filter(Boolean)
  const invalid = new Set()
  for (const part of parts) {
    const [key] = part.split('/')
    const normalizedKey = (key || '').trim().toUpperCase()
    if (normalizedKey && !validTargetSet.has(normalizedKey)) {
      invalid.add(normalizedKey)
    }
  }
  return Array.from(invalid)
})
const savedMappingsList = computed(() => {
  return Object.entries(savedMappings.value)
    .map(([source, target]) => ({ source, target }))
    .sort((left, right) => left.source.localeCompare(right.source))
})
const correctionSourceOptions = computed(() => {
  const commands = new Set()
  const normalized = normalizeCommandSequence(workingSequence.value)

  normalized
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
    .forEach((part) => {
      const [key] = part.split('/')
      const normalizedKey = (key || '').trim().toUpperCase()
      if (normalizedKey) {
        commands.add(normalizedKey)
      }
    })

  Object.keys(savedMappings.value || {}).forEach((key) => {
    const normalizedKey = String(key || '').trim().toUpperCase()
    if (normalizedKey) {
      commands.add(normalizedKey)
    }
  })

  return Array.from(commands).sort()
})
const splitPart = (p) => p.split('/')

function hasMeaningfulValue(value) {
  if (value === null || value === undefined) {
    return false
  }

  const normalized = String(value).trim()
  return normalized !== '' && normalized.toLowerCase() !== 'nan'
}

function normalizeCommandSequence(sequence) {
  return String(sequence || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .join(',')
}

const clearExcelImportStatus = () => {
  excelImportError.value = ''
  excelImportMessage.value = ''
}

const replaceCommandInSequence = (sequence, sourceKey, targetKey) => {
  const normalizedSource = (sourceKey || '').trim().toUpperCase()
  const normalizedTarget = (targetKey || '').trim().toUpperCase()
  if (!normalizedSource || !normalizedTarget || !sequence) {
    return sequence
  }
  return sequence
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
    .map((part) => {
      const segments = part.split('/')
      if (segments.length < 3) {
        return part
      }
      if ((segments[0] || '').trim().toUpperCase() !== normalizedSource) {
        return part
      }
      return `${normalizedTarget}/${segments[1]}/${segments[2]}`
    })
    .join(',')
}

const applyCorrectionMappingsToSequence = (sequence, mappings = savedMappings.value) => {
  const normalized = normalizeCommandSequence(sequence)
  if (!normalized || !mappings || typeof mappings !== 'object') {
    return normalized
  }

  return normalized
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
    .map((part) => {
      const segments = part.split('/')
      if (segments.length < 3) {
        return part
      }

      const sourceKey = (segments[0] || '').trim().toUpperCase()
      const mappedKey = mappings[sourceKey]
      if (typeof mappedKey !== 'string' || !mappedKey.trim()) {
        return part
      }

      return `${mappedKey.trim().toUpperCase()}/${segments[1]}/${segments[2]}`
    })
    .join(',')
}

const syncCapturedSequence = (sequence, mappings = savedMappings.value) => {
  const normalized = applyCorrectionMappingsToSequence(sequence, mappings)
  keyMonitorSequence.value = normalized
  editableSequence.value = normalized
  sequenceDirty.value = false
  replaceSourceKey.value = ''
  replaceTargetKey.value = ''
}

onMounted(async () => {
  await loadCurrentDevice()
  await loadCorrectionRules()
  await loadExcelFiles()
  startStatusPolling()
})

onBeforeUnmount(() => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
})

const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    selectedDevice.value = data.device
  } catch {}
}

const loadExcelFiles = async () => {
  excelLoadingFiles.value = true
  clearExcelImportStatus()
  try {
    const response = await fetch('/api/excel/files')
    if (!response.ok) {
      throw new Error('加载 Excel 文件列表失败')
    }
    const data = await response.json()
    excelFiles.value = Array.isArray(data.files) ? data.files : []

    if (selectedExcelFile.value && !excelFiles.value.includes(selectedExcelFile.value)) {
      selectedExcelFile.value = ''
      excelRows.value = []
    }
  } catch (error) {
    excelImportError.value = error.message || '加载 Excel 文件列表失败'
  } finally {
    excelLoadingFiles.value = false
  }
}

const analyzeSelectedExcel = async () => {
  if (!selectedExcelFile.value) {
    excelRows.value = []
    return
  }

  excelLoadingRows.value = true
  clearExcelImportStatus()
  try {
    const response = await fetch(`/api/excel/analyze?file_name=${encodeURIComponent(selectedExcelFile.value)}`)
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || '读取 Excel 内容失败')
    }

    const data = await response.json()
    excelRows.value = Array.isArray(data.valid_rows) ? data.valid_rows : []

    if (excelRows.value.length === 0) {
      excelImportError.value = '该 Excel 文件未解析出有效命令行'
      return
    }
  } catch (error) {
    excelRows.value = []
    excelImportError.value = error.message || '读取 Excel 内容失败'
  } finally {
    excelLoadingRows.value = false
  }
}

const handleExcelFileChange = async () => {
  excelRows.value = []
  clearExcelImportStatus()
  await analyzeSelectedExcel()
}

const uploadExcelFile = async (event) => {
  const file = event.target?.files?.[0]
  if (!file) {
    return
  }

  excelUploading.value = true
  clearExcelImportStatus()
  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch('/api/excel/upload', {
      method: 'POST',
      body: formData,
    })

    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || '上传 Excel 文件失败')
    }

    excelImportMessage.value = data.message || 'Excel 文件上传成功'
    await loadExcelFiles()
    selectedExcelFile.value = data.filename || file.name
    await analyzeSelectedExcel()
  } catch (error) {
    excelImportError.value = error.message || '上传 Excel 文件失败'
  } finally {
    if (event.target) {
      event.target.value = ''
    }
    excelUploading.value = false
  }
}

const startStatusPolling = () => {
  statusTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/keymonitor/status')
      if (res.ok) {
        const data = await res.json()
        keyMonitorActive.value = data.active
        if (data.active) {
          isStarting.value = false
          syncCapturedSequence(data.live_sequence || '')
        } else {
          keyMonitorSequence.value = applyCorrectionMappingsToSequence(data.latest_sequence || '')
          if (!isStarting.value && !sequenceDirty.value) {
            editableSequence.value = applyCorrectionMappingsToSequence(data.latest_sequence || '')
          }
        }
        keyMonitorError.value = data.last_error || ''
        apiUnavailable.value = false
      } else if (res.status === 404) {
        apiUnavailable.value = true
        keyMonitorError.value = '后端未提供按键监听接口，请重启后端服务以加载最新代码'
        clearInterval(statusTimer); statusTimer = null
      }
    } catch {}
  }, 800)
}

const startKeyMonitor = async () => {
  syncCapturedSequence('')
  keyMonitorError.value = ''
  isStarting.value = true
  try {
    const res = await fetch('/api/keymonitor/start', { method: 'POST' })
    if (res.ok) {
      keyMonitorActive.value = true
      keyMonitorError.value = ''
      apiUnavailable.value = false
    } else {
      const data = await res.json().catch(() => ({}))
      keyMonitorError.value = data?.detail || '启动监听失败'
      if (res.status === 404) {
        apiUnavailable.value = true
      }
    }
  } catch {}
}

const loadCorrectionRules = async () => {
  try {
    const res = await fetch('/api/keymonitor/mappings')
    if (!res.ok) {
      throw new Error('加载纠正规则失败')
    }
    const data = await res.json()
    const mappings = data.mappings || {}
    savedMappings.value = mappings
    validMonitorTargets.value = (data.valid_targets && data.valid_targets.length > 0)
      ? data.valid_targets
      : defaultValidMonitorKeys
    keyMonitorSequence.value = applyCorrectionMappingsToSequence(keyMonitorSequence.value, mappings)
    editableSequence.value = applyCorrectionMappingsToSequence(editableSequence.value, mappings)
    sequenceDirty.value = editableSequence.value !== keyMonitorSequence.value
    mappingError.value = ''
  } catch (error) {
    mappingError.value = error.message || '加载纠正规则失败'
  }
}

const stopKeyMonitor = async () => {
  try {
    const res = await fetch('/api/keymonitor/stop', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      keyMonitorActive.value = false
      isStarting.value = false
      syncCapturedSequence(data.sequence || '')
      apiUnavailable.value = false
    }
  } catch {}
}

const copySequence = async () => {
  if (keyMonitorActive.value || isStarting.value) {
    alert('监听进行中，停止后再复制序列')
    return
  }
  if (!workingSequence.value) return
  const compressed = compressAdjacent(workingSequence.value)
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(compressed)
    } else {
      const el = document.createElement('textarea')
      el.value = compressed
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    alert('序列已复制（已合并相邻相同指令）')
  } catch {}
}

const handleEditableSequenceInput = () => {
  sequenceDirty.value = true
}

const restoreCapturedSequence = () => {
  editableSequence.value = keyMonitorSequence.value
  sequenceDirty.value = false
  replaceSourceKey.value = ''
  replaceTargetKey.value = ''
}

const saveSequenceToExcel = async () => {
  const sequence = normalizeCommandSequence(workingSequence.value)
  if (!selectedExcelFile.value) {
    excelImportError.value = '请先选择 Excel 文件'
    return
  }
  if (!sequence) {
    excelImportError.value = '当前没有可写入的命令序列'
    return
  }

  excelSavingSequence.value = true
  clearExcelImportStatus()
  try {
    const response = await fetch('/api/excel/append_sequence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: selectedExcelFile.value, sequence })
    })

    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || '写入 preScript 失败')
    }

    if (selectedExcelFile.value) {
      await analyzeSelectedExcel()
    }

    excelImportError.value = ''
    excelImportMessage.value = data.message || `已写入 ${selectedExcelFile.value} 的 preScript`
  } catch (error) {
    excelImportError.value = error.message || '写入 preScript 失败'
  } finally {
    excelSavingSequence.value = false
  }
}

const saveCorrectionRule = async () => {
  const sourceKey = replaceSourceKey.value.trim().toUpperCase()
  const targetKey = replaceTargetKey.value.trim().toUpperCase()
  if (!sourceKey || !targetKey) {
    return
  }

  savingMapping.value = true
  try {
    const res = await fetch('/api/keymonitor/mappings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_key: sourceKey, target_key: targetKey })
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || data.success === false) {
      throw new Error(data?.message || data?.detail || '保存纠正规则失败')
    }

    savedMappings.value = data.mappings || {}
    validMonitorTargets.value = (data.valid_targets && data.valid_targets.length > 0)
      ? data.valid_targets
      : defaultValidMonitorKeys
    keyMonitorSequence.value = data.latest_sequence || replaceCommandInSequence(keyMonitorSequence.value, sourceKey, targetKey)
    editableSequence.value = replaceCommandInSequence(editableSequence.value, sourceKey, targetKey)
    sequenceDirty.value = editableSequence.value !== keyMonitorSequence.value
    replaceSourceKey.value = ''
    replaceTargetKey.value = ''
    mappingError.value = ''
  } catch (error) {
    mappingError.value = error.message || '保存纠正规则失败'
  } finally {
    savingMapping.value = false
  }
}

const removeCorrectionRule = async (sourceKey) => {
  try {
    const res = await fetch(`/api/keymonitor/mappings/${encodeURIComponent(sourceKey)}`, { method: 'DELETE' })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || data.success === false) {
      throw new Error(data?.message || data?.detail || '删除纠正规则失败')
    }
    savedMappings.value = data.mappings || {}
    mappingError.value = ''
  } catch (error) {
    mappingError.value = error.message || '删除纠正规则失败'
  }
}

function compressAdjacent(seq) {
  const parts = seq.split(',').map(s => s.trim()).filter(Boolean)
  const out = []
  for (const part of parts) {
    const segs = part.split('/')
    if (segs.length < 3) {
      out.push(part)
      continue
    }
    const key = segs[0]
    const cnt = parseInt(segs[1], 10) || 1
    const delay = segs[2]
    if (delay === '*' || isNaN(cnt)) {
      out.push(`${key}/${cnt}/${delay}`)
      continue
    }
    const last = out.length > 0 ? out[out.length - 1] : null
    if (last) {
      const lastSegs = last.split('/')
      if (lastSegs.length >= 3 && lastSegs[0] === key && lastSegs[2] === delay) {
        const lastCnt = parseInt(lastSegs[1], 10) || 1
        out[out.length - 1] = `${key}/${lastCnt + cnt}/${delay}`
        continue
      }
    }
    out.push(`${key}/${cnt}/${delay}`)
  }
  return out.join(',')
}
</script>

