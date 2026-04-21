<template>
  <div class="card w-full max-w-7xl mx-auto">
    <h2 class="mb-4">Excel执行</h2>
    
    <div v-if="!selectedDevice" class="bg-yellow-50 p-4 rounded-lg mb-6">
      <p class="text-warning mb-2">请先在设备管理页面选择一个ADB设备</p>
      <router-link to="/devices" class="btn btn-primary">
        前往设备管理
      </router-link>
    </div>
    
    <div>
      <input
        ref="verifyImageFolderInput"
        type="file"
        class="hidden"
        webkitdirectory
        directory
        multiple
        @change="handleVerifyImageFolderChange"
      >

      <!-- 文件选择部分 -->
      <div class="mb-6">
        <h3 class="font-medium mb-3">选择Excel文件</h3>
        <button @click="loadExcelFiles" class="btn btn-secondary mb-4">
          刷新文件列表
        </button>
        
        <div v-if="loadingFiles">
          <p>加载中...</p>
        </div>
        
        <div v-if="excelFiles.length > 0">
          <p class="mb-3">当前目录下的Excel文件：</p>
          <div class="space-y-2 mb-4">
            <div 
              v-for="(file, index) in excelFiles" 
              :key="file" 
              class="border rounded-lg p-4 cursor-pointer hover:bg-gray-50"
              :class="selectedFile === file ? 'border-primary bg-blue-50' : ''"
              @click="selectFile(file)"
            >
              <div class="flex items-center justify-between">
                <div class="flex-1">
                  <p class="font-medium">文件 {{ index + 1 }}</p>
                  <p class="text-gray-600 truncate">{{ file }}</p>
                </div>
                <div class="flex items-center">
                  <button 
                    @click.stop="deleteFile(file)" 
                    class="btn btn-danger mr-2"
                    :disabled="executing"
                  >
                    删除
                  </button>
                  <div class="text-primary" v-if="selectedFile === file">
                    ✅
                  </div>
                </div>
              </div>
            </div>
          </div>
          
        </div>
        
        <!-- 文件上传按钮 -->
        <div class="mb-4 flex items-center gap-2">
          <input 
            type="file" 
            id="fileUpload" 
            ref="fileInput" 
            class="hidden" 
            accept=".xlsx,.xls"
            @change="uploadFile"
          >
          <label for="fileUpload" class="btn btn-primary cursor-pointer">
            上传Excel文件
          </label>
          <button @click="analyzeFile" class="btn btn-primary" :disabled="loadingAnalysis || !selectedFile">
            {{ loadingAnalysis ? '分析中...' : '分析文件' }}
          </button>
        </div>
        
        <div v-if="excelFiles.length === 0">
          <p class="text-danger mb-4">当前目录下没有找到Excel文件。</p>
          <div class="bg-yellow-50 p-4 rounded-lg mb-4">
            <h4 class="font-medium mb-2">提示：</h4>
            <p class="text-sm mb-2">
              请将Excel文件放在应用程序所在的目录中，支持 .xlsx 和 .xls 格式。
            </p>
            <p class="text-sm">
              或者使用上面的按钮上传Excel文件。
            </p>
          </div>
        </div>
      </div>
      

      
      <!-- 文件分析部分 -->
      <div v-if="selectedFile" class="mb-6">
        <!-- 验证结果显示 -->
        <div v-if="validationResult" class="mb-4">
          <div 
            class="p-4 rounded-lg"
            :class="validationResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'"
          >
            <h4 class="font-medium mb-2 flex items-center gap-2">
              <span 
                class="text-xl"
                :class="validationResult.success ? 'text-green-600' : 'text-red-600'"
              >
                {{ validationResult.success ? '✅' : '❌' }}
              </span>
              文件验证结果 - {{ validationResult.success ? '通过' : '发现问题' }}
              (共 {{ validationResult.total_rows }} 行)
            </h4>
            
            <!-- 错误列表 -->
            <div v-if="validationResult.errors && validationResult.errors.length > 0" class="mt-2">
              <p class="text-sm font-medium text-red-700 mb-1">错误列表：</p>
              <div class="text-sm text-red-600 space-y-1 max-h-40 overflow-y-auto">
                <div v-for="(error, idx) in validationResult.errors" :key="idx" class="break-all">
                  • {{ error }}
                </div>
              </div>
            </div>
            
            <!-- 警告列表 -->
            <div v-if="validationResult.warnings && validationResult.warnings.length > 0" class="mt-2">
              <p class="text-sm font-medium text-yellow-700 mb-1">警告列表：</p>
              <div class="text-sm text-yellow-600 space-y-1">
                <div v-for="(warning, idx) in validationResult.warnings" :key="idx" class="break-all">
                  • {{ warning }}
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div v-if="loadingAnalysis">
          <p>分析中...</p>
        </div>
        
        <div v-else-if="excelAnalysis">
          <div v-if="excelAnalysis.valid_rows.length > 0">
            <p class="mb-3">找到 {{ excelAnalysis.valid_rows.length }} 行有效命令：</p>
            
            <!-- 筛选和搜索功能 -->
            <div class="mb-4 flex flex-wrap gap-4 items-center">
              <div>
                <label class="form-label mr-2">筛选结果：</label>
                <select v-model="filterResult" class="form-select">
                  <option value="">全部</option>
                  <option value="PASS">PASS</option>
                  <option value="FAIL">FAIL</option>
                  <option value="empty">空</option>
                </select>
              </div>
              <div class="flex-1 min-w-[200px]">
                <label class="form-label mr-2">搜索：</label>
                <input 
                  v-model="searchKeyword" 
                  type="text" 
                  class="form-input w-full"
                  placeholder="搜索用例标题或校验图片"
                >
              </div>
            </div>
            
            <div class="mb-4 flex justify-between items-center">
              <button 
                @click="executeSelectedRows()" 
                class="btn btn-success"
                :disabled="selectedRows.length === 0"
              >
                批量执行 ({{ selectedRows.length }})
              </button>
              <button 
                @click="stopAllExecution()" 
                class="btn btn-danger"
                :disabled="!isBatchExecuting"
              >
                停止所有执行
              </button>
            </div>
            <div class="mb-4 flex flex-wrap items-center gap-3 text-sm text-gray-600">
              <span>
                校验图片文件夹：{{ verifyImageFolderName || '未选择，点击校验图片时会自动提示选择' }}
              </span>
              <button class="btn btn-secondary btn-sm" @click="triggerVerifyImageFolderPicker()">
                选择文件夹
              </button>
              <span v-if="verifyImageFileCount > 0">已索引 {{ verifyImageFileCount }} 张图片</span>
            </div>
            <div class="mb-4">
            <table class="border w-full table-auto">
                <thead class="bg-gray-100">
                  <tr>
                  <th class="border px-3 py-2 text-left" style="width: 50px;">
                      <input 
                        type="checkbox" 
                      @change="toggleSelectAll" 
                      :checked="isPageAllSelected"
                      >
                    </th>
                  <th class="border px-3 py-2 text-left">结果</th>
                  <th class="border px-3 py-2 text-left">用例标题</th>
                  <th class="border px-3 py-2 text-left" style="width: 500px;">操作步骤</th>
                  <th class="border px-3 py-2 text-left">校验图片</th>
                  <th class="border px-3 py-2 text-left">操作</th>
                  <th class="border px-3 py-2 text-left">执行结果</th>
                  </tr>
                </thead>
                <tbody>
                <tr v-for="item in pagedRows" :key="item.idx">
                    <td class="border px-3 py-2">
                      <input 
                        type="checkbox" 
                      :checked="selectedRows.includes(item.idx)" 
                      @change="toggleSelectRow(item.idx)"
                      >
                    </td>
                    <td class="border px-3 py-2">
                    <span v-if="item.row.result" :class="item.row.result.toUpperCase() === 'PASS' ? 'text-success' : 'text-danger'">
                      {{ item.row.result }}
                      </span>
                    <span v-else-if="item.row.test_result" :class="item.row.test_result.toUpperCase() === 'PASS' ? 'text-success' : 'text-danger'">
                      {{ item.row.test_result }}
                      </span>
                      <span v-else>-</span>
                    </td>
                    <td class="border px-3 py-2 whitespace-normal break-words">
                    <span v-if="item.row.title" class="text-primary">{{ item.row.title }}</span>
                      <span v-else>-</span>
                    </td>
                  <td class="border px-3 py-2 whitespace-normal break-words" style="max-width: 500px;">
                    <div v-if="item.row.step && item.row.step !== 'nan'">
                      {{ item.row.step }}
                      </div>
                    <div v-if="item.row.oriStep && item.row.oriStep !== 'nan'" class="mb-1">
                      {{ item.row.oriStep }}
                      </div>
                    <div v-if="item.row.preScript && item.row.preScript !== 'nan'">
                      {{ item.row.preScript }}
                      </div>
                    <div v-if="item.row.command && item.row.command !== 'nan'">
                      <template v-if="Array.isArray(item.row.command)">
                        <div v-for="(cmd, cmdIndex) in item.row.command" :key="cmdIndex" v-if="cmd && cmd !== 'nan'">
                            {{ cmd }}
                          </div>
                        </template>
                        <template v-else>
                        {{ item.row.command }}
                        </template>
                      </div>
                    <span v-if="(!item.row.step || item.row.step === 'nan') && (!item.row.oriStep || item.row.oriStep === 'nan') && (!item.row.preScript || item.row.preScript === 'nan') && (!item.row.command || item.row.command === 'nan')">-</span>
                    </td>
                    <td class="border px-3 py-2 whitespace-normal break-words">
                    <span v-if="item.row.verify_image && item.row.verify_image !== 'nan'" 
                          class="cursor-pointer text-primary hover:underline"
                            @click="previewVerifyImage(item.row.verify_image)">
                      {{ item.row.verify_image }}
                      </span>
                      <span v-else>-</span>
                    </td>
                    <td class="border px-3 py-2">
                      <button 
                      v-if="!executingRows[item.idx]"
                      @click="executeExcelRowByIndex(item.idx)" 
                        class="btn btn-primary"
                      >
                        执行
                      </button>
                      <button 
                        v-else
                      @click="stopExecution(item.idx)" 
                        class="btn btn-danger"
                      >
                        停止执行
                      </button>
                    </td>
                    <td class="border px-3 py-2">
                      <button 
                      v-if="rowScreenshots[item.idx]"
                      @click="showExecutionResult(item.idx)" 
                        class="btn btn-sm btn-info"
                      >
                        查看结果
                      </button>
                      <span v-else>-</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          
          <div class="flex items-center justify-between flex-wrap gap-3">
            <div class="flex items-center gap-2">
              <span>每页</span>
              <select v-model.number="pageSize" class="form-select">
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
              </select>
              <span>条</span>
            </div>
            <div class="flex items-center gap-2">
              <button class="btn btn-secondary" @click="handlePrevPage" :disabled="currentPage === 1">上一页</button>
              <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
              <div class="flex items-center gap-1">
                <span>跳转到</span>
                <input 
                  type="number" 
                  v-model.number="jumpPage" 
                  class="form-input w-16 text-center" 
                  :min="1" 
                  :max="totalPages"
                  @keyup.enter="handleJumpPage"
                >
                <button class="btn btn-primary btn-sm" @click="handleJumpPage" :disabled="!jumpPage || jumpPage < 1 || jumpPage > totalPages">跳转</button>
              </div>
              <button class="btn btn-secondary" @click="handleNextPage" :disabled="currentPage === totalPages">下一页</button>
              <span>共 {{ filteredRows.length }} 条</span>
            </div>
          </div>
            
            <div v-if="excelAnalysis.skipped_rows.length > 0" class="bg-yellow-50 p-4 rounded-lg mb-4">
              <h4 class="font-medium mb-2">跳过的行：</h4>
              <div class="space-y-2 max-h-40 overflow-y-auto">
                <div v-for="(row, index) in excelAnalysis.skipped_rows" :key="index" class="text-sm">
                  <div class="break-all">第{{ row.row }}行: {{ row.reason }}</div>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else>
            <p class="text-danger">文件中没有找到有效命令。</p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 执行日志和截图部分 -->
    <div class="fixed bottom-4 left-4 w-96 flex flex-col gap-4 z-10">
      <!-- 执行日志 -->
      <div class="bg-white border rounded-lg shadow-lg p-4">
        <h3 class="font-medium mb-2">执行日志</h3>
        <div class="border rounded-lg p-3 max-h-40 overflow-y-auto bg-gray-50">
          <div v-if="executionResults.length === 0" class="text-gray-500 italic">
            暂无执行日志
          </div>
          <div 
              v-for="(result, index) in executionResults" 
              :key="index"
              class="mb-1"
            >
              <div class="break-all" :class="{
                'text-blue-600': result.status === 'info',
                'text-green-600': result.status === 'success',
                'text-red-600': result.status === 'error'
              }">
                {{ result.message }}
              </div>
            </div>
        </div>
      </div>
      
      
    </div>
  </div>

  <!-- 执行结果弹窗 -->
  <div v-if="showScreenshotModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl p-4 w-[95vw] max-w-[95vw] h-[90vh] max-h-[90vh] overflow-hidden flex flex-col">
      <div class="flex justify-between items-center mb-2">
        <div>
          <h3 class="text-lg font-medium">执行结果对比</h3>
          <p v-if="modalResultTitle" class="text-sm text-gray-500 mt-1">
            {{ modalResultTitle }}
          </p>
        </div>
        <button @click="showScreenshotModal = false" class="text-gray-500 hover:text-gray-700">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <span v-if="modalResultStatus"
          class="px-3 py-1 rounded-full font-medium"
          :class="modalResultStatus === 'PASS' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
        >
          {{ modalResultStatus }}
        </span>
        <span v-if="modalResultScore !== null" class="text-gray-600">
          匹配分数: {{ Number(modalResultScore).toFixed(3) }}
        </span>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0 overflow-auto">
        <div class="border rounded-lg p-3 flex flex-col min-h-[320px]">
          <h4 class="font-medium mb-3">ADB截图</h4>
          <div class="flex-1 flex justify-center items-center bg-gray-50 rounded-lg overflow-hidden">
            <img 
              v-if="modalScreenshotUrl"
              :src="modalScreenshotUrl + '?t=' + Date.now()" 
              class="max-h-full max-w-full object-contain" 
              alt="执行截图"
            >
            <span v-else class="text-gray-400">暂无截图</span>
          </div>
        </div>
        <div class="border rounded-lg p-3 flex flex-col min-h-[320px]">
          <h4 class="font-medium mb-3">用例校验图</h4>
          <p v-if="modalVerifyImageName" class="text-sm text-gray-500 mb-2">{{ modalVerifyImageName }}</p>
          <div class="flex-1 flex justify-center items-center bg-gray-50 rounded-lg overflow-hidden">
            <img 
              v-if="modalVerifyImageUrl"
              :src="modalVerifyImageUrl" 
              class="max-h-full max-w-full object-contain" 
              alt="校验图片"
            >
            <span v-else class="text-gray-400">该用例未配置校验图</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- 校验图片预览弹窗 -->
  <div v-if="showVerifyImageModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl p-4 w-[90vw] max-w-[90vw] h-[90vh] max-h-[90vh] overflow-hidden">
      <div class="flex justify-between items-center mb-2">
        <div>
          <h3 class="text-lg font-medium">校验图片预览</h3>
          <p v-if="verifyImagePreviewName" class="text-sm text-gray-500 mt-1">{{ verifyImagePreviewName }}</p>
        </div>
        <button @click="showVerifyImageModal = false" class="text-gray-500 hover:text-gray-700">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="flex justify-center items-center h-[calc(90vh-60px)]">
        <img 
          v-if="verifyImageUrl"
          :src="verifyImageUrl" 
          class="max-h-full max-w-full object-contain" 
          alt="校验图片"
        >
        <span v-else class="text-gray-400">未找到同名校验图片</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, onUnmounted } from 'vue'
import { useRouter, useRoute, onBeforeRouteLeave } from 'vue-router'

// 状态管理
const selectedDevice = ref('')
const excelFiles = ref([])
const selectedFile = ref('')
const excelAnalysis = ref(null)
const validationResult = ref(null)
const executionResults = ref([])
const rowIndex = ref(1)
const loadingFiles = ref(false)
const loadingAnalysis = ref(false)
const executingRows = ref({})
const stopExecutionFlags = ref({})
const selectedRows = ref([])
const filterResult = ref('')
const searchKeyword = ref('')
const rowScreenshots = ref({})
const rowResultMeta = ref({})
const showScreenshotModal = ref(false)
const modalScreenshotUrl = ref('')
const modalVerifyImageUrl = ref('')
const modalVerifyImageName = ref('')
const modalResultTitle = ref('')
const modalResultStatus = ref('')
const modalResultScore = ref(null)
const showVerifyImageModal = ref(false)
const verifyImageUrl = ref('')
const verifyImagePreviewName = ref('')
const verifyImageFolderInput = ref(null)
const verifyImageFolderName = ref('')
const verifyImageFileCount = ref(0)
const localVerifyImageMap = ref({})
const pendingVerifyImageRequest = ref(null)
const currentPage = ref(1)
const jumpPage = ref(1)
const pageSize = ref(20)
const isBatchExecuting = ref(false)

// 路由实例
const router = useRouter()
const route = useRoute()

// 导航守卫，处理页面离开时的确认

onBeforeRouteLeave((to, from, next) => {
  // 检查是否有截图
  if (Object.keys(rowScreenshots.value).length > 0) {
    const confirmLeave = confirm('您正在前往其它页面，将清除测试用例结果的图片')
    if (confirmLeave) {
      // 调用API删除所有截图
      fetch('/api/screenshot/clear', {
        method: 'DELETE'
      })
      .then(response => response.json())
      .then(data => {
        console.log('清除截图成功:', data)
        // 清除前端截图状态
        Object.keys(rowScreenshots.value).forEach(key => {
          delete rowScreenshots.value[key]
        })
        // 强制响应式更新
        rowScreenshots.value = { ...rowScreenshots.value }
        next()
      })
      .catch(error => {
        console.error('清除截图失败:', error)
        // 即使API调用失败，也要继续导航
        rowScreenshots.value = {}
        next()
      })
    } else {
      // 取消导航
      next(false)
    }
  } else {
    // 没有截图，直接离开
    next()
  }
})

onUnmounted(() => {
  clearLocalVerifyImageCache()
})

 



// 计算属性：筛选和搜索后的行
const filteredRows = computed(() => {
  if (!excelAnalysis.value || !excelAnalysis.value.valid_rows) return []
  let items = excelAnalysis.value.valid_rows.map((row, i) => ({ row, idx: i + 1 }))
  if (filterResult.value) {
    if (filterResult.value === 'empty') {
      items = items.filter(x => !x.row.test_result || x.row.test_result === '')
    } else {
      items = items.filter(x => {
        const result = x.row.test_result || ''
        return result.toUpperCase() === filterResult.value
      })
    }
  }
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    items = items.filter(x => {
      if (x.row.title && String(x.row.title).toLowerCase().includes(keyword)) return true
      if (x.row.verify_image && String(x.row.verify_image).toLowerCase().includes(keyword)) return true
      return false
    })
  }
  return items
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value)))
const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})
const isPageAllSelected = computed(() => {
  if (pagedRows.value.length === 0) return false
  const pageIdxs = pagedRows.value.map(x => x.idx)
  return pageIdxs.every(id => selectedRows.value.includes(id))
})

// 加载当前设备
onMounted(async () => {
  await loadCurrentDevice()
  await loadExcelFiles()
})

// 加载当前设备
const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    selectedDevice.value = data.device
  } catch (error) {
    console.error('获取当前设备失败:', error)
  }
}

// 加载Excel文件列表
const loadExcelFiles = async () => {
  loadingFiles.value = true
  try {
    const response = await fetch('/api/excel/files')
    const data = await response.json()
    excelFiles.value = data.files
  } catch (error) {
    console.error('获取Excel文件列表失败:', error)
  } finally {
    loadingFiles.value = false
  }
}

// 选择文件
const selectFile = (file) => {
  selectedFile.value = file
  excelAnalysis.value = null
  validationResult.value = null
  executionResults.value = []
  rowScreenshots.value = {}
  rowResultMeta.value = {}
  rowIndex.value = 1
}

const normalizeVerifyImageName = (imageName) => {
  return String(imageName || '')
    .split(/[/\\]/)
    .pop()
    ?.trim()
    .toLowerCase() || ''
}

const getLocalVerifyImageEntry = (imageName) => {
  const key = normalizeVerifyImageName(imageName)
  return key ? localVerifyImageMap.value[key] || null : null
}

const clearLocalVerifyImageCache = () => {
  Object.values(localVerifyImageMap.value).forEach((entry) => {
    if (entry?.url) {
      URL.revokeObjectURL(entry.url)
    }
  })
  localVerifyImageMap.value = {}
  verifyImageFileCount.value = 0
  verifyImageFolderName.value = ''
}

const triggerVerifyImageFolderPicker = (request = null) => {
  pendingVerifyImageRequest.value = request
  verifyImageFolderInput.value?.click()
}

const inferFolderName = (files) => {
  const firstFile = files[0]
  if (!firstFile) return ''
  const relativePath = firstFile.webkitRelativePath || ''
  if (!relativePath.includes('/')) return '已选择本地文件夹'
  return relativePath.split('/')[0]
}

const applyVerifyImagePreview = (imageName) => {
  const matchedEntry = getLocalVerifyImageEntry(imageName)
  if (!matchedEntry) {
    return false
  }

  verifyImagePreviewName.value = matchedEntry.relativePath || matchedEntry.name
  verifyImageUrl.value = matchedEntry.url
  showVerifyImageModal.value = true
  return true
}

const openExecutionResultModal = (rowIndex, matchedEntry = null) => {
  const rowData = excelAnalysis.value?.valid_rows?.[rowIndex - 1]
  if (!rowData || !rowScreenshots.value[rowIndex]) {
    return
  }

  const verifyImageName = rowData.verify_image && rowData.verify_image !== 'nan'
    ? rowData.verify_image
    : ''

  modalScreenshotUrl.value = rowScreenshots.value[rowIndex]
  modalVerifyImageName.value = matchedEntry
    ? (matchedEntry.relativePath || matchedEntry.name)
    : verifyImageName
  modalVerifyImageUrl.value = matchedEntry?.url || ''
  modalResultTitle.value = rowData.title || `第 ${rowIndex} 行`
  modalResultStatus.value = rowResultMeta.value[rowIndex]?.verify_result || rowData.result || rowData.test_result || ''
  modalResultScore.value = rowResultMeta.value[rowIndex]?.score ?? null
  showScreenshotModal.value = true
}

const handleVerifyImageFolderChange = (event) => {
  const files = Array.from(event.target.files || [])
  const pendingRequest = pendingVerifyImageRequest.value
  pendingVerifyImageRequest.value = null

  if (verifyImageFolderInput.value) {
    verifyImageFolderInput.value.value = ''
  }

  if (files.length === 0) {
    return
  }

  clearLocalVerifyImageCache()

  const nextImageMap = {}
  for (const file of files) {
    const isImageFile = file.type.startsWith('image/') || /\.(png|jpg|jpeg|bmp|webp)$/i.test(file.name)
    if (!isImageFile) {
      continue
    }

    const key = normalizeVerifyImageName(file.name)
    if (!key || nextImageMap[key]) {
      continue
    }

    nextImageMap[key] = {
      name: file.name,
      relativePath: file.webkitRelativePath || file.name,
      url: URL.createObjectURL(file),
      file
    }
  }

  localVerifyImageMap.value = nextImageMap
  verifyImageFileCount.value = Object.keys(nextImageMap).length
  verifyImageFolderName.value = inferFolderName(files)

  if (!pendingRequest) {
    return
  }

  if (pendingRequest.mode === 'preview') {
    if (!applyVerifyImagePreview(pendingRequest.imageName)) {
      alert(`在所选文件夹中未找到同名图片：${pendingRequest.imageName}`)
    }
    return
  }

  if (pendingRequest.mode === 'result') {
    const matchedEntry = getLocalVerifyImageEntry(pendingRequest.imageName)
    openExecutionResultModal(pendingRequest.rowIndex, matchedEntry)
    if (!matchedEntry) {
      alert(`在所选文件夹中未找到同名图片：${pendingRequest.imageName}`)
    }
  }
}

// 分析文件
const analyzeFile = async () => {
  if (!selectedFile.value) {
    alert('请先选择一个Excel文件')
    return
  }
  
  loadingAnalysis.value = true
  try {
    // 首先调用验证功能
    const validateResponse = await fetch(`/api/excel/validate?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!validateResponse.ok) {
      throw new Error('验证文件失败')
    }
    const validateData = await validateResponse.json()
    validationResult.value = validateData
    
    // 如果验证失败，不继续分析，让用户查看错误
    if (!validateData.success) {
      alert('文件验证发现问题，请查看下方的验证结果')
      // 即使验证失败，仍然可以继续分析，让用户自己决定
    }
    
    // 继续调用分析功能
    const response = await fetch(`/api/excel/analyze?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!response.ok) {
      throw new Error('分析文件失败')
    }
    const data = await response.json()
    excelAnalysis.value = data
    // 分析完成后默认筛选全部的行，按照Excel里原本的表格顺序
    filterResult.value = ''
  } catch (error) {
    console.error('分析文件失败:', error)
    alert('分析文件失败: ' + error.message)
  } finally {
    loadingAnalysis.value = false
  }
}

// 执行Excel行（通过输入框）
const executeExcelRow = async () => {
  await executeExcelRowByIndex(rowIndex.value)
}

const readFileAsBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      resolve(result.includes(',') ? result.split(',')[1] : result)
    }
    reader.onerror = () => reject(new Error('读取校验图片失败'))
    reader.readAsDataURL(file)
  })
}

const buildExecutionPayload = async (index) => {
  const payload = {
    file_name: selectedFile.value,
    row_index: index
  }

  const rowData = excelAnalysis.value?.valid_rows?.[index - 1]
  if (!rowData?.verify_image) {
    return payload
  }

  const matchedEntry = getLocalVerifyImageEntry(rowData.verify_image)
  if (!matchedEntry?.file) {
    return payload
  }

  payload.verify_image_base64 = await readFileAsBase64(matchedEntry.file)
  return payload
}



// 执行Excel行（通过点击按钮）
const executeExcelRowByIndex = (index) => {
  return new Promise((resolve) => {
    if (!selectedFile.value) {
      alert('请先选择一个Excel文件')
      resolve()
      return
    }
    
    if (!index || index < 1 || index > excelAnalysis.value.valid_rows.length) {
      alert('请输入有效的行号')
      resolve()
      return
    }
    
    // 设置当前行的执行状态为true
    executingRows.value[index] = true
    // 重置停止标志
    stopExecutionFlags.value[index] = false
    // 只在非批量执行时清空日志
    if (!isBatchExecuting.value) {
      executionResults.value = []
    }

    buildExecutionPayload(index)
    .then((payload) => fetch('/api/excel/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }))
    .then(response => {
      if (!response.ok) {
        throw new Error('执行命令失败')
      }
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      // 读取流数据
      const readChunk = () => {
        // 检查是否停止执行
        if (stopExecutionFlags.value[index]) {
          reader.cancel()
          executingRows.value[index] = false
          executionResults.value.push({
            status: 'error',
            message: '执行已停止'
          })
          resolve()
          return
        }
        
        reader.read().then(({ done, value }) => {
          if (done) {
            // 执行完成
            executingRows.value[index] = false
            resolve()
            return
          }
          
          // 解码数据
          buffer += decoder.decode(value, { stream: true })
          
          // 处理SSE格式的数据
          const lines = buffer.split('\n')
          buffer = lines.pop() // 保留不完整的行
          
          lines.forEach(line => {
            if (line.startsWith('data:')) {
              const data = line.substring(5).trim()
              if (data) {
                try {
                  const result = JSON.parse(data)
                  // 添加到执行结果
                  executionResults.value.push(result)
                  // 如果有截图URL，记录当前行的截图URL
                  if (result.screenshot_url) {
                    rowScreenshots.value[index] = result.screenshot_url
                  }
                  // 如果有验证结果，更新执行结果
                  if (result.verify_result) {
                    rowResultMeta.value[index] = {
                      verify_result: result.verify_result,
                      score: result.score ?? null
                    }
                    // 找到对应的行并更新结果
                    const rowData = excelAnalysis.value.valid_rows[index - 1]
                    if (rowData) {
                      rowData.result = result.verify_result
                    }
                  }
                } catch (e) {
                  console.error('解析数据失败:', e)
                }
              }
            }
          })
          
          // 继续读取
          readChunk()
        })
        .catch(error => {
          console.error('读取流失败:', error)
          executionResults.value.push({
            status: 'error',
            message: '执行命令失败：' + error.message
          })
          executingRows.value[index] = false
          resolve()
        })
      }
      
      // 开始读取
      readChunk()
    })
    .catch(error => {
      console.error('执行命令失败:', error)
      executionResults.value = [
        { status: 'error', message: '执行命令失败：' + error.message }
      ]
      executingRows.value[index] = false
      resolve()
    })
  })
}

// 停止执行
const stopExecution = (index) => {
  stopExecutionFlags.value[index] = true
}

// 显示执行结果
const showExecutionResult = (rowIndex) => {
  const rowData = excelAnalysis.value?.valid_rows?.[rowIndex - 1]
  if (!rowScreenshots.value[rowIndex] || !rowData) {
    return
  }

  const verifyImageName = rowData.verify_image && rowData.verify_image !== 'nan'
    ? rowData.verify_image
    : ''

  if (!verifyImageName) {
    openExecutionResultModal(rowIndex, null)
    return
  }

  const matchedEntry = getLocalVerifyImageEntry(verifyImageName)
  if (matchedEntry) {
    openExecutionResultModal(rowIndex, matchedEntry)
    return
  }

  triggerVerifyImageFolderPicker({
    mode: 'result',
    rowIndex,
    imageName: verifyImageName
  })
}

// 预览校验图片
const previewVerifyImage = (imageName) => {
  if (!imageName || imageName === 'nan') {
    return
  }

  if (applyVerifyImagePreview(imageName)) {
    return
  }

  triggerVerifyImageFolderPicker({
    mode: 'preview',
    imageName
  })
}

// 切换单行选择
const toggleSelectRow = (rowIndex) => {
  const index = selectedRows.value.indexOf(rowIndex)
  if (index > -1) {
    selectedRows.value.splice(index, 1)
  } else {
    selectedRows.value.push(rowIndex)
  }
  selectedRows.value = Array.from(new Set(selectedRows.value)).sort((a, b) => a - b)
}

// 全选/取消全选
const toggleSelectAll = () => {
  const pageIds = pagedRows.value.map(x => x.idx)
  const allSelected = pageIds.every(id => selectedRows.value.includes(id))
  if (allSelected) {
    selectedRows.value = selectedRows.value.filter(id => !pageIds.includes(id))
  } else {
    selectedRows.value = Array.from(new Set([...selectedRows.value, ...pageIds])).sort((a, b) => a - b)
  }
}

// 批量执行选中的行
const executeSelectedRows = async () => {
  if (selectedRows.value.length === 0) return
  
  // 设置批量执行标志
  isBatchExecuting.value = true
  
  try {
    // 按顺序执行选中的行
    const ordered = Array.from(new Set(selectedRows.value)).sort((a, b) => a - b)
    for (const rowIndex of ordered) {
      // 检查是否已经触发了停止命令
      if (!isBatchExecuting.value) break
      
      await executeExcelRowByIndex(rowIndex)
      // 等待一段时间再执行下一行
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  } finally {
    // 执行完成后清除标志
    isBatchExecuting.value = false
  }
}

// 停止所有执行
const stopAllExecution = () => {
  isBatchExecuting.value = false
  
  // 为所有正在执行的行设置停止标志
  for (const rowIndex in executingRows.value) {
    if (executingRows.value[rowIndex]) {
      stopExecutionFlags.value[rowIndex] = true
    }
  }
  
  // 显示停止消息
  executionResults.value.push({
    status: 'info',
    message: '所有执行已停止'
  })
}

// 处理上一页点击
const handlePrevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    selectedRows.value = []
  }
}

// 处理下一页点击
const handleNextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    selectedRows.value = []
  }
}

// 处理跳转到指定页码
const handleJumpPage = () => {
  const page = parseInt(jumpPage.value)
  if (page && page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    selectedRows.value = []
  }
}

// 监听页码变化，更新跳转输入框
watch(currentPage, (newPage) => {
  jumpPage.value = newPage
})

// 上传文件
const fileInput = ref(null)
const uploadFile = async (event) => {
  const file = event.target.files[0]
  if (!file) {
    return
  }
  
  const formData = new FormData()
  formData.append('file', file)
  
  try {
    const response = await fetch('/api/excel/upload', {
      method: 'POST',
      body: formData
    })
    
    if (!response.ok) {
      throw new Error('上传文件失败')
    }
    
    const data = await response.json()
    alert('文件上传成功: ' + data.filename)
    // 刷新文件列表
    await loadExcelFiles()
    // 选择上传的文件
    selectFile(data.filename)
  } catch (error) {
    console.error('上传文件失败:', error)
    alert('上传文件失败: ' + error.message)
  } finally {
    // 重置文件输入
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

// 删除文件
const executing = ref(false)
const deleteFile = async (file) => {
  if (confirm(`确定要删除文件 ${file} 吗？`)) {
    executing.value = true
    try {
      const response = await fetch(`/api/excel/delete?file_name=${encodeURIComponent(file)}`, {
        method: 'DELETE'
      })
      
      if (!response.ok) {
        throw new Error('删除文件失败')
      }
      
      const data = await response.json()
      alert(data.message)
      
      // 刷新文件列表
      await loadExcelFiles()
      
      // 如果删除的是当前选中的文件，清除选中状态
      if (selectedFile.value === file) {
        selectedFile.value = ''
        excelAnalysis.value = null
        executionResults.value = []
      }
    } catch (error) {
      console.error('删除文件失败:', error)
      alert('删除文件失败: ' + error.message)
    } finally {
      executing.value = false
    }
  }
}
</script>
