<template>
            <div class="card w-full max-w-7xl mx-auto excel-execution-page">
              <div class="mb-4 flex flex-wrap items-center gap-3">
                <router-link to="/excel" class="btn btn-secondary btn-sm">
                  返回功能选择
                </router-link>
                <h2 class="mb-0">图片校验执行</h2>
              </div>

              <div class="excel-execution-scroll">
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
                        <div class="flex items-center justify-between gap-4">
                          <div class="flex-1 min-w-0">
                            <p class="font-medium">文件 {{ index + 1 }}</p>
                            <p class="text-gray-600 truncate">{{ file }}</p>
                          </div>
                          <div class="flex items-center gap-2">
                            <button
                              @click.stop="deleteFile(file)"
                              class="btn btn-danger"
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

                <div v-if="selectedFile" class="mb-6">
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
                              实时显示发送按键、截图和图片校验反馈。新日志会自动滚动到最新一条，不再遮挡表格内容。
                            </p>
                          </div>
                          <div class="flex flex-wrap items-center gap-2">
                            <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">信息 {{ executionLogStats.info }}</span>
                            <span class="rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700">成功 {{ executionLogStats.success }}</span>
                            <span class="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">异常 {{ executionLogStats.error }}</span>
                            <button
                              class="btn btn-secondary btn-sm"
                              @click="clearExecutionLogs"
                              :disabled="executionResults.length === 0"
                            >
                              清空日志
                            </button>
                          </div>
                        </div>

                        <div
                          ref="executionLogContainer"
                          class="mt-4 max-h-80 overflow-y-auto rounded-[22px] border border-slate-200/80 bg-slate-50/85 p-3 sm:p-4"
                        >
                          <div
                            v-if="executionResults.length === 0"
                            class="flex min-h-32 items-center justify-center rounded-[18px] border border-dashed border-slate-200 bg-white/70 text-sm text-gray-400"
                          >
                            暂无执行日志，开始执行后会在这里实时显示。
                          </div>
                          <div v-else class="space-y-2">
                            <div
                              v-for="(result, index) in executionResults"
                              :key="index"
                              class="flex items-start gap-3 rounded-[18px] border border-white/80 bg-white/80 px-4 py-3 shadow-[0_12px_30px_rgba(15,23,42,0.06)]"
                            >
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
                              </div>
                            </div>
                          </div>
                        </div>
                      </section>

                      <div class="mb-4 overflow-x-auto rounded-[28px] border border-white/70 bg-white/72 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
                        <table class="excel-results-table w-full min-w-[1160px] table-fixed">
                          <colgroup>
                            <col style="width: 48px;">
                            <col style="width: 86px;">
                            <col style="width: 170px;">
                            <col>
                            <col style="width: 170px;">
                            <col style="width: 128px;">
                            <col style="width: 128px;">
                          </colgroup>
                          <thead class="bg-slate-50/90">
                            <tr>
                              <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                                <input
                                  type="checkbox"
                                  @change="toggleSelectAll"
                                  :checked="isPageAllSelected"
                                >
                              </th>
                              <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">结果</th>
                              <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">用例标题</th>
                              <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">操作步骤</th>
                              <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">校验图片</th>
                              <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">操作</th>
                              <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">执行结果</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="item in pagedRows" :key="item.idx">
                              <td class="border px-3 py-3 text-center align-top">
                                <input
                                  type="checkbox"
                                  :checked="selectedRows.includes(item.idx)"
                                  @change="toggleSelectRow(item.idx)"
                                >
                              </td>
                              <td class="border px-3 py-3 align-top">
                                <span v-if="item.row.result" :class="item.row.result.toUpperCase() === 'PASS' ? 'text-success' : 'text-danger'">
                                  {{ item.row.result }}
                                </span>
                                <span v-else-if="item.row.test_result" :class="item.row.test_result.toUpperCase() === 'PASS' ? 'text-success' : 'text-danger'">
                                  {{ item.row.test_result }}
                                </span>
                                <span v-else>-</span>
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
                              <td class="border px-3 py-3 align-top">
                                <span
                                  v-if="item.row.verify_image && item.row.verify_image !== 'nan'"
                                  class="block cursor-pointer truncate text-primary hover:underline"
                                  :title="item.row.verify_image"
                                  @click="previewVerifyImage(item.row.verify_image)"
                                >
                                  {{ item.row.verify_image }}
                                </span>
                                <span v-else>-</span>
                              </td>
                              <td class="border px-3 py-3 text-center align-top">
                                <div class="flex flex-col items-center gap-2">
                                  <button
                                    @click="openCaseEditModal(item)"
                                    class="btn btn-secondary min-w-[88px] whitespace-nowrap"
                                    :disabled="savingCaseFields || executingRows[item.idx]"
                                  >
                                    编辑
                                  </button>
                                  <button
                                    v-if="!executingRows[item.idx]"
                                    @click="executeExcelRowByIndex(item.idx)"
                                    class="btn btn-primary min-w-[88px] whitespace-nowrap"
                                  >
                                    执行
                                  </button>
                                  <button
                                    v-else
                                    @click="stopExecution(item.idx)"
                                    class="btn btn-danger min-w-[88px] whitespace-nowrap"
                                  >
                                    停止执行
                                  </button>
                                </div>
                              </td>
                              <td class="border px-3 py-3 text-center align-top">
                                <button
                                  v-if="rowScreenshots[item.idx]"
                                  @click="showExecutionResult(item.idx)"
                                  class="btn btn-sm btn-info min-w-[96px] whitespace-nowrap"
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
                        <div class="flex items-center gap-2 flex-wrap">
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

                      <div v-if="excelAnalysis.skipped_rows.length > 0" class="bg-yellow-50 p-4 rounded-lg mb-4 mt-4">
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
              </div>

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
                    <span
                      v-if="modalResultStatus"
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
                        <span v-else class="text-gray-400">{{ modalVerifyImagePlaceholder || '该用例未配置校验图' }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

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
          </template>

<script setup>
import { ref, onMounted, computed, watch, onUnmounted, nextTick, reactive } from 'vue'
import { useRouter, useRoute, onBeforeRouteLeave } from 'vue-router'

const selectedDevice = ref('')
const excelFiles = ref([])
const selectedFile = ref('')
const excelAnalysis = ref(null)
const validationResult = ref(null)
const executionResults = ref([])
const executionLogContainer = ref(null)
const rowIndex = ref(1)
const loadingFiles = ref(false)
const loadingAnalysis = ref(false)
const executingRows = ref({})
const stopExecutionFlags = ref({})
const executionAbortControllers = ref({})
const selectedRows = ref([])
const filterResult = ref('')
const searchKeyword = ref('')
const rowScreenshots = ref({})
const rowResultMeta = ref({})
const showScreenshotModal = ref(false)
const modalScreenshotUrl = ref('')
const modalVerifyImageUrl = ref('')
const modalVerifyImageName = ref('')
const modalVerifyImagePlaceholder = ref('')
const modalResultTitle = ref('')
const modalResultStatus = ref('')
const modalResultScore = ref(null)
const showVerifyImageModal = ref(false)
const showCaseEditModal = ref(false)
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
const savingCaseFields = ref(false)
const MAX_PERSISTED_EXECUTION_RESULTS = 200
const EXCEL_EXECUTION_STORAGE_KEY = 'checkpilot.excelExecution.state'
const editingCaseIndex = ref(null)
const editingCaseExcelRow = ref(null)
const editingCaseForm = reactive({
  title: '',
  ori_step: '',
  pre_script: '',
  verify_image: ''
})
let isRestoringExecutionState = false

// 路由实例
const router = useRouter()
const route = useRoute()

const readPersistedExecutionState = () => {
  try {
    const raw = localStorage.getItem(EXCEL_EXECUTION_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (error) {
    console.error('读取页面状态失败:', error)
    return null
  }
}

const persistExecutionState = () => {
  if (isRestoringExecutionState) {
    return
  }

  try {
    localStorage.setItem(EXCEL_EXECUTION_STORAGE_KEY, JSON.stringify({
      selectedDevice: selectedDevice.value || '',
      selectedFile: selectedFile.value || '',
      rowIndex: rowIndex.value,
      filterResult: filterResult.value,
      searchKeyword: searchKeyword.value,
      currentPage: currentPage.value,
      jumpPage: jumpPage.value,
      pageSize: pageSize.value,
      selectedRows: Array.isArray(selectedRows.value) ? selectedRows.value : [],
      executionResults: executionResults.value.slice(-MAX_PERSISTED_EXECUTION_RESULTS),
      rowScreenshots: rowScreenshots.value,
      rowResultMeta: rowResultMeta.value,
      verifyImageFolderName: verifyImageFolderName.value || '',
      hadLocalVerifyImages: verifyImageFileCount.value > 0,
    }))
  } catch (error) {
    console.error('保存页面状态失败:', error)
  }
}

const applyRowResultMetaToAnalysis = () => {
  if (!excelAnalysis.value?.valid_rows) {
    return
  }

  Object.entries(rowResultMeta.value || {}).forEach(([rowIndexKey, meta]) => {
    const numericIndex = Number(rowIndexKey)
    const rowData = excelAnalysis.value?.valid_rows?.[numericIndex - 1]
    if (rowData && meta?.verify_result) {
      rowData.result = meta.verify_result
    }
  })
}

const restoreSavedDevice = async (savedDevice) => {
  if (!savedDevice) {
    return ''
  }

  try {
    const listResponse = await fetch('/api/devices/list')
    if (!listResponse.ok) {
      return ''
    }

    const listData = await listResponse.json()
    const devices = Array.isArray(listData.devices) ? listData.devices : []
    const deviceIndex = devices.indexOf(savedDevice)
    if (deviceIndex < 0) {
      return ''
    }

    const selectResponse = await fetch('/api/devices/select', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ device_index: deviceIndex })
    })

    if (!selectResponse.ok) {
      return ''
    }

    const selectData = await selectResponse.json()
    return selectData.status === 'success' ? selectData.device || savedDevice : ''
  } catch (error) {
    console.error('恢复设备选择失败:', error)
    return ''
  }
}

const restoreExecutionState = async () => {
  const savedState = readPersistedExecutionState()
  if (!savedState) {
    return
  }

  isRestoringExecutionState = true
  try {
    if (!selectedDevice.value && savedState.selectedDevice) {
      const restoredDevice = await restoreSavedDevice(savedState.selectedDevice)
      if (restoredDevice) {
        selectedDevice.value = restoredDevice
      }
    }

    if (savedState.selectedFile && excelFiles.value.includes(savedState.selectedFile)) {
      selectedFile.value = savedState.selectedFile
      await analyzeFile({ silent: true, resetView: false })
    }

    rowIndex.value = Number(savedState.rowIndex) || 1
    filterResult.value = savedState.filterResult || ''
    searchKeyword.value = savedState.searchKeyword || ''
    currentPage.value = Number(savedState.currentPage) || 1
    jumpPage.value = Number(savedState.jumpPage) || currentPage.value
    pageSize.value = Number(savedState.pageSize) || 20
    selectedRows.value = Array.isArray(savedState.selectedRows) ? savedState.selectedRows : []
    executionResults.value = Array.isArray(savedState.executionResults) ? savedState.executionResults : []
    rowScreenshots.value = savedState.rowScreenshots && typeof savedState.rowScreenshots === 'object' ? savedState.rowScreenshots : {}
    rowResultMeta.value = savedState.rowResultMeta && typeof savedState.rowResultMeta === 'object' ? savedState.rowResultMeta : {}
    applyRowResultMetaToAnalysis()

    if (savedState.hadLocalVerifyImages && savedState.verifyImageFolderName) {
      executionResults.value.push({
        status: 'info',
        message: `刷新后需重新选择本地校验图片文件夹：${savedState.verifyImageFolderName}`
      })
    }
  } finally {
    isRestoringExecutionState = false
    persistExecutionState()
  }
}

const clearExecutionAbortController = (index) => {
  if (!executionAbortControllers.value[index]) {
    return
  }

  delete executionAbortControllers.value[index]
  executionAbortControllers.value = { ...executionAbortControllers.value }
}

const abortExecution = (index) => {
  const controller = executionAbortControllers.value[index]
  if (controller && !controller.signal.aborted) {
    controller.abort()
  }
}

const isAbortError = (error) => {
  if (!error) {
    return false
  }

  const message = String(error.message || error || '').toLowerCase()
  return error.name === 'AbortError' || message.includes('abort') || message.includes('aborted')
}

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
  Object.keys(executionAbortControllers.value).forEach((key) => {
    abortExecution(key)
  })
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

const executionLogStats = computed(() => {
  return executionResults.value.reduce((stats, result) => {
    const status = result?.status || 'info'
    if (status === 'success') {
      stats.success += 1
    } else if (status === 'error') {
      stats.error += 1
    } else {
      stats.info += 1
    }
    return stats
  }, { info: 0, success: 0, error: 0 })
})

// 加载当前设备
onMounted(async () => {
  await loadCurrentDevice()
  await loadExcelFiles()
  await restoreExecutionState()
})

// 加载当前设备
const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    selectedDevice.value = data.device || ''

    if (!selectedDevice.value) {
      const savedState = readPersistedExecutionState()
      if (savedState?.selectedDevice) {
        const restoredDevice = await restoreSavedDevice(savedState.selectedDevice)
        if (restoredDevice) {
          selectedDevice.value = restoredDevice
        }
      }
    }
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

const readErrorMessage = async (response, fallbackMessage) => {
  try {
    const data = await response.json()
    return data.detail || data.message || fallbackMessage
  } catch {
    return fallbackMessage
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
  selectedRows.value = []
  currentPage.value = 1
  jumpPage.value = 1
  rowIndex.value = 1
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

const normalizeVerifyImageName = (imageName) => {
  return String(imageName || '')
    .split(/[/\\]/)
    .pop()
    ?.trim()
    .toLowerCase() || ''
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

const resolveResultModalVerifyImagePlaceholder = (verifyImageName, matchedEntry) => {
  if (matchedEntry?.url) {
    return ''
  }

  if (!verifyImageName) {
    return '该用例未配置校验图'
  }

  if (!verifyImageFileCount.value || !verifyImageFolderName.value) {
    return '未选择校验文件夹'
  }

  return '所选文件夹中未找到同名校验图片'
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
  modalVerifyImagePlaceholder.value = resolveResultModalVerifyImagePlaceholder(verifyImageName, matchedEntry)
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
const analyzeFile = async (options = {}) => {
  const { silent = false, resetView = true } = options
  if (!selectedFile.value) {
    if (!silent) {
      alert('请先选择一个Excel文件')
    }
    return
  }
  
  loadingAnalysis.value = true
  try {
    const validateResponse = await fetch(`/api/excel/validate?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!validateResponse.ok) {
      throw new Error('验证文件失败')
    }

    const validateData = await validateResponse.json()
    validationResult.value = validateData

    if (!validateData.success && !silent) {
      alert('文件验证发现问题，请查看下方的验证结果')
    }
    
    const response = await fetch(`/api/excel/analyze?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!response.ok) {
      throw new Error('分析文件失败')
    }

    const data = await response.json()
    excelAnalysis.value = data
    if (resetView) {
      filterResult.value = ''
      searchKeyword.value = ''
      currentPage.value = 1
      jumpPage.value = 1
      selectedRows.value = []
    }
    applyRowResultMetaToAnalysis()
  } catch (error) {
    console.error('分析文件失败:', error)
    if (!silent) {
      alert('分析文件失败: ' + error.message)
    }
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

    executingRows.value[index] = true
    stopExecutionFlags.value[index] = false
    const abortController = new AbortController()
    executionAbortControllers.value[index] = abortController
    if (!isBatchExecuting.value) {
      executionResults.value = []
    }

    let stopReported = false
    const reportStopped = () => {
      if (stopReported) {
        return
      }

      stopReported = true
      executionResults.value.push({
        status: 'info',
        message: '执行已停止'
      })
    }

    const finishExecution = () => {
      executingRows.value[index] = false
      clearExecutionAbortController(index)
      resolve()
    }

    buildExecutionPayload(index)
      .then((payload) => fetch('/api/excel/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: abortController.signal,
        body: JSON.stringify(payload)
      }))
      .then(response => {
        if (!response.ok) {
          throw new Error('执行命令失败')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        const readChunk = () => {
          if (abortController.signal.aborted || stopExecutionFlags.value[index]) {
            reportStopped()
            finishExecution()
            return
          }

          reader.read().then(({ done, value }) => {
            if (done) {
              finishExecution()
              return
            }

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop()

            lines.forEach(line => {
              if (line.startsWith('data:')) {
                const data = line.substring(5).trim()
                if (data) {
                  try {
                    const result = JSON.parse(data)
                    executionResults.value.push(result)
                    if (result.screenshot_url) {
                      rowScreenshots.value[index] = result.screenshot_url
                    }
                    if (result.verify_result) {
                      rowResultMeta.value[index] = {
                        verify_result: result.verify_result,
                        score: result.score ?? null
                      }
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

            readChunk()
          })
            .catch(error => {
              if (abortController.signal.aborted || stopExecutionFlags.value[index] || isAbortError(error)) {
                reportStopped()
                finishExecution()
                return
              }

              console.error('读取流失败:', error)
              executionResults.value.push({
                status: 'error',
                message: '执行命令失败：' + error.message
              })
              finishExecution()
            })
        }

        readChunk()
      })
      .catch(error => {
        if (abortController.signal.aborted || stopExecutionFlags.value[index] || isAbortError(error)) {
          reportStopped()
          finishExecution()
          return
        }

        console.error('执行命令失败:', error)
        executionResults.value = [
          { status: 'error', message: '执行命令失败：' + error.message }
        ]
        finishExecution()
      })
  })
}
// 停止执行
const stopExecution = (index) => {
  stopExecutionFlags.value[index] = true
  abortExecution(index)
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
  openExecutionResultModal(rowIndex, matchedEntry)
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
      abortExecution(rowIndex)
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

const executionStatusLabel = (status) => {
  if (status === 'success') {
    return 'SUCCESS'
  }
  if (status === 'error') {
    return 'ERROR'
  }
  return 'INFO'
}

const clearExecutionLogs = () => {
  executionResults.value = []
}

watch(() => executionResults.value.length, async (newLength, oldLength = 0) => {
  if (newLength === 0 || newLength <= oldLength) {
    return
  }

  await nextTick()
  const container = executionLogContainer.value
  if (container) {
    container.scrollTop = container.scrollHeight
  }
})

// 监听页码变化，更新跳转输入框
watch(currentPage, (newPage) => {
  jumpPage.value = newPage
})

watch(
  [selectedDevice, selectedFile, rowIndex, filterResult, searchKeyword, currentPage, jumpPage, pageSize, selectedRows, executionResults, rowScreenshots, rowResultMeta],
  () => {
    persistExecutionState()
  },
  { deep: true }
)

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
        validationResult.value = null
        executionResults.value = []
        rowScreenshots.value = {}
        rowResultMeta.value = {}
        selectedRows.value = []
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
