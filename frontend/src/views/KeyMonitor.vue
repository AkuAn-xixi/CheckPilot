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
          <div class="flex items-center gap-2">
            <select v-model="selectedExcel" class="form-select min-w-[220px]">
              <option value="" disabled>选择目标Excel文件</option>
              <option v-for="f in excelFiles" :key="f" :value="f">{{ f }}</option>
            </select>
            <button 
              @click="writeToExcel"
              class="btn btn-success"
              :disabled="!selectedExcel || !keyMonitorSequence || keyMonitorActive || isStarting"
              title="停止监听后写入到Excel"
            >
              写入到Excel
            </button>
          </div>
          <button 
            @click="copySequence"
            class="btn btn-primary"
            :disabled="!keyMonitorSequence || keyMonitorActive || isStarting"
            title="监听未进行时才可复制"
          >
            复制序列
          </button>
        </div>
        <div class="border rounded p-3 bg-gray-50 min-h-[120px] font-mono text-sm whitespace-pre-wrap w-full overflow-auto">
          <template v-if="displayParts.length > 0">
            <template v-for="(part, idx) in displayParts" :key="idx">
              <span>
                <template v-for="(seg, sIdx) in splitPart(part)" :key="sIdx">
                  <span v-if="sIdx === 2 && seg === '*'" class="text-gray-400">*</span>
                  <span v-else>{{ seg }}</span>
                  <span v-if="sIdx < 2">/</span>
                </template>
              </span>
              <span v-if="idx < displayParts.length - 1">, </span>
            </template>
          </template>
          <template v-else>
            <span class="text-gray-400">监听到的按键序列会显示在这里，格式为 KEY/次数/延迟,KEY/次数/延迟</span>
          </template>
        </div>
        <div class="text-sm text-gray-500 mt-2" v-if="keyMonitorActive && !keyMonitorSequence">
          正在监听，请在设备上按键…
        </div>
        <div class="text-sm text-danger mt-2" v-if="keyMonitorError">
          {{ keyMonitorError }}
        </div>
        <div class="mt-6">
          <div class="flex items-center gap-2 mb-2">
            <h3 class="font-medium">Excel 文件分析</h3>
            <button class="btn btn-secondary" @click="analyzeExcel" :disabled="!selectedExcel || keyMonitorActive || isStarting">
              分析文件
            </button>
          </div>
          <div v-if="loadingPreview">加载中…</div>
          <div v-else-if="previewColumns.length > 0" class="overflow-x-auto w-full">
            <table class="border w-full table-auto">
              <thead class="bg-gray-100">
                <tr>
                  <th v-for="c in previewColumns" :key="c" class="border px-3 py-2 text-left max-w-[220px] whitespace-normal break-words">
                    {{ c }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rIdx) in previewRows" :key="rIdx">
                  <td 
                    v-for="c in previewColumns" 
                    :key="c" 
                    class="border px-3 py-2 text-left max-w-[220px] whitespace-normal break-words cursor-pointer"
                    :class="isSelectedCell(rIdx, c) ? 'bg-yellow-100' : ''"
                    @click="selectCell(rIdx, c)"
                    title="点击选择为写入目标"
                  >
                    {{ row[c] ?? '' }}
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="text-sm text-gray-500 mt-2">
              总行数：{{ previewTotal }} （展示前 {{ previewRows.length }} 行）
            </div>
          </div>
          <div v-else class="text-sm text-gray-500">
            选择文件后点击“分析文件”查看全部列
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'

const selectedDevice = ref('')
const keyMonitorActive = ref(false)
const keyMonitorSequence = ref('')
const keyMonitorError = ref('')
let statusTimer = null
const apiUnavailable = ref(false)
const isStarting = ref(false)
const excelFiles = ref([])
const selectedExcel = ref('')
const loadingPreview = ref(false)
const previewColumns = ref([])
const previewRows = ref([])
const previewTotal = ref(0)
const selectedRow = ref(null)
const selectedCol = ref('')
const displayParts = computed(() => {
  const s = keyMonitorSequence.value || ''
  return s.split(',').map(i => i.trim()).filter(Boolean)
})
const splitPart = (p) => p.split('/')

onMounted(async () => {
  await loadCurrentDevice()
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

const startStatusPolling = () => {
  statusTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/keymonitor/status')
      if (res.ok) {
        const data = await res.json()
        keyMonitorActive.value = data.active
        if (data.active) {
          isStarting.value = false
          keyMonitorSequence.value = data.live_sequence || ''
        } else {
          if (!isStarting.value) {
            keyMonitorSequence.value = data.latest_sequence || ''
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
  keyMonitorSequence.value = ''
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

const loadExcelFiles = async () => {
  try {
    const res = await fetch('/api/excel/files')
    if (res.ok) {
      const data = await res.json()
      excelFiles.value = data.files || []
      if (!selectedExcel.value && excelFiles.value.length > 0) {
        selectedExcel.value = excelFiles.value[0]
      }
    }
  } catch {}
}

const writeToExcel = async () => {
  if (keyMonitorActive.value || isStarting.value) {
    alert('监听进行中，停止后再写入')
    return
  }
  if (!selectedExcel.value) {
    alert('请选择目标Excel文件')
    return
  }
  if (!keyMonitorSequence.value) {
    alert('当前没有可写入的序列')
    return
  }
  if (selectedRow.value === null || !selectedCol.value) {
    alert('请在下方表格中选择一个单元格作为写入目标')
    return
  }
  const seq = compressAdjacent(keyMonitorSequence.value)
  try {
    const res = await fetch('/api/excel/write_cell', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: selectedExcel.value, column_name: selectedCol.value, row_index: selectedRow.value, value: seq })
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail || '写入失败')
    }
    await analyzeExcel()
    alert('写入成功：已写入所选单元格')
  } catch (e) {
    alert(`写入失败：${e.message}`)
  }
}

const analyzeExcel = async () => {
  if (!selectedExcel.value) {
    alert('请选择目标Excel文件')
    return
  }
  loadingPreview.value = true
  previewColumns.value = []
  previewRows.value = []
  try {
    const url = `/api/excel/preview?file_name=${encodeURIComponent(selectedExcel.value)}`
    const res = await fetch(url)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail || '分析失败')
    }
    const data = await res.json()
    previewColumns.value = data.columns || []
    previewRows.value = data.rows || []
    previewTotal.value = data.row_count || previewRows.value.length
  } catch (e) {
    alert(`分析失败：${e.message}`)
  } finally {
    loadingPreview.value = false
  }
}

const selectCell = (r, c) => {
  if (keyMonitorActive.value || isStarting.value) return
  selectedRow.value = r
  selectedCol.value = c
}
const isSelectedCell = (r, c) => {
  return selectedRow.value === r && selectedCol.value === c
}

const stopKeyMonitor = async () => {
  try {
    const res = await fetch('/api/keymonitor/stop', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      keyMonitorActive.value = false
      isStarting.value = false
      if (data.sequence) keyMonitorSequence.value = data.sequence
      apiUnavailable.value = false
    }
  } catch {}
}

const copySequence = async () => {
  if (keyMonitorActive.value || isStarting.value) {
    alert('监听进行中，停止后再复制序列')
    return
  }
  if (!keyMonitorSequence.value) return
  const compressed = compressAdjacent(keyMonitorSequence.value)
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
  return out.join(', ')
}
</script>

