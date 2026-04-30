<template>
  <div class="card w-full max-w-7xl mx-auto excel-execution-page">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <router-link to="/excel" class="btn btn-secondary btn-sm">
        返回功能选择
      </router-link>
      <h2 class="mb-0">ASR 校验执行</h2>
    </div>

    <div class="excel-execution-scroll">
      <div class="space-y-6">
      <section class="rounded-[28px] border border-white/70 bg-white/72 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div class="min-w-0">
            <p class="eyebrow">Excel ASR</p>
            <h3 class="mt-2 text-xl font-semibold tracking-tight text-slate-900">环境与文件准备</h3>
            <p class="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
              选择 Excel 后可逐条执行、批量执行已选用例，或直接串行执行当前文件中的全部 ASR 用例。
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <button class="btn btn-secondary btn-sm" @click="loadStatus" :disabled="loadingStatus">
              {{ loadingStatus ? '刷新中...' : '刷新状态' }}
            </button>
          </div>
        </div>

        <div v-if="statusErrorMessage" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {{ statusErrorMessage }}
        </div>

        <div v-if="missingAsrDependencies.length" class="mt-4 rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-amber-900">
          <p class="font-medium">当前后端环境未完成 ASR 准备，执行按钮已提前禁用。</p>
          <p class="mt-2">当前 Python：{{ asrDependencyStatus.python_version || '未知' }}</p>
          <p>建议 Python：{{ asrDependencyStatus.recommended_python_version || '3.12' }}</p>
          <p class="mt-1 leading-6">缺少依赖：{{ missingAsrDependencies.join('、') }}</p>

          <div v-if="asrDependencyStatus.notes?.length" class="mt-3 space-y-1 text-xs leading-5 text-amber-800">
            <div v-for="(note, index) in asrDependencyStatus.notes" :key="index">{{ note }}</div>
          </div>

          <div v-if="asrDependencyStatus.install_steps?.length" class="mt-4 rounded-lg bg-white/70 p-4">
            <p class="text-sm font-medium mb-2">处理步骤：</p>
            <div class="space-y-1 text-sm leading-6">
              <div v-for="(step, index) in asrDependencyStatus.install_steps" :key="index">
                {{ index + 1 }}. {{ step }}
              </div>
            </div>
          </div>

          <div v-if="asrDependencyStatus.install_commands?.length" class="mt-4 rounded-lg bg-slate-950 p-4 font-mono text-xs leading-6 text-slate-100">
            <div v-for="(command, index) in asrDependencyStatus.install_commands" :key="index">{{ command }}</div>
          </div>
        </div>
      </section>

      <div class="mb-6">
        <h3 class="font-medium mb-3">选择Excel文件</h3>
        <button @click="loadExcelFiles" class="btn btn-secondary mb-4" :disabled="loadingFiles">
          {{ loadingFiles ? '刷新中...' : '刷新文件列表' }}
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
              <div class="flex items-center justify-between gap-4">
                <div class="flex-1 min-w-0">
                  <p class="font-medium">文件 {{ index + 1 }}</p>
                  <p class="text-gray-600 truncate">{{ file }}</p>
                </div>
                <div class="flex items-center gap-2">
                  <button class="btn btn-danger" @click.stop="deleteFile(file)" :disabled="deletingFile">
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

        <div class="mb-4 flex items-center gap-2">
          <button class="btn btn-primary" @click="triggerExcelUpload">上传Excel文件</button>
          <button @click="analyzeFile" class="btn btn-primary" :disabled="loadingAnalysis || !selectedFile">
            {{ loadingAnalysis ? '分析中...' : '分析文件' }}
          </button>
        </div>

        <div v-if="excelFiles.length === 0">
          <p class="text-danger mb-4">当前目录下没有找到Excel文件。</p>
          <div class="bg-yellow-50 p-4 rounded-lg mb-4">
            <h4 class="font-medium mb-2">提示：</h4>
            <p class="text-sm mb-2">请将 Excel 文件放在应用程序所在的目录中，支持 .xlsx 和 .xls 格式。</p>
            <p class="text-sm">或者使用上面的按钮上传 Excel 文件。</p>
          </div>
        </div>
      </div>

      <div class="mb-6 rounded-[28px] border border-white/70 bg-white/65 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_20px_44px_rgba(15,23,42,0.08)]">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div class="min-w-0">
            <p class="eyebrow">Model Setup</p>
            <div class="mt-2 flex flex-wrap items-center gap-3">
              <h3 class="text-lg font-semibold tracking-tight">模型导入与切换</h3>
              <span class="rounded-full bg-white/80 px-3 py-1 text-sm text-gray-500">
                {{ activeModelName ? `当前模型：${activeModelName}` : '未选择模型' }}
              </span>
            </div>
            <p class="mt-2 text-sm leading-6 text-gray-500">
              导入模型目录后即可在这里切换当前模型，ASR 执行会直接沿用当前选择。
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button class="btn btn-secondary btn-sm" @click="loadStatus" :disabled="loadingStatus || importingModel || selectingModel || deletingModel">
              {{ loadingStatus ? '刷新中...' : '刷新状态' }}
            </button>
            <button class="btn btn-primary btn-sm" @click="triggerModelFolderPicker" :disabled="importingModel || selectingModel || deletingModel">
              {{ importingModel ? `导入中 ${modelImportProgress.completed}/${modelImportProgress.total}` : '导入模型目录' }}
            </button>
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-3 text-sm text-gray-600">
          <span>已导入模型：{{ status.imported_models?.length || 0 }} 个</span>
          <span>当前设备：{{ selectedDevice || '未选择' }}</span>
          <span :class="missingAsrDependencies.length ? 'text-warning' : 'text-success'">
            环境状态：{{ missingAsrDependencies.length ? '缺少依赖' : '已就绪' }}
          </span>
        </div>

        <div v-if="modelImportMessage" class="mt-4 rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-800">
          {{ modelImportMessage }}
        </div>

        <div v-if="status.imported_models?.length" class="space-y-2 mt-4">
          <div v-for="model in status.imported_models" :key="model.name" class="border rounded-lg p-4 bg-white/80">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div class="flex-1 min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <p class="font-medium">{{ model.name }}</p>
                  <span v-if="model.is_active" class="rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700">当前使用</span>
                  <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{{ model.file_count }} 个文件</span>
                </div>
                <p class="text-gray-500 text-sm break-all mt-2">{{ model.path }}</p>
              </div>
              <div class="flex items-center gap-2">
                <button class="btn btn-secondary" @click="selectModel(model.name)" :disabled="selectingModel || deletingModel || importingModel || model.is_active">
                  {{ model.is_active ? '已选中' : '设为当前模型' }}
                </button>
                <button class="btn btn-danger" @click="deleteModel(model.name)" :disabled="deletingModel || selectingModel || importingModel">
                  删除
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="mt-4 bg-yellow-50 p-4 rounded-lg">
          <p class="text-sm text-gray-600">还没有导入模型。请先导入本地模型目录，再执行 ASR 用例。</p>
        </div>
      </div>

      <div v-if="selectedFile" class="mb-6">
        <div v-if="validationResult" ref="analysisSection" class="mb-4">
          <div class="p-4 rounded-lg" :class="validationResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'">
            <h4 class="font-medium mb-2 flex items-center gap-2">
              <span class="text-xl" :class="validationResult.success ? 'text-green-600' : 'text-red-600'">
                {{ validationResult.success ? '✅' : '❌' }}
              </span>
              文件验证结果 - {{ validationResult.success ? '通过' : '发现问题' }} (共 {{ validationResult.total_rows }} 行)
            </h4>

            <div v-if="validationResult.errors && validationResult.errors.length > 0" class="mt-2">
              <p class="text-sm font-medium text-red-700 mb-1">错误列表：</p>
              <div class="text-sm text-red-600 space-y-1 max-h-40 overflow-y-auto">
                <div v-for="(error, idx) in validationResult.errors" :key="idx" class="break-all">
                  • {{ error }}
                </div>
              </div>
            </div>

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

            <div class="mb-4 flex flex-wrap gap-4 items-center">
              <div class="flex-1 min-w-[200px]">
                <label class="form-label mr-2">搜索：</label>
                <input
                  v-model="searchKeyword"
                  type="text"
                  class="form-input w-full"
                  placeholder="搜索用例标题或步骤内容"
                >
              </div>
            </div>

            <div class="mb-4 flex justify-between items-center gap-3 flex-wrap">
              <div class="flex flex-wrap items-center gap-3">
                <button class="btn btn-success" @click="executeSelectedRows" :disabled="selectedRows.length === 0 || isBatchExecuting || hasActiveExecution || !canExecuteAsr">
                  批量执行 ({{ selectedRows.length }})
                </button>
                <button class="btn btn-primary" @click="executeAllRows" :disabled="allRowIndexes.length === 0 || isBatchExecuting || hasActiveExecution || !canExecuteAsr">
                  执行全部用例 ({{ allRowIndexes.length }})
                </button>
              </div>
              <button class="btn btn-danger" @click="stopAllExecution" :disabled="!isBatchExecuting">
                停止所有执行
              </button>
            </div>

            <section class="mb-5 rounded-[28px] border border-white/70 bg-white/65 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_20px_44px_rgba(15,23,42,0.08)]">
              <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div class="min-w-0">
                  <p class="eyebrow">Execution Console</p>
                  <div class="mt-2 flex flex-wrap items-center gap-3">
                    <h3 class="text-lg font-semibold tracking-tight">执行日志</h3>
                    <span class="rounded-full bg-white/80 px-3 py-1 text-sm text-gray-500">
                      {{ executionResults.length ? `共 ${executionResults.length} 条` : '等待执行输出' }}
                    </span>
                  </div>
                  <p class="mt-2 text-sm leading-6 text-gray-500">
                    实时显示发送按键、TTS 文本、录音、识别和文本比对反馈。新日志会自动滚动到最新一条，不再遮挡表格内容。
                  </p>
                </div>
                <div class="flex flex-wrap items-center gap-2">
                  <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">信息 {{ executionLogStats.info }}</span>
                  <span class="rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700">成功 {{ executionLogStats.success }}</span>
                  <span class="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">异常 {{ executionLogStats.error }}</span>
                  <button class="btn btn-secondary btn-sm" @click="clearExecutionLogs" :disabled="executionResults.length === 0">
                    清空日志
                  </button>
                </div>
              </div>

              <div ref="executionLogContainer" class="mt-4 max-h-80 overflow-y-auto rounded-[22px] border border-slate-200/80 bg-slate-50/85 p-3 sm:p-4">
                <div v-if="executionResults.length === 0" class="flex min-h-32 items-center justify-center rounded-[18px] border border-dashed border-slate-200 bg-white/70 text-sm text-gray-400">
                  暂无执行日志，开始执行后会在这里实时显示。
                </div>
                <div v-else class="space-y-2">
                  <div v-for="(result, index) in executionResults" :key="index" class="flex items-start gap-3 rounded-[18px] border border-white/80 bg-white/80 px-4 py-3 shadow-[0_12px_30px_rgba(15,23,42,0.06)]">
                    <span
                      class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                      :class="{
                        'bg-blue-500': result.status === 'info',
                        'bg-green-500': result.status === 'success',
                        'bg-red-500': result.status === 'error'
                      }"
                    ></span>
                    <div class="min-w-0">
                      <div class="text-[11px] font-semibold uppercase tracking-[0.24em] text-gray-400">
                        {{ executionStatusLabel(result.status) }}
                      </div>
                      <p class="mt-1 break-all text-sm leading-6 text-slate-700">
                        {{ result.message }}
                      </p>
                      <p v-if="result.tts_text" class="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-500">TTS 文本：{{ result.tts_text }}</p>
                      <p v-if="result.transcribed_text" class="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-500">识别文本：{{ result.transcribed_text }}</p>
                      <p v-if="result.reference_text" class="mt-1 whitespace-pre-wrap text-xs leading-5 text-slate-500">参考文本：{{ result.reference_text }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <div class="mb-4 overflow-x-auto rounded-[28px] border border-white/70 bg-white/72 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
              <table class="w-full min-w-[980px] table-fixed">
                <colgroup>
                  <col style="width: 52px;">
                  <col style="width: 220px;">
                  <col>
                  <col style="width: 132px;">
                  <col style="width: 240px;">
                </colgroup>
                <thead class="bg-slate-50/90">
                  <tr>
                    <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                      <input type="checkbox" @change="toggleSelectAll" :checked="isPageAllSelected">
                    </th>
                    <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">用例标题</th>
                    <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">操作步骤</th>
                    <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">操作</th>
                    <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">ASR 结果</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in pagedRows" :key="item.idx">
                    <td class="border px-3 py-3 text-center align-top">
                      <input type="checkbox" :checked="selectedRows.includes(item.idx)" @change="toggleSelectRow(item.idx)">
                    </td>
                    <td class="border px-3 py-3 align-top">
                      <span v-if="item.row.title" class="block truncate text-primary" :title="item.row.title">{{ item.row.title }}</span>
                      <span v-else>-</span>
                    </td>
                    <td class="border px-3 py-3 align-top">
                      <div v-if="getRowStepSegments(item.row).length" class="space-y-2">
                        <div
                          v-for="(segment, segmentIndex) in getRowStepSegments(item.row)"
                          :key="segmentIndex"
                          class="truncate rounded-2xl bg-slate-50/92 px-3 py-2 text-sm leading-5 text-slate-600 shadow-[inset_0_1px_0_rgba(255,255,255,0.92)]"
                          :title="segment"
                        >
                          {{ segment }}
                        </div>
                      </div>
                      <span v-else>-</span>
                    </td>
                    <td class="border px-3 py-3 text-center align-top">
                      <div class="flex flex-col items-center gap-2">
                        <button
                          class="btn btn-secondary min-w-[88px] whitespace-nowrap"
                          @click="openCaseEditModal(item)"
                          :disabled="savingCaseFields || executingRows[item.idx]"
                        >
                          编辑
                        </button>
                        <button
                          v-if="!executingRows[item.idx]"
                          class="btn btn-primary min-w-[88px] whitespace-nowrap"
                          @click="executeAsrRowByIndex(item.idx)"
                          :disabled="!canExecuteAsr || isBatchExecuting || hasActiveExecution"
                        >
                          执行
                        </button>
                        <button
                          v-else
                          class="btn btn-danger min-w-[88px] whitespace-nowrap"
                          @click="stopExecution(item.idx)"
                        >
                          停止执行
                        </button>
                      </div>
                    </td>
                    <td class="border px-3 py-3 text-center align-top">
                      <div v-if="rowRunMeta[item.idx] && (rowRunMeta[item.idx].asr_result || rowRunMeta[item.idx].tts_text || rowRunMeta[item.idx].transcribed_text || rowRunMeta[item.idx].reference_text || Number.isFinite(rowRunMeta[item.idx].asr_score))" class="space-y-2 text-left">
                        <div class="flex flex-wrap items-center gap-2">
                          <span
                            v-if="rowRunMeta[item.idx].asr_result"
                            class="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold"
                            :class="getAsrResultBadgeClass(rowRunMeta[item.idx].asr_result)"
                          >
                            {{ rowRunMeta[item.idx].asr_result }}
                          </span>
                          <span v-if="Number.isFinite(rowRunMeta[item.idx].asr_score)" class="text-sm font-semibold text-slate-700">
                            {{ formatAsrScore(rowRunMeta[item.idx].asr_score) }}
                          </span>
                        </div>
                        <p v-if="rowRunMeta[item.idx].tts_text" class="line-clamp-3 text-xs leading-5 text-slate-500" :title="rowRunMeta[item.idx].tts_text">
                          TTS：{{ rowRunMeta[item.idx].tts_text }}
                        </p>
                        <p v-if="rowRunMeta[item.idx].transcribed_text" class="line-clamp-3 text-xs leading-5 text-slate-500" :title="rowRunMeta[item.idx].transcribed_text">
                          {{ rowRunMeta[item.idx].transcribed_text }}
                        </p>
                        <p v-else-if="rowRunMeta[item.idx].asr_result === 'NO_REF'" class="text-xs leading-5 text-amber-600">
                          缺少参考文本，仅返回识别结果。
                        </p>
                      </div>
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
              <div class="flex items-center gap-2 flex-wrap">
                <button class="btn btn-secondary" @click="handlePrevPage" :disabled="currentPage === 1">上一页</button>
                <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
                <div class="flex items-center gap-1">
                  <span>跳转到</span>
                  <input
                    v-model.number="jumpPage"
                    type="number"
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

            <div v-if="excelAnalysis.skipped_rows?.length > 0" class="bg-yellow-50 p-4 rounded-lg mb-4 mt-4">
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

      <div v-if="showCaseEditModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-lg shadow-xl p-6 w-[92vw] max-w-2xl">
          <div class="flex items-start justify-between gap-4 mb-4">
            <div>
              <h3 class="text-lg font-medium">编辑用例信息</h3>
              <p v-if="editingCaseExcelRow" class="text-sm text-gray-500 mt-1">
                第 {{ editingCaseExcelRow }} 行，修改后会直接写回当前 Excel 文件。
              </p>
            </div>
            <button @click="closeCaseEditModal" class="text-gray-500 hover:text-gray-700" :disabled="savingCaseFields">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="space-y-4">
            <div>
              <label class="form-label">用例标题</label>
              <input
                v-model="editingCaseForm.title"
                type="text"
                class="form-input w-full"
                placeholder="请输入用例标题"
              >
            </div>
            <div>
              <label class="form-label">原始步骤</label>
              <textarea
                v-model="editingCaseForm.ori_step"
                class="form-input w-full min-h-[120px] resize-y"
                placeholder="请输入 oriStep 内容，例如 HOME/1/1"
              ></textarea>
            </div>
            <div>
              <label class="form-label">前置脚本</label>
              <textarea
                v-model="editingCaseForm.pre_script"
                class="form-input w-full min-h-[120px] resize-y"
                placeholder="请输入 preScript 内容，留空则不写入"
              ></textarea>
            </div>
            <div>
              <label class="form-label">校验图片</label>
              <input
                v-model="editingCaseForm.verify_image"
                type="text"
                class="form-input w-full"
                placeholder="请输入校验图片名称或路径"
              >
            </div>
          </div>

          <div class="mt-6 flex justify-end gap-3">
            <button class="btn btn-secondary" @click="closeCaseEditModal" :disabled="savingCaseFields">
              取消
            </button>
            <button class="btn btn-primary" @click="saveCaseFields" :disabled="savingCaseFields">
              {{ savingCaseFields ? '保存中...' : '保存修改' }}
            </button>
          </div>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'

const loadingStatus = ref(false)
const statusErrorMessage = ref('')
const status = reactive({
  project_exists: false,
  project_root: '',
  voice_project_exists: false,
  voice_project_root: '',
  qwen_root: '',
  qwen_models: [],
  runtime_model_root: '',
  imported_models: [],
  active_model: null,
  case_files: [],
  reference_count: 0,
  audio_count: 0,
  result_count: 0,
  dependencies: {
    available: {},
    ready: true,
    missing: [],
    python_version: '',
    recommended_python_version: '3.12',
    install_commands: [],
    install_steps: [],
    notes: [],
    restart_required: false
  }
})

const selectedDevice = ref('')
const excelFiles = ref([])
const selectedFile = ref('')
const excelAnalysis = ref(null)
const validationResult = ref(null)
const loadingFiles = ref(false)
const loadingAnalysis = ref(false)
const deletingFile = ref(false)
const executingRows = ref({})
const stopExecutionFlags = ref({})
const selectedRows = ref([])
const searchKeyword = ref('')
const currentPage = ref(1)
const jumpPage = ref(1)
const pageSize = ref(20)
const isBatchExecuting = ref(false)
const executionResults = ref([])
const executionLogContainer = ref(null)
const analysisSection = ref(null)
const rowRunMeta = ref({})
const showCaseEditModal = ref(false)
const fileInput = ref(null)
const modelFolderInput = ref(null)
const importingModel = ref(false)
const selectingModel = ref(false)
const deletingModel = ref(false)
const savingCaseFields = ref(false)
const modelImportMessage = ref('')
const modelImportProgress = reactive({
  completed: 0,
  total: 0,
  modelName: ''
})
const editingCaseIndex = ref(null)
const editingCaseExcelRow = ref(null)
const editingCaseForm = reactive({
  title: '',
  ori_step: '',
  pre_script: '',
  verify_image: ''
})

const activeModelName = computed(() => status.active_model?.name || '')
const asrDependencyStatus = computed(() => status.dependencies || {})
const missingAsrDependencies = computed(() => Array.isArray(asrDependencyStatus.value.missing) ? asrDependencyStatus.value.missing : [])
const canExecuteAsr = computed(() => Boolean(activeModelName.value && selectedDevice.value && missingAsrDependencies.value.length === 0))
const asrDependencyBlockMessage = computed(() => {
  if (missingAsrDependencies.value.length === 0) {
    return ''
  }

  const commands = Array.isArray(asrDependencyStatus.value.install_commands)
    ? asrDependencyStatus.value.install_commands
    : []
  const commandText = commands.length ? `\n\n建议执行：\n${commands.join('\n')}` : ''
  return `当前后端缺少 ASR 运行依赖：${missingAsrDependencies.value.join('、')}。请先按页面顶部提示安装依赖，重启后端后点击“刷新状态”。${commandText}`
})

const filteredRows = computed(() => {
  if (!excelAnalysis.value?.valid_rows) {
    return []
  }

  let items = excelAnalysis.value.valid_rows.map((row, index) => ({ row, idx: index + 1 }))
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    items = items.filter(({ row }) => {
      if (row.title && String(row.title).toLowerCase().includes(keyword)) {
        return true
      }

      return getRowStepSegments(row).some((segment) => segment.toLowerCase().includes(keyword))
    })
  }

  return items
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value)))

const allRowIndexes = computed(() => {
  if (!excelAnalysis.value?.valid_rows) {
    return []
  }

  return excelAnalysis.value.valid_rows.map((_, index) => index + 1)
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

const hasActiveExecution = computed(() => Object.values(executingRows.value).some(Boolean))

const isPageAllSelected = computed(() => {
  if (pagedRows.value.length === 0) {
    return false
  }

  const ids = pagedRows.value.map((item) => item.idx)
  return ids.every((id) => selectedRows.value.includes(id))
})

const executionLogStats = computed(() => {
  return executionResults.value.reduce((stats, result) => {
    const statusKey = result?.status || 'info'
    if (statusKey === 'success') {
      stats.success += 1
    } else if (statusKey === 'error') {
      stats.error += 1
    } else {
      stats.info += 1
    }
    return stats
  }, { info: 0, success: 0, error: 0 })
})

const readErrorMessage = async (response, fallbackMessage) => {
  try {
    const data = await response.json()
    return data.detail || data.message || fallbackMessage
  } catch {
    return fallbackMessage
  }
}

const inferFolderName = (files) => {
  const firstFile = files[0]
  if (!firstFile) {
    return ''
  }

  const relativePath = firstFile.webkitRelativePath || ''
  if (!relativePath.includes('/')) {
    return firstFile.name.replace(/\.[^.]+$/, '')
  }

  return relativePath.split('/')[0]
}

const getRelativeModelPath = (file, modelName) => {
  const relativePath = file.webkitRelativePath || file.name
  const prefix = `${modelName}/`
  if (relativePath.startsWith(prefix)) {
    return relativePath.slice(prefix.length)
  }
  const segments = relativePath.split('/')
  return segments.length > 1 ? segments.slice(1).join('/') : file.name
}

const hasMeaningfulValue = (value) => {
  if (value === null || value === undefined) {
    return false
  }

  const normalized = String(value).trim()
  return normalized !== '' && normalized.toLowerCase() !== 'nan'
}

const getRowStepSegments = (row) => {
  const segments = []
  const seen = new Set()
  const addSegment = (value) => {
    if (!hasMeaningfulValue(value)) {
      return
    }

    const normalized = String(value).trim()
    if (!normalized || seen.has(normalized)) {
      return
    }

    seen.add(normalized)
    segments.push(normalized)
  }

  const hasSplitStepFields = hasMeaningfulValue(row?.oriStep) || hasMeaningfulValue(row?.preScript)
  if (hasSplitStepFields) {
    addSegment(row?.oriStep)
    addSegment(row?.preScript)
    return segments
  }

  addSegment(row?.step)

  if (Array.isArray(row?.commands)) {
    row.commands.forEach((command) => addSegment(command))
  } else if (Array.isArray(row?.command)) {
    row.command.forEach((command) => addSegment(command))
  } else {
    addSegment(row?.command)
  }

  return segments
}

const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    selectedDevice.value = data.device || ''
  } catch (error) {
    console.error('获取当前设备失败:', error)
  }
}

const loadStatus = async () => {
  loadingStatus.value = true
  statusErrorMessage.value = ''

  try {
    const response = await fetch('/api/excel/asr/status')
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, `请求失败: ${response.status}`))
    }

    const data = await response.json()
    Object.assign(status, data)
  } catch (error) {
    console.error('加载 ASR 状态失败:', error)
    statusErrorMessage.value = error instanceof Error ? error.message : '加载 ASR 状态失败'
  } finally {
    loadingStatus.value = false
  }
}

const triggerModelFolderPicker = () => {
  modelFolderInput.value?.click()
}

const handleModelFolderChange = async (event) => {
  const files = Array.from(event.target.files || [])
  if (modelFolderInput.value) {
    modelFolderInput.value.value = ''
  }

  if (files.length === 0) {
    return
  }

  const modelName = inferFolderName(files)
  if (!modelName) {
    alert('无法识别模型目录名称')
    return
  }

  importingModel.value = true
  modelImportMessage.value = ''
  modelImportProgress.completed = 0
  modelImportProgress.total = files.length
  modelImportProgress.modelName = modelName

  try {
    for (const file of files) {
      const formData = new FormData()
      formData.append('model_name', modelName)
      formData.append('relative_path', getRelativeModelPath(file, modelName))
      formData.append('file', file)

      const response = await fetch('/api/excel/asr/models/import', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(await readErrorMessage(response, `导入模型文件失败: ${file.name}`))
      }

      modelImportProgress.completed += 1
      modelImportMessage.value = `正在导入模型 ${modelName}：${modelImportProgress.completed}/${modelImportProgress.total}`
    }

    await loadStatus()
    modelImportMessage.value = `模型 ${modelName} 导入完成，当前可在列表中切换。`
  } catch (error) {
    console.error('导入模型失败:', error)
    modelImportMessage.value = error instanceof Error ? error.message : '导入模型失败'
  } finally {
    importingModel.value = false
  }
}

const selectModel = async (modelName) => {
  selectingModel.value = true
  try {
    const response = await fetch('/api/excel/asr/models/select', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ model_name: modelName })
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, '切换模型失败'))
    }

    await loadStatus()
  } catch (error) {
    console.error('切换模型失败:', error)
    alert(error instanceof Error ? error.message : '切换模型失败')
  } finally {
    selectingModel.value = false
  }
}

const deleteModel = async (modelName) => {
  if (!confirm(`确定要删除模型 ${modelName} 吗？`)) {
    return
  }

  deletingModel.value = true
  try {
    const response = await fetch(`/api/excel/asr/models?model_name=${encodeURIComponent(modelName)}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, '删除模型失败'))
    }

    const data = await response.json()
    await loadStatus()

    if (data.active_model) {
      modelImportMessage.value = `模型 ${data.deleted_model} 已删除，当前模型已切换为 ${data.active_model}。`
    } else {
      modelImportMessage.value = `模型 ${data.deleted_model} 已删除。`
    }
  } catch (error) {
    console.error('删除模型失败:', error)
    alert(error instanceof Error ? error.message : '删除模型失败')
  } finally {
    deletingModel.value = false
  }
}

const loadExcelFiles = async () => {
  loadingFiles.value = true
  try {
    const response = await fetch('/api/excel/files')
    const data = await response.json()
    excelFiles.value = data.files || []
  } catch (error) {
    console.error('获取 Excel 文件列表失败:', error)
  } finally {
    loadingFiles.value = false
  }
}

const selectFile = (file) => {
  selectedFile.value = file
  excelAnalysis.value = null
  validationResult.value = null
  selectedRows.value = []
  currentPage.value = 1
  jumpPage.value = 1
  executionResults.value = []
  rowRunMeta.value = {}
}

const openCaseEditModal = (item) => {
  editingCaseIndex.value = item.idx
  editingCaseExcelRow.value = item.row.row
  editingCaseForm.title = item.row.title || ''
  editingCaseForm.ori_step = item.row.oriStep || item.row.step || ''
  editingCaseForm.pre_script = item.row.preScript || ''
  editingCaseForm.verify_image = item.row.verify_image || ''
  showCaseEditModal.value = true
}

const closeCaseEditModal = () => {
  showCaseEditModal.value = false
  editingCaseIndex.value = null
  editingCaseExcelRow.value = null
  editingCaseForm.title = ''
  editingCaseForm.ori_step = ''
  editingCaseForm.pre_script = ''
  editingCaseForm.verify_image = ''
}

const saveCaseFields = async () => {
  if (!selectedFile.value || !editingCaseIndex.value || !editingCaseExcelRow.value) {
    return
  }

  savingCaseFields.value = true
  try {
    const response = await fetch('/api/excel/update_case_fields', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        file_name: selectedFile.value,
        excel_row: editingCaseExcelRow.value,
        title: editingCaseForm.title,
        ori_step: editingCaseForm.ori_step,
        pre_script: editingCaseForm.pre_script,
        step: editingCaseForm.ori_step,
        verify_image: editingCaseForm.verify_image
      })
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, '更新用例字段失败'))
    }

    const rowData = excelAnalysis.value?.valid_rows?.[editingCaseIndex.value - 1]
    if (rowData) {
      rowData.title = editingCaseForm.title
      if (hasMeaningfulValue(rowData.oriStep) || hasMeaningfulValue(rowData.preScript) || Array.isArray(rowData.commands)) {
        rowData.oriStep = editingCaseForm.ori_step
        rowData.preScript = editingCaseForm.pre_script
      } else {
        rowData.step = editingCaseForm.ori_step
      }
      rowData.verify_image = editingCaseForm.verify_image
    }

    closeCaseEditModal()
  } catch (error) {
    console.error('更新用例字段失败:', error)
    alert('更新用例字段失败: ' + error.message)
  } finally {
    savingCaseFields.value = false
  }
}

const analyzeFile = async () => {
  if (!selectedFile.value) {
    alert('请先选择一个 Excel 文件')
    return
  }

  loadingAnalysis.value = true
  try {
    const validateResponse = await fetch(`/api/excel/validate?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!validateResponse.ok) {
      throw new Error(await readErrorMessage(validateResponse, '验证文件失败'))
    }

    validationResult.value = await validateResponse.json()

    const response = await fetch(`/api/excel/analyze?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, '分析文件失败'))
    }

    excelAnalysis.value = await response.json()
    selectedRows.value = []
    searchKeyword.value = ''
    currentPage.value = 1
    jumpPage.value = 1
    rowRunMeta.value = {}

    await nextTick()
    analysisSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (error) {
    console.error('分析文件失败:', error)
    alert(error instanceof Error ? error.message : '分析文件失败')
  } finally {
    loadingAnalysis.value = false
  }
}

const triggerExcelUpload = () => {
  fileInput.value?.click()
}

const uploadFile = async (event) => {
  const file = event.target.files?.[0]
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
      throw new Error(await readErrorMessage(response, '上传文件失败'))
    }

    const data = await response.json()
    await loadExcelFiles()
    selectFile(data.filename)
  } catch (error) {
    console.error('上传文件失败:', error)
    alert(error instanceof Error ? error.message : '上传文件失败')
  } finally {
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

const deleteFile = async (file) => {
  if (!confirm(`确定要删除文件 ${file} 吗？`)) {
    return
  }

  deletingFile.value = true
  try {
    const response = await fetch(`/api/excel/delete?file_name=${encodeURIComponent(file)}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, '删除文件失败'))
    }

    await loadExcelFiles()
    if (selectedFile.value === file) {
      selectedFile.value = ''
      excelAnalysis.value = null
      validationResult.value = null
      executionResults.value = []
      rowRunMeta.value = {}
    }
  } catch (error) {
    console.error('删除文件失败:', error)
    alert(error instanceof Error ? error.message : '删除文件失败')
  } finally {
    deletingFile.value = false
  }
}

const executeAsrRowByIndex = (index) => {
  return new Promise((resolve) => {
    if (!selectedFile.value) {
      alert('请先选择一个 Excel 文件')
      resolve()
      return
    }

    if (!activeModelName.value) {
      alert('请先导入并选择一个 ASR 模型')
      resolve()
      return
    }

    if (!selectedDevice.value) {
      alert('请先选择设备')
      resolve()
      return
    }

    if (missingAsrDependencies.value.length > 0) {
      alert(asrDependencyBlockMessage.value)
      resolve()
      return
    }

    executingRows.value[index] = true
    stopExecutionFlags.value[index] = false
    rowRunMeta.value[index] = {}
    if (!isBatchExecuting.value) {
      executionResults.value = []
    }

    fetch('/api/excel/asr/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        file_name: selectedFile.value,
        row_index: index
      })
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await readErrorMessage(response, '执行 ASR 用例失败'))
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        const readChunk = () => {
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
              executingRows.value[index] = false
              resolve()
              return
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            lines.forEach((line) => {
              if (!line.startsWith('data:')) {
                return
              }

              const rawData = line.substring(5).trim()
              if (!rawData) {
                return
              }

              try {
                const result = JSON.parse(rawData)
                executionResults.value.push(result)
                if (
                  Object.prototype.hasOwnProperty.call(result, 'asr_result') ||
                  Object.prototype.hasOwnProperty.call(result, 'asr_score') ||
                  Object.prototype.hasOwnProperty.call(result, 'tts_text') ||
                  Object.prototype.hasOwnProperty.call(result, 'transcribed_text') ||
                  Object.prototype.hasOwnProperty.call(result, 'reference_text')
                ) {
                  const previousMeta = rowRunMeta.value[index] || {}
                  rowRunMeta.value[index] = {
                    ...previousMeta,
                    asr_result: Object.prototype.hasOwnProperty.call(result, 'asr_result') ? (result.asr_result || '') : (previousMeta.asr_result || ''),
                    asr_score: Object.prototype.hasOwnProperty.call(result, 'asr_score') ? result.asr_score : previousMeta.asr_score,
                    tts_text: Object.prototype.hasOwnProperty.call(result, 'tts_text') ? (result.tts_text || '') : (previousMeta.tts_text || ''),
                    transcribed_text: Object.prototype.hasOwnProperty.call(result, 'transcribed_text') ? (result.transcribed_text || '') : (previousMeta.transcribed_text || ''),
                    reference_text: Object.prototype.hasOwnProperty.call(result, 'reference_text') ? (result.reference_text || '') : (previousMeta.reference_text || '')
                  }
                }
              } catch (error) {
                console.error('解析执行流失败:', error)
              }
            })

            readChunk()
          }).catch((error) => {
            console.error('读取执行流失败:', error)
            executionResults.value.push({
              status: 'error',
              message: '执行失败：' + error.message
            })
            executingRows.value[index] = false
            resolve()
          })
        }

        readChunk()
      })
      .catch((error) => {
        console.error('执行 ASR 用例失败:', error)
        executionResults.value.push({
          status: 'error',
          message: error instanceof Error ? error.message : '执行 ASR 用例失败'
        })
        executingRows.value[index] = false
        resolve()
      })
  })
}

const stopExecution = (index) => {
  stopExecutionFlags.value[index] = true
}

const toggleSelectRow = (rowIndex) => {
  const index = selectedRows.value.indexOf(rowIndex)
  if (index > -1) {
    selectedRows.value.splice(index, 1)
  } else {
    selectedRows.value.push(rowIndex)
  }
  selectedRows.value = Array.from(new Set(selectedRows.value)).sort((a, b) => a - b)
}

const toggleSelectAll = () => {
  const pageIds = pagedRows.value.map((item) => item.idx)
  const allSelected = pageIds.every((id) => selectedRows.value.includes(id))
  if (allSelected) {
    selectedRows.value = selectedRows.value.filter((id) => !pageIds.includes(id))
  } else {
    selectedRows.value = Array.from(new Set([...selectedRows.value, ...pageIds])).sort((a, b) => a - b)
  }
}

const executeSelectedRows = async () => {
  await executeBatchRows(selectedRows.value, '已选用例')
}

const executeAllRows = async () => {
  await executeBatchRows(allRowIndexes.value, '当前 Excel 全部用例')
}

const executeBatchRows = async (rowIndexes, label) => {
  const orderedRows = Array.from(new Set(rowIndexes)).sort((a, b) => a - b)
  if (orderedRows.length === 0) {
    return
  }

  isBatchExecuting.value = true
  executionResults.value.push({
    status: 'info',
    message: `开始批量执行${label}，共 ${orderedRows.length} 条`
  })

  let completedAll = false
  try {
    for (const [offset, rowIndex] of orderedRows.entries()) {
      if (!isBatchExecuting.value) {
        break
      }

      await executeAsrRowByIndex(rowIndex)
      if (!isBatchExecuting.value) {
        break
      }

      if (offset < orderedRows.length - 1) {
        await new Promise((resolve) => setTimeout(resolve, 1000))
      }
    }
    completedAll = isBatchExecuting.value
  } finally {
    isBatchExecuting.value = false
    if (completedAll) {
      executionResults.value.push({
        status: 'success',
        message: `批量执行${label}完成，共执行 ${orderedRows.length} 条`
      })
    }
  }
}

const stopAllExecution = () => {
  isBatchExecuting.value = false
  for (const rowIndex in executingRows.value) {
    if (executingRows.value[rowIndex]) {
      stopExecutionFlags.value[rowIndex] = true
    }
  }
  executionResults.value.push({
    status: 'info',
    message: '所有执行已停止'
  })
}

const executionStatusLabel = (statusKey) => {
  if (statusKey === 'success') {
    return 'SUCCESS'
  }
  if (statusKey === 'error') {
    return 'ERROR'
  }
  return 'INFO'
}

const formatAsrScore = (score) => {
  if (!Number.isFinite(score)) {
    return ''
  }
  return `${(score * 100).toFixed(2)}%`
}

const getAsrResultBadgeClass = (result) => {
  if (result === 'PASS') {
    return 'bg-emerald-100 text-emerald-700'
  }
  if (result === 'FAIL') {
    return 'bg-rose-100 text-rose-700'
  }
  if (result === 'NO_REF') {
    return 'bg-amber-100 text-amber-700'
  }
  return 'bg-slate-100 text-slate-600'
}

const clearExecutionLogs = () => {
  executionResults.value = []
}

const handlePrevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value -= 1
    selectedRows.value = []
  }
}

const handleNextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value += 1
    selectedRows.value = []
  }
}

const handleJumpPage = () => {
  const page = parseInt(jumpPage.value, 10)
  if (page && page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    selectedRows.value = []
  }
}

watch(() => executionResults.value.length, async (newLength, oldLength = 0) => {
  if (newLength === 0 || newLength <= oldLength) {
    return
  }

  await nextTick()
  if (executionLogContainer.value) {
    executionLogContainer.value.scrollTop = executionLogContainer.value.scrollHeight
  }
})

watch(currentPage, (newPage) => {
  jumpPage.value = newPage
})

watch(totalPages, (nextTotalPages) => {
  if (currentPage.value > nextTotalPages) {
    currentPage.value = nextTotalPages
  }
})

onMounted(async () => {
  await loadCurrentDevice()
  await Promise.all([loadStatus(), loadExcelFiles()])
})
</script>

<style scoped>
.excel-execution-page {
  flex: 1;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 24px 28px;
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.excel-execution-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.9) rgba(226, 232, 240, 0.72);
}

.excel-execution-scroll::-webkit-scrollbar {
  width: 10px;
}

.excel-execution-scroll::-webkit-scrollbar-track {
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.72);
}

.excel-execution-scroll::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.9);
  background-clip: padding-box;
}
</style>