<template>
  <div class="card w-full max-w-7xl mx-auto excel-execution-page">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <router-link to="/excel" class="btn btn-secondary btn-sm">
        {{ $t('common.chooseFeature') }}
      </router-link>
      <h2 class="mb-0">{{ $t('excelAsr.title') }}</h2>
    </div>

    <div class="excel-execution-scroll">
      <div class="space-y-4">
      <div class="excel-top-grid mb-6">
      <section v-if="showCompactFileSelectorPanel" class="excel-top-compact-card excel-section-card mb-0 rounded-[24px] border border-white/70 bg-white/72 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
        <div class="excel-top-compact-header">
          <div class="min-w-0">
            <p class="eyebrow">{{ $t('excelExecution.chooseExcel') }}</p>
            <h3 class="excel-top-compact-title">{{ selectedFile }}</h3>
            <p class="excel-top-compact-meta">{{ $t('excelExecution.fileReadyHint') }}</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button @click="analyzeFile" class="btn btn-primary btn-sm" :disabled="loadingAnalysis || !selectedFile">
              {{ loadingAnalysis ? $t('common.analyzing') : $t('common.analyzeFile') }}
            </button>
            <button
              v-if="validationResult"
              @click="openValidationResultModal"
              class="btn btn-secondary btn-sm"
              :disabled="loadingAnalysis"
            >
              {{ $t('excelExecution.viewAnalysisResult') }}
            </button>
            <button @click="expandFileSelectorPanel" class="btn btn-secondary btn-sm">
              {{ $t('excelExecution.changeSelectedFile') }}
            </button>
          </div>
        </div>
      </section>
      <section v-else class="excel-file-panel excel-section-card mb-0 rounded-[28px] border border-white/70 bg-white/72 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div class="min-w-0">
            <p class="eyebrow">{{ $t('excelExecution.chooseExcel') }}</p>
            <div class="mt-2 flex flex-wrap items-center gap-3">
              <h3 class="text-lg font-semibold tracking-tight text-slate-900">{{ selectedFile || $t('common.notSelected') }}</h3>
              <span class="rounded-full bg-white/80 px-3 py-1 text-sm text-gray-500">
                {{ $t('common.total', { count: excelFiles.length }) }}
              </span>
            </div>
            <p class="mt-2 text-sm leading-6 text-gray-500">
              {{ $t('excelAsr.prepSubtitle') }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button @click="loadExcelFiles" class="btn btn-secondary btn-sm" :disabled="loadingFiles">
              {{ loadingFiles ? $t('common.refreshing') : $t('common.refreshFileList') }}
            </button>
            <button class="btn btn-primary btn-sm" @click="triggerExcelUpload">{{ $t('common.uploadExcel') }}</button>
            <button @click="analyzeFile" class="btn btn-primary btn-sm" :disabled="loadingAnalysis || !selectedFile">
              {{ loadingAnalysis ? $t('common.analyzing') : $t('common.analyzeFile') }}
            </button>
            <button
              v-if="validationResult"
              @click="openValidationResultModal"
              class="btn btn-secondary btn-sm"
              :disabled="loadingAnalysis"
            >
              {{ $t('excelExecution.viewAnalysisResult') }}
            </button>
          </div>
        </div>

        <div v-if="loadingFiles" class="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
          {{ $t('common.loading') }}
        </div>

        <template v-else-if="excelFiles.length > 0">
          <p class="mt-4 mb-3 text-sm text-slate-500">{{ $t('common.currentDirectoryExcelFiles') }}</p>
          <div class="excel-file-list space-y-2">
            <div
              v-for="(file, index) in excelFiles"
              :key="file"
              class="excel-file-item border rounded-lg cursor-pointer bg-white/80 hover:bg-gray-50"
              :class="selectedFile === file ? 'border-primary bg-blue-50' : ''"
              @click="selectFile(file)"
            >
              <div class="flex items-center justify-between gap-4">
                <div class="flex-1 min-w-0">
                  <p class="font-medium">{{ $t('common.fileNumber', { index: index + 1 }) }}</p>
                  <p class="text-gray-600 truncate">{{ file }}</p>
                </div>
                <div class="flex items-center gap-2">
                  <button class="btn btn-danger btn-sm" @click.stop="deleteFile(file)" :disabled="deletingFile">
                    {{ $t('common.delete') }}
                  </button>
                  <div class="text-primary" v-if="selectedFile === file">
                    ✅
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div v-else class="mt-4 rounded-lg border border-yellow-200 bg-yellow-50 p-4">
          <p class="text-danger mb-4">{{ $t('common.noExcelFiles') }}</p>
          <h4 class="font-medium mb-2">{{ $t('common.hint') }}</h4>
          <p class="text-sm mb-2">{{ $t('excelAsr.uploadTip1') }}</p>
          <p class="text-sm">{{ $t('excelAsr.uploadTip2') }}</p>
        </div>
      </section>

      <section v-if="showCompactModelSelectorPanel" class="excel-top-compact-card excel-section-card mb-0 rounded-[24px] border border-white/70 bg-white/65 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_20px_44px_rgba(15,23,42,0.08)]">
        <div class="excel-top-compact-header">
          <div class="min-w-0">
            <p class="eyebrow">{{ $t('excelAsr.modelSetup') }}</p>
            <h3 class="excel-top-compact-title">{{ activeModelName || $t('excelAsr.noActiveModel') }}</h3>
            <p class="excel-top-compact-meta">{{ $t('excelAsr.currentDevice', { device: selectedDevice || $t('common.notSelected') }) }}</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button class="btn btn-secondary btn-sm" @click="loadStatus" :disabled="loadingStatus || importingModel || selectingModel || deletingModel">
              {{ loadingStatus ? $t('common.refreshing') : $t('common.refreshStatus') }}
            </button>
            <button class="btn btn-secondary btn-sm" @click="expandModelSelectorPanel">
              {{ $t('excelExecution.changeSelectedModel') }}
            </button>
          </div>
        </div>
      </section>
      <section v-else class="excel-section-card excel-top-model-panel mb-0 rounded-[28px] border border-white/70 bg-white/65 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_20px_44px_rgba(15,23,42,0.08)]">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div class="min-w-0">
            <p class="eyebrow">{{ $t('excelAsr.modelSetup') }}</p>
            <div class="mt-2 flex flex-wrap items-center gap-3">
              <h3 class="text-lg font-semibold tracking-tight">{{ $t('excelAsr.modelTitle') }}</h3>
              <span class="rounded-full bg-white/80 px-3 py-1 text-sm text-gray-500">
                {{ activeModelName ? $t('excelAsr.activeModel', { model: activeModelName }) : $t('excelAsr.noActiveModel') }}
              </span>
            </div>
            <p class="mt-2 text-sm leading-6 text-gray-500">
              {{ $t('excelAsr.modelSubtitle') }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button class="btn btn-secondary btn-sm" @click="loadStatus" :disabled="loadingStatus || importingModel || selectingModel || deletingModel">
              {{ loadingStatus ? $t('common.refreshing') : $t('common.refreshStatus') }}
            </button>
            <button class="btn btn-primary btn-sm" @click="triggerModelFolderPicker" :disabled="importingModel || selectingModel || deletingModel">
              {{ importingModel ? $t('excelAsr.importingModel', { completed: modelImportProgress.completed, total: modelImportProgress.total }) : $t('excelAsr.importModelDirectory') }}
            </button>
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-3 text-sm text-gray-600">
          <span>{{ $t('excelAsr.importedModels', { count: status.imported_models?.length || 0 }) }}</span>
          <span>{{ $t('excelAsr.currentDevice', { device: selectedDevice || $t('common.notSelected') }) }}</span>
          <span :class="missingAsrDependencies.length ? 'text-warning' : 'text-success'">
            {{ $t('excelAsr.environmentStatus', { status: missingAsrDependencies.length ? $t('common.missingDependencies') : $t('common.ready') }) }}
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
                  <span v-if="model.is_active" class="rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700">{{ $t('excelAsr.modelInUse') }}</span>
                  <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{{ $t('excelAsr.modelFiles', { count: model.file_count }) }}</span>
                  <span
                    v-if="formatBackendKindLabel(model.kind)"
                    class="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700"
                  >
                    {{ formatBackendKindLabel(model.kind) }}
                  </span>
                </div>
                <p class="text-gray-500 text-sm break-all mt-2">{{ model.path }}</p>
              </div>
              <div class="flex items-center gap-2">
                <button class="btn btn-secondary" @click="selectModel(model.name)" :disabled="selectingModel || deletingModel || importingModel || model.is_active">
                  {{ model.is_active ? $t('excelAsr.selectedModel') : $t('excelAsr.useThisModel') }}
                </button>
                <button class="btn btn-danger" @click="deleteModel(model.name)" :disabled="deletingModel || selectingModel || importingModel">
                  {{ $t('common.delete') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="mt-4 bg-yellow-50 p-4 rounded-lg">
          <p class="text-sm text-gray-600">{{ $t('excelAsr.noModels') }}</p>
        </div>
      </section>
      </div>

      <!-- 执行设置 -->
      <div class="mb-4 flex items-center gap-3">
        <button
          class="btn btn-secondary btn-sm"
          @click="showExecutionSettings = !showExecutionSettings"
        >
          ⚙ {{ showExecutionSettings ? '隐藏设置' : '执行设置' }}
        </button>
      </div>

      <div v-if="showExecutionSettings" class="mb-6 rounded-xl border border-gray-200 bg-gray-50/80 p-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

          <!-- 匹配阈值 -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">匹配阈值</label>
            <div class="flex items-center gap-2">
              <input
                v-model.number="matchThreshold"
                type="range"
                min="0.5"
                max="1"
                step="0.01"
                class="flex-1"
              >
              <input
                v-model.number="matchThreshold"
                type="number"
                min="0"
                max="1"
                step="0.01"
                class="form-input w-16 text-center text-sm"
              >
            </div>
          </div>

          <!-- 执行模式 -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">执行模式</label>
            <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
              <button
                class="px-3 py-1.5 flex-1 transition-colors"
                :class="executionMode === 'single' ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="executionMode = 'single'"
              >单次</button>
              <button
                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                :class="executionMode === 'loop_row' ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="executionMode = 'loop_row'"
              >单行循环</button>
              <button
                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                :class="executionMode === 'loop_list' ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="executionMode = 'loop_list'"
              >列表循环</button>
            </div>
          </div>

          <!-- 执行后校验 -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">执行后校验</label>
            <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
              <button
                class="px-3 py-1.5 flex-1 transition-colors"
                :class="enableVerification ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="enableVerification = true"
              >开启</button>
              <button
                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                :class="!enableVerification ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="enableVerification = false"
              >关闭</button>
            </div>
          </div>

          <!-- 执行录屏 -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">执行录屏</label>
            <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
              <button
                class="px-3 py-1.5 flex-1 transition-colors"
                :class="enableRecording ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="enableRecording = true"
              >开启</button>
              <button
                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                :class="!enableRecording ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="enableRecording = false"
              >关闭</button>
            </div>
          </div>

          <!-- 录制模式 -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">录制模式</label>
            <div class="inline-flex rounded-lg border border-gray-200 overflow-hidden text-sm">
              <button
                class="px-3 py-1.5 flex-1 transition-colors"
                :class="audioInputMode === 'speaker' ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="onAudioModeChange('speaker')"
              >外放</button>
              <button
                class="px-3 py-1.5 flex-1 transition-colors border-l border-gray-200"
                :class="audioInputMode === 'capture_card' ? 'bg-[#e8f2fe] text-[#1890ff]' : 'bg-white text-gray-600 hover:bg-gray-50'"
                @click="onAudioModeChange('capture_card')"
              >采集卡</button>
            </div>
          </div>

          <!-- 音频输入设备 -->
          <div class="flex flex-col gap-1.5">
            <div class="flex items-center justify-between">
              <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">音频输入设备</label>
              <button class="text-xs text-blue-500 hover:text-blue-700" @click="loadAudioDevices" :disabled="loadingAudioDevices">
                {{ loadingAudioDevices ? '刷新中...' : '刷新' }}
              </button>
            </div>
            <select
              class="form-input w-full text-sm"
              :value="audioDeviceIndex ?? ''"
              @change="onAudioDeviceChange($event.target.value)"
            >
              <option value="">系统默认</option>
              <option v-for="device in audioDevices" :key="device.index" :value="device.index">
                [{{ device.type === 'output' ? '输出' : '输入' }}|{{ device.hostapi }}] {{ device.name }} {{ device.is_default ? '(默认)' : '' }}
              </option>
            </select>
          </div>

          <!-- 颜色相似度下限 -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">颜色相似度下限</label>
            <div class="flex items-center gap-2">
              <input
                v-model.number="colorMinSimilarity"
                type="range"
                min="0"
                max="1"
                step="0.01"
                class="flex-1"
              >
              <input
                v-model.number="colorMinSimilarity"
                type="number"
                min="0"
                max="1"
                step="0.01"
                class="form-input w-16 text-center text-sm"
              >
            </div>
          </div>

          <!-- 颜色权重 -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">颜色权重</label>
            <div class="flex items-center gap-2">
              <input
                v-model.number="colorWeight"
                type="range"
                min="0"
                max="0.6"
                step="0.01"
                class="flex-1"
              >
              <input
                v-model.number="colorWeight"
                type="number"
                min="0"
                max="0.6"
                step="0.01"
                class="form-input w-16 text-center text-sm"
              >
            </div>
          </div>

          <!-- 特征相似度下限 -->
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-gray-500 uppercase tracking-wide">特征相似度下限</label>
            <div class="flex items-center gap-2">
              <input
                v-model.number="featureMinSimilarity"
                type="range"
                min="0"
                max="1"
                step="0.01"
                class="flex-1"
              >
              <input
                v-model.number="featureMinSimilarity"
                type="number"
                min="0"
                max="1"
                step="0.01"
                class="form-input w-16 text-center text-sm"
              >
            </div>
          </div>

        </div>
      </div>

      <div v-if="selectedFile" class="mb-6">
        <div v-if="loadingAnalysis">
          <p>{{ $t('common.analyzing') }}</p>
        </div>

        <div v-else-if="excelAnalysis">
          <div v-if="excelAnalysis.valid_rows.length > 0">
            <p class="mb-3">{{ $t('common.foundValidRows', { count: excelAnalysis.valid_rows.length }) }}</p>

            <div class="mb-4 flex flex-wrap gap-4 items-center">
              <div class="flex-1 min-w-[200px]">
                <label class="form-label mr-2">{{ $t('common.search') }}</label>
                <input
                  v-model="searchKeyword"
                  type="text"
                  class="form-input w-full"
                  :placeholder="$t('excelAsr.searchPlaceholder')"
                >
              </div>
            </div>

            <div class="mb-4 flex justify-between items-center gap-3 flex-wrap">
              <div class="flex flex-wrap items-center gap-3">
                <button class="btn btn-secondary" @click="addNewCase" :disabled="!selectedFile || isBatchExecuting">
                  {{ $t('excelAsr.addCase') }}
                </button>
                <button class="btn btn-danger" @click="deleteSelectedCases" :disabled="selectedRows.length === 0 || isBatchExecuting">
                  {{ $t('excelAsr.deleteSelected', { count: selectedRows.length }) }}
                </button>
                <button class="btn btn-success" @click="executeSelectedRows" :disabled="selectedRows.length === 0 || isBatchExecuting || hasActiveExecution || !canExecuteAsr">
                  {{ $t('excelAsr.batchExecute', { count: selectedRows.length }) }}
                </button>
                <button class="btn btn-primary" @click="executeAllRows" :disabled="allRowIndexes.length === 0 || isBatchExecuting || hasActiveExecution || !canExecuteAsr">
                  {{ $t('excelAsr.executeAll', { count: allRowIndexes.length }) }}
                </button>
                <button v-if="latestBatchReport?.report_url" class="btn btn-secondary" @click="openLatestBatchReport">
                  {{ $t('excelAsr.openLatestReport') }}
                </button>
              </div>
              <button class="btn btn-danger" @click="stopAllExecution" :disabled="!isBatchExecuting">
                {{ $t('excelAsr.stopAll') }}
              </button>
            </div>

            <div class="excel-table-shell mb-4 overflow-x-auto rounded-[28px] border border-white/70 bg-white/72 shadow-[inset_0_1px_0_rgba(255,255,255,0.92),0_18px_40px_rgba(15,23,42,0.08)]">
              <table class="excel-results-table w-full min-w-[980px] table-fixed">
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
                    <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelAsr.columns.title') }}</th>
                    <th class="border px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelAsr.columns.steps') }}</th>
                    <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelAsr.columns.actions') }}</th>
                    <th class="border px-3 py-3 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{{ $t('excelAsr.columns.result') }}</th>
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
                      <!-- 执行中：指令动效（展开，支持换行） -->
                      <div v-if="executingRows[item.idx] && getRowCommandTokens(item.row).length" class="excel-step-group">
                        <span
                          v-for="cmd in getRowCommandTokens(item.row)"
                          :key="cmd.id"
                          class="excel-step-command"
                          :class="{ 'excel-step-command-active': isCommandActive(item.idx, cmd) }"
                          :title="cmd.raw"
                        >
                          <span class="excel-step-command-key">{{ cmd.key }}</span>
                          <span v-if="cmd.meta" class="excel-step-command-meta">{{ cmd.meta }}</span>
                          <span v-if="getCommandProgress(item.idx, cmd)" class="excel-step-command-progress">{{ getCommandProgress(item.idx, cmd) }}</span>
                        </span>
                      </div>
                      <!-- 未执行：指令序列（单行，溢出渐隐） -->
                      <div
                        v-else-if="getRowCommandTokens(item.row).length"
                        class="excel-step-sequence-collapsed"
                        :title="getRowCommandTokens(item.row).map(c => c.raw).join(', ')"
                      >
                        <span
                          v-for="cmd in getRowCommandTokens(item.row)"
                          :key="cmd.id"
                          class="excel-step-command"
                          :title="cmd.raw"
                        >
                          <span class="excel-step-command-key">{{ cmd.key }}</span>
                          <span v-if="cmd.meta" class="excel-step-command-meta">{{ cmd.meta }}</span>
                        </span>
                      </div>
                      <span v-else>-</span>
                    </td>
                    <td class="border px-3 py-3 text-center align-top">
                      <div class="excel-row-actions flex flex-col items-center gap-2">
                        <button
                          class="btn btn-secondary min-w-[88px] whitespace-nowrap"
                          @click="openCaseEditModal(item)"
                          :disabled="savingCaseFields || executingRows[item.idx]"
                        >
                          {{ $t('common.edit') }}
                        </button>
                        <button
                          class="btn btn-danger min-w-[88px] whitespace-nowrap"
                          @click="deleteCase(item)"
                          :disabled="isBatchExecuting || executingRows[item.idx]"
                        >
                          {{ $t('excelAsr.deleteCase') }}
                        </button>
                        <button
                          v-if="!executingRows[item.idx]"
                          class="btn btn-primary min-w-[88px] whitespace-nowrap"
                          @click="executeAsrRowByIndex(item.idx)"
                          :disabled="!canExecuteAsr || isBatchExecuting || hasActiveExecution"
                        >
                          {{ $t('common.execute') }}
                        </button>
                        <button
                          v-else
                          class="btn btn-danger min-w-[88px] whitespace-nowrap"
                          @click="stopExecution(item.idx)"
                        >
                          {{ $t('common.stop') }}
                        </button>
                      </div>
                    </td>
                    <td class="border px-3 py-3 text-center align-top">
                      <div v-if="rowRunMeta[item.idx] && (rowRunMeta[item.idx].asr_result || rowRunMeta[item.idx].tts_text || rowRunMeta[item.idx].transcribed_text || rowRunMeta[item.idx].reference_text || Number.isFinite(rowRunMeta[item.idx].asr_score))" class="space-y-2 text-left">
                        <!-- 多段结果 -->
                        <template v-if="rowRunMeta[item.idx].segments && rowRunMeta[item.idx].segments.length > 1">
                          <div v-for="(seg, si) in rowRunMeta[item.idx].segments" :key="si" class="border-l-2 pl-2 mb-2" :class="si > 0 ? 'border-slate-200' : 'border-transparent'">
                            <div class="flex flex-wrap items-center gap-2">
                              <span class="text-xs font-medium text-slate-400">段{{ si + 1 }}</span>
                              <span
                                v-if="seg.asr_result"
                                class="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold"
                                :class="getAsrResultBadgeClass(seg.asr_result)"
                              >
                                {{ seg.asr_result }}
                              </span>
                              <span v-if="Number.isFinite(seg.asr_score)" class="text-sm font-semibold text-slate-700">
                                {{ formatAsrScore(seg.asr_score) }}
                              </span>
                            </div>
                            <p v-if="seg.reference_text" class="line-clamp-2 text-xs leading-5 text-slate-500" :title="seg.reference_text">
                              TTS：{{ seg.reference_text }}
                            </p>
                            <p v-if="seg.transcribed_text" class="line-clamp-2 text-xs leading-5 text-slate-500" :title="seg.transcribed_text">
                              ASR：{{ seg.transcribed_text }}
                            </p>
                            <p v-else-if="seg.asr_result === 'NO_REF'" class="text-xs leading-5 text-amber-600">
                              {{ $t('excelAsr.noReference') }}
                            </p>
                          </div>
                        </template>
                        <!-- 单段结果（兼容原有展示） -->
                        <template v-else>
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
                          <p v-if="rowRunMeta[item.idx].reference_text" class="line-clamp-3 text-xs leading-5 text-slate-500" :title="rowRunMeta[item.idx].reference_text">
                            TTS：{{ rowRunMeta[item.idx].reference_text }}
                          </p>
                          <p v-if="rowRunMeta[item.idx].transcribed_text" class="line-clamp-3 text-xs leading-5 text-slate-500" :title="rowRunMeta[item.idx].transcribed_text">
                            ASR：{{ rowRunMeta[item.idx].transcribed_text }}
                          </p>
                          <p v-else-if="rowRunMeta[item.idx].asr_result === 'NO_REF'" class="text-xs leading-5 text-amber-600">
                            {{ $t('excelAsr.noReference') }}
                          </p>
                        </template>
                      </div>
                      <span v-else>-</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="flex items-center justify-between flex-wrap gap-3">
              <div class="flex items-center gap-2">
                <span>{{ $t('common.perPage') }}</span>
                <select v-model.number="pageSize" class="form-select">
                  <option :value="10">10</option>
                  <option :value="20">20</option>
                  <option :value="50">50</option>
                </select>
                <span>{{ $t('common.items') }}</span>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <button class="btn btn-secondary" @click="handlePrevPage" :disabled="currentPage === 1">{{ $t('common.previousPage') }}</button>
                <span>{{ $t('common.pageInfo', { current: currentPage, total: totalPages }) }}</span>
                <div class="flex items-center gap-1">
                  <span>{{ $t('common.goTo') }}</span>
                  <input
                    v-model.number="jumpPage"
                    type="number"
                    class="form-input w-16 text-center"
                    :min="1"
                    :max="totalPages"
                    @keyup.enter="handleJumpPage"
                  >
                  <button class="btn btn-primary btn-sm" @click="handleJumpPage" :disabled="!jumpPage || jumpPage < 1 || jumpPage > totalPages">{{ $t('common.jump') }}</button>
                </div>
                <button class="btn btn-secondary" @click="handleNextPage" :disabled="currentPage === totalPages">{{ $t('common.nextPage') }}</button>
                <span>{{ $t('common.total', { count: filteredRows.length }) }}</span>
              </div>
            </div>

            <div v-if="excelAnalysis.skipped_rows?.length > 0" class="excel-note-card bg-yellow-50 p-4 rounded-lg mb-4 mt-4">
              <h4 class="font-medium mb-2">{{ $t('excelExecution.skippedRows') }}</h4>
              <div class="space-y-2 max-h-40 overflow-y-auto">
                <div v-for="(row, index) in excelAnalysis.skipped_rows" :key="index" class="text-sm">
                  <div class="break-all">{{ $t('excelExecution.rowFallbackTitle', { row: row.row }) }}: {{ row.reason }}</div>
                </div>
              </div>
            </div>
          </div>

          <div v-else>
            <p class="text-danger">{{ $t('excelExecution.noValidCommands') }}</p>
          </div>
        </div>
      </div>

      <div
        v-if="showValidationResultModal && validationResult"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      >
        <div class="bg-white rounded-[24px] shadow-xl p-5 w-[92vw] max-w-4xl max-h-[88vh] overflow-hidden flex flex-col">
          <div class="flex items-start justify-between gap-4 mb-4">
            <div class="min-w-0">
              <h3 class="text-lg font-medium break-words">
                {{ $t('common.fileValidationResult', { status: validationResult.success ? $t('common.pass') : $t('common.fail'), count: validationResult.total_rows }) }}
              </h3>
              <p v-if="selectedFile" class="text-sm text-gray-500 mt-1 break-all">{{ selectedFile }}</p>
            </div>
            <button @click="closeValidationResultModal" class="text-gray-500 hover:text-gray-700">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="overflow-y-auto pr-1 space-y-4">
            <div
              class="rounded-[20px] border px-4 py-4"
              :class="validationResult.success ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'"
            >
              <div class="flex items-start gap-3">
                <span
                  class="text-xl"
                  :class="validationResult.success ? 'text-green-600' : 'text-red-600'"
                >
                  {{ validationResult.success ? '✅' : '❌' }}
                </span>
                <div class="min-w-0">
                  <p class="font-medium text-slate-900">
                    {{ $t('common.fileValidationResult', { status: validationResult.success ? $t('common.pass') : $t('common.fail'), count: validationResult.total_rows }) }}
                  </p>
                </div>
              </div>
            </div>

            <div v-if="validationResult.errors && validationResult.errors.length > 0" class="rounded-[20px] border border-red-200 bg-red-50 px-4 py-4">
              <p class="text-sm font-medium text-red-700 mb-2">{{ $t('common.errors') }}</p>
              <div class="space-y-1 text-sm text-red-600">
                <div v-for="(error, idx) in validationResult.errors" :key="idx" class="break-all">
                  {{ error }}
                </div>
              </div>
            </div>

            <div v-if="validationResult.warnings && validationResult.warnings.length > 0" class="rounded-[20px] border border-yellow-200 bg-yellow-50 px-4 py-4">
              <p class="text-sm font-medium text-yellow-700 mb-2">{{ $t('common.warnings') }}</p>
              <div class="space-y-1 text-sm text-yellow-600">
                <div v-for="(warning, idx) in validationResult.warnings" :key="idx" class="break-all">
                  {{ warning }}
                </div>
              </div>
            </div>
          </div>

          <div class="mt-4 flex justify-end">
            <button class="btn btn-secondary" @click="closeValidationResultModal">
              {{ $t('common.close') }}
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="showCaseEditModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      >
        <div class="bg-white rounded-lg shadow-xl p-6 w-[92vw] max-w-2xl">
          <div class="flex items-start justify-between gap-4 mb-4">
            <div>
              <h3 class="text-lg font-medium">{{ $t('excelExecution.editCaseInfo') }}</h3>
              <p v-if="editingCaseExcelRow" class="text-sm text-gray-500 mt-1">
                {{ $t('excelExecution.editCaseRow', { row: editingCaseExcelRow }) }}
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
              <label class="form-label">{{ $t('excelExecution.caseTitle') }}</label>
              <input
                v-model="editingCaseForm.title"
                type="text"
                class="form-input w-full"
                :placeholder="$t('excelExecution.caseTitlePlaceholder')"
              >
            </div>
            <div>
              <label class="form-label">{{ $t('excelExecution.originalSteps') }}</label>
              <textarea
                v-model="editingCaseForm.ori_step"
                class="form-input w-full min-h-[120px] resize-y"
                :placeholder="$t('excelExecution.originalStepsPlaceholder')"
              ></textarea>
            </div>
            <div>
              <label class="form-label">{{ $t('excelExecution.preScript') }}</label>
              <textarea
                v-model="editingCaseForm.pre_script"
                class="form-input w-full min-h-[120px] resize-y"
                :placeholder="$t('excelExecution.preScriptPlaceholder')"
              ></textarea>
            </div>
            <div>
              <label class="form-label">{{ $t('excelExecution.verifyImageField') }}</label>
              <input
                v-model="editingCaseForm.verify_image"
                type="text"
                class="form-input w-full"
                :placeholder="$t('excelExecution.verifyImagePlaceholder')"
              >
            </div>
          </div>

          <div class="mt-6 flex justify-end gap-3">
            <button class="btn btn-secondary" @click="closeCaseEditModal" :disabled="savingCaseFields">
              {{ $t('common.cancel') }}
            </button>
            <button class="btn btn-primary" @click="saveCaseFields" :disabled="savingCaseFields">
              {{ savingCaseFields ? $t('excelExecution.saving') : $t('common.saveChanges') }}
            </button>
          </div>
        </div>
      </div>

      <input
        ref="fileInput"
        type="file"
        class="hidden"
        accept=".xlsx,.xls"
        @change="uploadFile"
      >
      <input
        ref="modelFolderInput"
        type="file"
        class="hidden"
        webkitdirectory
        directory
        multiple
        @change="handleModelFolderChange"
      >
    </div>
    </div>

    <UploadExcelConfirmModal
      :visible="uploadConfirmVisible"
      @confirm="confirmUpload"
      @cancel="cancelUpload"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import UploadExcelConfirmModal from '../../components/UploadExcelConfirmModal.vue'
import { useUploadExcelConfirm } from '../../composables/useUploadExcelConfirm.js'
import { showAlert as alert, showConfirm as confirm, showPrompt as prompt } from '../../stores/dialogStore'

// 命名组件，供 ExcelFeatureLayout 内的 <keep-alive include="ExcelAsrAutomation"> 缓存匹配
defineOptions({ name: 'ExcelAsrAutomation' })
import {
  beginExecution,
  executionState,
  isExecutionRunning,
  finishExecution as finishExecutionStore,
  recordRowResult,
  registerStopHandler,
} from '../../stores/executionStore'

const { t } = useI18n({ useScope: 'global' })

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
const executionAbortControllers = ref({})
const selectedRows = ref([])
const searchKeyword = ref('')
const currentPage = ref(1)
const jumpPage = ref(1)
const pageSize = ref(20)
const isBatchExecuting = ref(false)
const executionResults = ref([])
const rowRunMeta = ref({})
const latestBatchReport = ref(null)
const showCaseEditModal = ref(false)
const showValidationResultModal = ref(false)
const fileInput = ref(null)
const modelFolderInput = ref(null)
const fileSelectorPanelExpanded = ref(false)
const modelSelectorPanelExpanded = ref(false)
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
const audioInputMode = ref('speaker')
const audioDeviceIndex = ref(null)
const audioDevices = ref([])
const loadingAudioDevices = ref(false)
const savingAudioConfig = ref(false)
const showExecutionSettings = ref(false)
const executionMode = ref('single')
const enableRecording = ref(true)
const enableVerification = ref(true)
const matchThreshold = ref(0.85)
// 图片校验参数（后端 customization.json 全局区，image_service 运行时读取）
const colorMinSimilarity = ref(0.4)
const colorWeight = ref(0.2)
const featureMinSimilarity = ref(0.3)
let colorVerifyConfigTimer = null

const loadColorVerifyConfig = async () => {
  try {
    const res = await fetch('/api/customization/color-verify-config')
    if (res.ok) {
      const data = await res.json()
      const minSimilarity = Number(data.color_min_similarity)
      const weight = Number(data.color_weight)
      const featureMin = Number(data.feature_min_similarity)
      colorMinSimilarity.value = Number.isFinite(minSimilarity) ? minSimilarity : 0.4
      colorWeight.value = Number.isFinite(weight) ? weight : 0.2
      featureMinSimilarity.value = Number.isFinite(featureMin) ? featureMin : 0.3
    }
  } catch (error) {
    console.error('加载图片校验配置失败:', error)
  }
}

const saveColorVerifyConfig = async () => {
  try {
    await fetch('/api/customization/color-verify-config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        color_min_similarity: colorMinSimilarity.value,
        color_weight: colorWeight.value,
        feature_min_similarity: featureMinSimilarity.value,
      })
    })
  } catch (error) {
    console.error('保存图片校验配置失败:', error)
  }
}

// 校验参数改动后防抖保存到后端（image_service 每次校验实时读取，立即生效）
watch([colorMinSimilarity, colorWeight, featureMinSimilarity], () => {
  if (colorVerifyConfigTimer) clearTimeout(colorVerifyConfigTimer)
  colorVerifyConfigTimer = setTimeout(saveColorVerifyConfig, 500)
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
const hasAnalyzedCurrentFile = computed(() => Boolean(selectedFile.value && (validationResult.value || excelAnalysis.value)))
const shouldCollapseFileSelectorPanel = computed(() => Boolean(selectedFile.value && (hasAnalyzedCurrentFile.value || activeModelName.value)))
const shouldCollapseModelSelectorPanel = computed(() => Boolean(selectedFile.value && activeModelName.value))
const showCompactFileSelectorPanel = computed(() => shouldCollapseFileSelectorPanel.value && !fileSelectorPanelExpanded.value)
const showCompactModelSelectorPanel = computed(() => shouldCollapseModelSelectorPanel.value && !modelSelectorPanelExpanded.value)
const asrDependencyBlockMessage = computed(() => {
  if (missingAsrDependencies.value.length === 0) {
    return ''
  }

  const commands = Array.isArray(asrDependencyStatus.value.install_commands)
    ? asrDependencyStatus.value.install_commands
    : []
  const commandText = commands.length ? `\n\n${t('excelAsr.handlingSteps')}\n${commands.join('\n')}` : ''
  return `${t('excelAsr.dependencyWarning')} ${t('excelAsr.missingDependencies', { dependencies: missingAsrDependencies.value.join(', ') })}${commandText}`
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

const readErrorMessage = async (response, fallbackMessage) => {
  try {
    const data = await response.json()
    return data.detail || data.message || fallbackMessage
  } catch {
    return fallbackMessage
  }
}

const isAbortError = (error) => {
  if (!error) {
    return false
  }

  const message = String(error.message || error || '').toLowerCase()
  return error.name === 'AbortError' || message.includes('abort') || message.includes('aborted')
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
      throw new Error(await readErrorMessage(response, `${t('excelAsr.alerts.loadStatusFailed')}: ${response.status}`))
    }

    const data = await response.json()
    Object.assign(status, data)
  } catch (error) {
    console.error('加载 ASR 状态失败:', error)
    statusErrorMessage.value = error instanceof Error ? error.message : t('excelAsr.alerts.loadStatusFailed')
  } finally {
    loadingStatus.value = false
  }
}

const loadAudioDevices = async () => {
  loadingAudioDevices.value = true
  try {
    const response = await fetch('/api/excel/asr/audio-devices')
    if (!response.ok) throw new Error('获取音频设备列表失败')
    const data = await response.json()
    audioDevices.value = data.devices || []
  } catch (error) {
    console.error('获取音频设备列表失败:', error)
    audioDevices.value = []
  } finally {
    loadingAudioDevices.value = false
  }
}

const loadAudioConfig = async () => {
  try {
    const response = await fetch('/api/excel/asr/audio-config')
    if (!response.ok) throw new Error('获取音频配置失败')
    const data = await response.json()
    audioInputMode.value = data.audio_input_mode || 'speaker'
    audioDeviceIndex.value = data.audio_device_index ?? null
  } catch (error) {
    console.error('获取音频配置失败:', error)
  }
}

const saveAudioConfig = async () => {
  savingAudioConfig.value = true
  try {
    const response = await fetch('/api/excel/asr/audio-config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_input_mode: audioInputMode.value,
        audio_device_index: audioDeviceIndex.value,
      }),
    })
    if (!response.ok) throw new Error('保存音频配置失败')
  } catch (error) {
    console.error('保存音频配置失败:', error)
  } finally {
    savingAudioConfig.value = false
  }
}

const onAudioModeChange = async (mode) => {
  audioInputMode.value = mode
  audioDeviceIndex.value = null
  await saveAudioConfig()
}

const onAudioDeviceChange = async (index) => {
  audioDeviceIndex.value = index === '' ? null : Number(index)
  await saveAudioConfig()
}

// 指令动效：解析命令为 token 列表
const parseCommandToken = (raw, index) => {
  if (!raw || String(raw).trim().toLowerCase() === 'nan') return null
  const parts = String(raw).trim().split('/')
  const key = (parts[0] || '').trim().toUpperCase()
  if (!key) return null
  const repeat = parseInt(parts[1]) || 1
  const delay = parseFloat(parts[2]) || 0
  const meta = []
  if (repeat > 1) meta.push(`x${repeat}`)
  if (delay > 0) meta.push(`${delay}s`)
  return { id: `cmd-${index}`, raw: String(raw).trim(), key, repeat, delay, meta: meta.join(' / '), index }
}

const getRowCommandTokens = (row) => {
  const commands = row?.commands || []
  return commands.map((cmd, i) => parseCommandToken(cmd, i)).filter(Boolean)
}

// 指令动效：跟踪当前执行到哪条指令 + 重复次数 + 耗时
const rowActiveCommandIndex = ref({})
const rowCommandProgress = ref({})  // { [rowIndex]: { repeat: '1/8', elapsed: '0.3s' } }

const isCommandActive = (rowIndex, cmd) => {
  const activeIdx = rowActiveCommandIndex.value[rowIndex]
  return activeIdx !== undefined && cmd.index === activeIdx
}

const getCommandProgress = (rowIndex, cmd) => {
  if (!isCommandActive(rowIndex, cmd)) return ''
  const progress = rowCommandProgress.value[rowIndex]
  if (!progress?.repeat) return '...'
  return progress.repeat
}

// 从 SSE 消息中解析指令进度
const parseCommandProgressFromMessage = (message) => {
  if (typeof message !== 'string') return null
  // 匹配 "✓ DOWN (1/8) 发送成功 (耗时199ms)" 或 "✓ DOWN 发送成功 (耗时199ms)"
  const match = message.match(/^✓\s+(\S+?)(?:\s+\((\d+)\/(\d+)\))?\s+发送成功\s+\(耗时(\d+)ms\)/)
  if (!match) return null
  return {
    key: match[1].trim().toUpperCase(),
    current: match[2] ? parseInt(match[2]) : null,
    total: match[3] ? parseInt(match[3]) : null,
    isLastRepeat: match[2] && match[3] ? parseInt(match[2]) === parseInt(match[3]) : true,
  }
}

const buildAsrExecutionLogEntry = (statusKey, message, rowIndex = null) => {
  return {
    status: statusKey,
    message,
    row_index: Number.isInteger(rowIndex) ? rowIndex : null,
    happened_at: new Date().toISOString()
  }
}

const appendExecutionLog = (statusKey, message, rowIndex = null) => {
  executionResults.value.push({
    ...buildAsrExecutionLogEntry(statusKey, message, rowIndex)
  })
}

const getBatchReportTitle = () => {
  const fileName = selectedFile.value || 'ASR'
  const baseName = fileName.replace(/\.[^.]+$/, '')
  return `${baseName}报告`
}

const buildAsrBatchReportRows = (rowIndexes) => {
  const validRows = excelAnalysis.value?.valid_rows || []
  return rowIndexes.map((rowIndex) => {
    const row = validRows[rowIndex - 1] || {}
    const meta = rowRunMeta.value[rowIndex] || {}
    const score = Number.isFinite(meta.asr_score) ? meta.asr_score : null
    return {
      row_index: rowIndex,
      case_title: row.title || t('excelExecution.rowFallbackTitle', { row: rowIndex }),
      asr_result: meta.asr_result || '',
      asr_score: score,
      transcribed_text: meta.transcribed_text || '',
      tts_text: meta.tts_text || '',
      reference_text: meta.reference_text || '',
      reference_path: meta.reference_path || '',
      audio_path: meta.audio_path || '',
      transcript_path: meta.transcript_path || '',
      compare_result_path: meta.compare_result_path || '',
      note: meta.asr_result === 'NO_REF' ? t('excelAsr.noReference') : ''
    }
  })
}

const createAsrBatchReport = async (rowIndexes, label) => {
  const rowResults = buildAsrBatchReportRows(rowIndexes)
  if (rowResults.length === 0) {
    return null
  }

  try {
    const response = await fetch('/api/reports/asr-batch', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: getBatchReportTitle(),
        file_name: selectedFile.value || '',
        label,
        device: selectedDevice.value || '',
        model_name: activeModelName.value || '',
        row_results: rowResults,
        execution_logs: executionResults.value.map((item) => ({
          status: item.status,
          message: item.message,
          row_index: Number.isInteger(item.row_index) ? item.row_index : null,
          happened_at: item.happened_at || ''
        }))
      })
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.reportGenerateFailed')))
    }

    const data = await response.json()
    latestBatchReport.value = data.report || null
    if (latestBatchReport.value?.title) {
      appendExecutionLog('success', t('excelAsr.alerts.reportGenerated', { title: latestBatchReport.value.title }))
    }
    return latestBatchReport.value
  } catch (error) {
    appendExecutionLog('error', error instanceof Error ? error.message : t('excelAsr.alerts.reportGenerateFailed'))
    return null
  }
}

const openLatestBatchReport = () => {
  if (!latestBatchReport.value?.report_url) {
    return
  }

  window.open(latestBatchReport.value.report_url, '_blank', 'noopener')
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
    await alert(t('excelAsr.alerts.unknownModelFolder'))
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
        throw new Error(await readErrorMessage(response, t('excelAsr.alerts.importModelFileFailed', { name: file.name })))
      }

      modelImportProgress.completed += 1
      modelImportMessage.value = t('excelAsr.alerts.importProgress', {
        model: modelName,
        completed: modelImportProgress.completed,
        total: modelImportProgress.total
      })
    }

    await loadStatus()
    modelImportMessage.value = t('excelAsr.alerts.importComplete', { model: modelName })
  } catch (error) {
    console.error('导入模型失败:', error)
    modelImportMessage.value = error instanceof Error ? error.message : t('excelAsr.alerts.importFailed')
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
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.switchModelFailed')))
    }

    await loadStatus()
  } catch (error) {
    console.error('切换模型失败:', error)
    await alert(error instanceof Error ? error.message : t('excelAsr.alerts.switchModelFailed'))
  } finally {
    selectingModel.value = false
  }
}

const formatBytes = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const formatBackendKindLabel = (kind) => {
  if (!kind) {
    return ''
  }

  const normalized = String(kind).toLowerCase()
  if (normalized === 'qwen') {
    return t('excelAsr.backendQwen')
  }
  if (normalized === 'cohere') {
    return t('excelAsr.backendCohere')
  }

  return ''
}


const deleteModel = async (modelName) => {
  if (!await confirm(t('excelAsr.alerts.deleteModelConfirm', { name: modelName }))) {
    return
  }

  deletingModel.value = true
  try {
    const response = await fetch(`/api/excel/asr/models?model_name=${encodeURIComponent(modelName)}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.deleteModelFailed')))
    }

    const data = await response.json()
    await loadStatus()

    if (data.active_model) {
      modelImportMessage.value = t('excelAsr.alerts.deleteModelSuccessWithActive', {
        deleted: data.deleted_model,
        active: data.active_model
      })
    } else {
      modelImportMessage.value = t('excelAsr.alerts.deleteModelSuccess', { deleted: data.deleted_model })
    }
  } catch (error) {
    console.error('删除模型失败:', error)
    await alert(error instanceof Error ? error.message : t('excelAsr.alerts.deleteModelFailed'))
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
  showValidationResultModal.value = false
  selectedRows.value = []
  currentPage.value = 1
  jumpPage.value = 1
  executionResults.value = []
  rowRunMeta.value = {}
}

// ───────────────────── 编辑弹窗：控制台操作日志 ─────────────────────
// 在编辑用例弹窗中记录用户操作，便于联调时在控制台追踪用户行为。
const logEditAction = (...args) => {
  console.log('[编辑ASR用例]', ...args)
}

// 表单字段变更防抖日志：停止输入 600ms 后输出一次"改了什么"
let editFormLogTimer = null
let lastEditFormSnapshot = null

const resetEditFormLogSnapshot = () => {
  lastEditFormSnapshot = { ...editingCaseForm }
}

const flushEditFormLog = () => {
  if (!showCaseEditModal.value || !lastEditFormSnapshot) {
    return
  }
  const changed = {}
  for (const key of Object.keys(editingCaseForm)) {
    if (editingCaseForm[key] !== lastEditFormSnapshot[key]) {
      changed[key] = { 旧值: lastEditFormSnapshot[key], 新值: editingCaseForm[key] }
    }
  }
  if (Object.keys(changed).length > 0) {
    logEditAction('用户修改字段:', changed)
  }
  lastEditFormSnapshot = { ...editingCaseForm }
}

watch(
  () => ({ ...editingCaseForm }),
  () => {
    if (!showCaseEditModal.value) {
      return
    }
    clearTimeout(editFormLogTimer)
    editFormLogTimer = setTimeout(flushEditFormLog, 600)
  }
)

const openCaseEditModal = (item) => {
  editingCaseIndex.value = item.idx
  editingCaseExcelRow.value = item.row.row
  editingCaseForm.title = item.row.title || ''
  editingCaseForm.ori_step = item.row.oriStep || item.row.step || ''
  editingCaseForm.pre_script = item.row.preScript || ''
  editingCaseForm.verify_image = item.row.verify_image || ''
  showCaseEditModal.value = true
  // 控制台日志：打开编辑弹窗（含初始字段值）
  logEditAction('打开编辑弹窗', {
    excel_row: editingCaseExcelRow.value,
    idx: editingCaseIndex.value,
    title: editingCaseForm.title,
    ori_step: editingCaseForm.ori_step,
    pre_script: editingCaseForm.pre_script,
    verify_image: editingCaseForm.verify_image,
  })
  resetEditFormLogSnapshot()
}

const closeCaseEditModal = (saved = false) => {
  logEditAction(saved ? '关闭编辑弹窗（保存成功）' : '关闭编辑弹窗（未保存/取消）', {
    excel_row: editingCaseExcelRow.value,
    title: editingCaseForm.title,
  })
  showCaseEditModal.value = false
  editingCaseIndex.value = null
  editingCaseExcelRow.value = null
  editingCaseForm.title = ''
  editingCaseForm.ori_step = ''
  editingCaseForm.pre_script = ''
  editingCaseForm.verify_image = ''
  lastEditFormSnapshot = null
}

const saveCaseFields = async () => {
  if (!selectedFile.value || !editingCaseIndex.value || !editingCaseExcelRow.value) {
    return
  }

  savingCaseFields.value = true
  // 控制台日志：提交保存
  logEditAction('点击"保存"，提交字段', {
    file_name: selectedFile.value,
    excel_row: editingCaseExcelRow.value,
    payload: {
      title: editingCaseForm.title,
      ori_step: editingCaseForm.ori_step,
      pre_script: editingCaseForm.pre_script,
      verify_image: editingCaseForm.verify_image,
    },
  })
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
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.updateCaseFailedSimple')))
    }

    logEditAction('保存成功', { excel_row: editingCaseExcelRow.value })

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

    closeCaseEditModal(true)
  } catch (error) {
    logEditAction('保存失败', { excel_row: editingCaseExcelRow.value, error: error.message })
    console.error('更新用例字段失败:', error)
    await alert(t('excelAsr.alerts.updateCaseFailed', { detail: error.message }))
  } finally {
    savingCaseFields.value = false
  }
}

const analyzeFile = async (options = {}) => {
  const { silent = false } = options
  if (!selectedFile.value) {
    if (!silent) {
      await alert(t('excelAsr.alerts.selectFileFirst'))
    }
    return
  }

  loadingAnalysis.value = true
  showValidationResultModal.value = false
  try {
    const validateResponse = await fetch(`/api/excel/validate?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!validateResponse.ok) {
      throw new Error(await readErrorMessage(validateResponse, t('excelAsr.alerts.validateFailed')))
    }

    validationResult.value = await validateResponse.json()
    if (!silent) {
      openValidationResultModal()
    }

    const response = await fetch(`/api/excel/analyze?file_name=${encodeURIComponent(selectedFile.value)}`)
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.analyzeFailed')))
    }

    excelAnalysis.value = await response.json()
    selectedRows.value = []
    searchKeyword.value = ''
    currentPage.value = 1
    jumpPage.value = 1
    rowRunMeta.value = {}
  } catch (error) {
    console.error('分析文件失败:', error)
    await alert(error instanceof Error ? error.message : t('excelAsr.alerts.analyzeFailed'))
  } finally {
    loadingAnalysis.value = false
  }
}

const {
  uploadConfirmVisible,
  requestUpload: requestUploadExcelConfirm,
  confirmUpload,
  cancelUpload,
} = useUploadExcelConfirm()

const triggerExcelUpload = () => {
  requestUploadExcelConfirm(() => {
    fileInput.value?.click()
  })
}

const openValidationResultModal = () => {
  if (validationResult.value) {
    showValidationResultModal.value = true
  }
}

const closeValidationResultModal = () => {
  showValidationResultModal.value = false
}

const expandFileSelectorPanel = () => {
  fileSelectorPanelExpanded.value = true
}

const expandModelSelectorPanel = () => {
  modelSelectorPanelExpanded.value = true
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
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.uploadFailed')))
    }

    const data = await response.json()
    await loadExcelFiles()
    selectFile(data.filename)
  } catch (error) {
    console.error('上传文件失败:', error)
    await alert(error instanceof Error ? error.message : t('excelAsr.alerts.uploadFailed'))
  } finally {
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

const deleteFile = async (file) => {
  if (!await confirm(t('excelAsr.alerts.deleteFileConfirm', { file }))) {
    return
  }

  deletingFile.value = true
  try {
    const response = await fetch(`/api/excel/delete?file_name=${encodeURIComponent(file)}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.deleteFileFailed')))
    }

    await loadExcelFiles()
    if (selectedFile.value === file) {
      selectedFile.value = ''
      excelAnalysis.value = null
      validationResult.value = null
      showValidationResultModal.value = false
      executionResults.value = []
      rowRunMeta.value = {}
    }
  } catch (error) {
    console.error('删除文件失败:', error)
    await alert(error instanceof Error ? error.message : t('excelAsr.alerts.deleteFileFailed'))
  } finally {
    deletingFile.value = false
  }
}

// 将单条执行结果投影到全局进度 store（ASR 模块）
const finalizeAsrRow = (index) => {
  const meta = rowRunMeta.value[index]
  let passed = false
  if (meta?.segments && meta.segments.length > 0) {
    passed = meta.segments.every((seg) => seg.asr_result === 'PASS')
  } else {
    passed = meta?.asr_result === 'PASS'
  }
  recordRowResult({ passed })
}

// 互斥兜底：其它模块执行中时不允许启动 ASR 执行
const assertAsrExecutionSlot = () => {
  if (isExecutionRunning.value && executionState.activeType !== 'asr') {
    alert(t('excelAsr.alerts.otherModuleRunning'))
    return false
  }
  return true
}

const executeAsrRowByIndex = (index) => {
  return new Promise(async (resolve) => {
    if (!selectedFile.value) {
      await alert(t('excelAsr.alerts.selectFileFirst'))
      resolve()
      return
    }

    if (!activeModelName.value) {
      await alert(t('excelAsr.alerts.selectModelFirst'))
      resolve()
      return
    }

    if (!selectedDevice.value) {
      await alert(t('excelAsr.alerts.selectDeviceFirst'))
      resolve()
      return
    }

    if (missingAsrDependencies.value.length > 0) {
      await alert(asrDependencyBlockMessage.value)
      resolve()
      return
    }

    if (!assertAsrExecutionSlot()) {
      resolve()
      return
    }

    // 批量执行时由 executeBatchRows 统一 beginExecution；仅单行执行在此初始化进度卡片
    if (!isBatchExecuting.value) {
      const asrRowData = excelAnalysis.value?.valid_rows?.[index - 1]
      const asrTitle = asrRowData?.title || `第 ${index} 行`
      if (!beginExecution({ type: 'asr', total: 1, label: asrTitle })) {
        resolve()
        return
      }
    }

    executingRows.value[index] = true
    stopExecutionFlags.value[index] = false
    rowRunMeta.value[index] = {}
    rowActiveCommandIndex.value = { ...rowActiveCommandIndex.value, [index]: 0 }
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
      appendExecutionLog('error', t('excelAsr.alerts.executionStopped'), index)
    }

    const finishExecution = () => {
      finalizeAsrRow(index)
      // 批量执行时由 executeBatchRows 统一结束；仅单行执行在此收尾
      if (!isBatchExecuting.value) {
        finishExecutionStore({ completed: !stopReported })
      }
      executingRows.value[index] = false
      const nextCmd = { ...rowActiveCommandIndex.value }
      delete nextCmd[index]
      rowActiveCommandIndex.value = nextCmd
      const nextProg = { ...rowCommandProgress.value }
      delete nextProg[index]
      rowCommandProgress.value = nextProg
      clearExecutionAbortController(index)
      resolve()
    }

    fetch('/api/excel/asr/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      signal: abortController.signal,
      body: JSON.stringify({
        file_name: selectedFile.value,
        row_index: index
      })
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await readErrorMessage(response, t('excelAsr.alerts.executeFailed')))
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        const readChunk = () => {
          if (stopExecutionFlags.value[index] || abortController.signal.aborted) {
            reader.cancel()
            reportStopped()
            finishExecution()
            return
          }

          reader.read().then(async ({ done, value }) => {
            if (done) {
              finishExecution()
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
                executionResults.value.push({
                  ...result,
                  row_index: index,
                  happened_at: new Date().toISOString()
                })

                // 根据 SSE 事件跟踪当前执行的指令
                const msg = result.message || ''
                const progressInfo = parseCommandProgressFromMessage(msg)
                if (progressInfo) {
                  const row = excelAnalysis.value?.valid_rows?.[index - 1]
                  const tokens = getRowCommandTokens(row || { commands: [] })
                  const currentActiveIdx = rowActiveCommandIndex.value[index] ?? 0

                  // 从当前活跃位置开始查找匹配的指令（避免匹配到同名的前一条）
                  let found = null
                  for (let i = currentActiveIdx; i < tokens.length; i++) {
                    if (tokens[i].key === progressInfo.key) {
                      found = tokens[i]
                      break
                    }
                  }
                  // 如果从当前位置找不到，从头找（容错）
                  if (!found) {
                    found = tokens.find(t => t.key === progressInfo.key)
                  }

                  if (found) {
                    // 如果是重复指令的最后一次，移动到下一条
                    if (progressInfo.isLastRepeat && found.index === currentActiveIdx) {
                      const nextIdx = found.index + 1
                      if (nextIdx < tokens.length) {
                        rowActiveCommandIndex.value = { ...rowActiveCommandIndex.value, [index]: nextIdx }
                        rowCommandProgress.value = { ...rowCommandProgress.value, [index]: { repeat: '' } }
                      }
                    } else {
                      rowActiveCommandIndex.value = { ...rowActiveCommandIndex.value, [index]: found.index }
                      const repeat = (progressInfo.current && progressInfo.total) ? `${progressInfo.current}/${progressInfo.total}` : ''
                      rowCommandProgress.value = { ...rowCommandProgress.value, [index]: { repeat } }
                    }
                  }
                }
                if (
                  Object.prototype.hasOwnProperty.call(result, 'asr_result') ||
                  Object.prototype.hasOwnProperty.call(result, 'asr_score') ||
                  Object.prototype.hasOwnProperty.call(result, 'tts_text') ||
                  Object.prototype.hasOwnProperty.call(result, 'transcribed_text') ||
                  Object.prototype.hasOwnProperty.call(result, 'reference_text') ||
                  Object.prototype.hasOwnProperty.call(result, 'reference_path') ||
                  Object.prototype.hasOwnProperty.call(result, 'audio_path') ||
                  Object.prototype.hasOwnProperty.call(result, 'transcript_path') ||
                  Object.prototype.hasOwnProperty.call(result, 'compare_result_path')
                ) {
                  const previousMeta = rowRunMeta.value[index] || { segments: [] }
                  const segIdx = result.segment_index ?? 0
                  const totalSegs = result.total_segments ?? 1

                  // 构建段元数据
                  const segMeta = {
                    asr_result: Object.prototype.hasOwnProperty.call(result, 'asr_result') ? (result.asr_result || '') : '',
                    asr_score: Object.prototype.hasOwnProperty.call(result, 'asr_score') ? result.asr_score : null,
                    tts_text: Object.prototype.hasOwnProperty.call(result, 'tts_text') ? (result.tts_text || '') : '',
                    transcribed_text: Object.prototype.hasOwnProperty.call(result, 'transcribed_text') ? (result.transcribed_text || '') : '',
                    reference_text: Object.prototype.hasOwnProperty.call(result, 'reference_text') ? (result.reference_text || '') : '',
                    reference_path: Object.prototype.hasOwnProperty.call(result, 'reference_path') ? (result.reference_path || '') : '',
                    audio_path: Object.prototype.hasOwnProperty.call(result, 'audio_path') ? (result.audio_path || '') : '',
                    transcript_path: Object.prototype.hasOwnProperty.call(result, 'transcript_path') ? (result.transcript_path || '') : '',
                    compare_result_path: Object.prototype.hasOwnProperty.call(result, 'compare_result_path') ? (result.compare_result_path || '') : ''
                  }

                  // 更新段数组
                  const segments = [...(previousMeta.segments || [])]
                  segments[segIdx] = segMeta

                  // 顶层字段兼容：单段时直接映射，多段时用最后一段的值
                  rowRunMeta.value[index] = {
                    ...previousMeta,
                    ...segMeta,
                    segments,
                    total_segments: totalSegs
                  }
                }
              } catch (error) {
                console.error('解析执行流失败:', error)
              }
            })

            readChunk()
          }).catch((error) => {
            if (stopExecutionFlags.value[index] || abortController.signal.aborted || isAbortError(error)) {
              reportStopped()
              finishExecution()
              return
            }

            console.error('读取执行流失败:', error)
            appendExecutionLog('error', t('excelAsr.alerts.executionFailedWithDetail', { detail: error.message }), index)
            finishExecution()
          })
        }

        readChunk()
      })
      .catch((error) => {
        if (stopExecutionFlags.value[index] || abortController.signal.aborted || isAbortError(error)) {
          reportStopped()
          finishExecution()
          return
        }

        console.error('执行 ASR 用例失败:', error)
        appendExecutionLog('error', error instanceof Error ? error.message : t('excelAsr.alerts.executeFailed'), index)
        finishExecution()
      })
  })
}

const stopExecution = (index) => {
  stopExecutionFlags.value[index] = true
  abortExecution(index)
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

// 新增用例：写入占位命令 OK/1/1 使新行在列表可见，之后可用编辑弹窗填写
const addNewCase = async () => {
  if (!selectedFile.value) {
    await alert(t('excelAsr.alerts.selectFileFirst'))
    return
  }
  const title = await prompt(t('excelAsr.alerts.newCaseTitlePrompt')) || ''
  try {
    const response = await fetch('/api/excel/add_case', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: selectedFile.value, title })
    })
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.addCaseFailed')))
    }
    const data = await response.json().catch(() => ({}))
    console.log('[新增ASR用例] 已新增:', data)
    await analyzeFile({ silent: true })
  } catch (error) {
    console.error('新增用例失败:', error)
    await alert(t('excelAsr.alerts.addCaseFailed', { detail: error.message }))
  }
}

// 删除单个用例（item.idx 是 1 基列表索引，item.row.row 是 Excel 行号）
const deleteCase = async (item) => {
  if (isBatchExecuting.value || executingRows.value[item.idx]) {
    return
  }
  if (!await confirm(t('excelAsr.alerts.deleteCaseConfirm'))) {
    return
  }
  const excelRow = item.row.row
  try {
    const response = await fetch('/api/excel/delete_cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: selectedFile.value, excel_rows: [excelRow] })
    })
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.deleteCaseFailed')))
    }
    console.log('[删除ASR用例] 已删除行:', excelRow)
    selectedRows.value = selectedRows.value.filter((r) => r !== item.idx)
    await analyzeFile({ silent: true })
  } catch (error) {
    console.error('删除用例失败:', error)
    await alert(t('excelAsr.alerts.deleteCaseFailed', { detail: error.message }))
  }
}

// 批量删除选中的用例
const deleteSelectedCases = async () => {
  if (selectedRows.value.length === 0) {
    return
  }
  if (!await confirm(t('excelAsr.alerts.deleteSelectedConfirm', { count: selectedRows.value.length }))) {
    return
  }
  const validRows = excelAnalysis.value?.valid_rows || []
  const excelRows = selectedRows.value
    .map((idx) => validRows[idx - 1]?.row)
    .filter((r) => r)
  if (excelRows.length === 0) {
    return
  }
  try {
    const response = await fetch('/api/excel/delete_cases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: selectedFile.value, excel_rows: excelRows })
    })
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, t('excelAsr.alerts.deleteCaseFailed')))
    }
    console.log('[批量删除ASR] 已删除:', excelRows)
    selectedRows.value = []
    await analyzeFile({ silent: true })
  } catch (error) {
    console.error('批量删除失败:', error)
    await alert(t('excelAsr.alerts.deleteCaseFailed', { detail: error.message }))
  }
}

const executeSelectedRows = async () => {
  await executeBatchRows(selectedRows.value, t('excelAsr.selectedCasesLabel'))
}

const executeAllRows = async () => {
  await executeBatchRows(allRowIndexes.value, t('excelAsr.allCasesLabel'))
}

const executeBatchRows = async (rowIndexes, label) => {
  const orderedRows = Array.from(new Set(rowIndexes)).sort((a, b) => a - b)
  if (orderedRows.length === 0) {
    return
  }

  if (!assertAsrExecutionSlot()) {
    return
  }

  if (!beginExecution({ type: 'asr', total: orderedRows.length, label })) {
    return
  }

  latestBatchReport.value = null
  isBatchExecuting.value = true
  appendExecutionLog('info', t('excelAsr.alerts.batchStart', { label, count: orderedRows.length }))

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
    finishExecutionStore({ completed: completedAll })
    if (completedAll) {
      appendExecutionLog('success', t('excelAsr.alerts.batchComplete', { label, count: orderedRows.length }))
      await createAsrBatchReport(orderedRows, label)
    }
  }
}

const stopAllExecution = () => {
  isBatchExecuting.value = false
  for (const rowIndex in executingRows.value) {
    if (executingRows.value[rowIndex]) {
      stopExecutionFlags.value[rowIndex] = true
      abortExecution(rowIndex)
    }
  }
  appendExecutionLog('info', t('excelAsr.alerts.allStopped'))
}

const executionStatusLabel = (statusKey) => {
  if (statusKey === 'success') {
    return t('common.success')
  }
  if (statusKey === 'error') {
    return t('common.error')
  }
  return t('common.info')
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

watch(currentPage, (newPage) => {
  jumpPage.value = newPage
})

watch(totalPages, (nextTotalPages) => {
  if (currentPage.value > nextTotalPages) {
    currentPage.value = nextTotalPages
  }
})

watch(selectedFile, (nextFile, previousFile) => {
  if (!nextFile) {
    fileSelectorPanelExpanded.value = false
    modelSelectorPanelExpanded.value = false
    return
  }

  if (activeModelName.value && nextFile !== previousFile) {
    fileSelectorPanelExpanded.value = false
    modelSelectorPanelExpanded.value = false
  }
})

watch(activeModelName, (nextModel, previousModel) => {
  if (!nextModel) {
    modelSelectorPanelExpanded.value = false
    return
  }

  if (selectedFile.value && nextModel !== previousModel) {
    modelSelectorPanelExpanded.value = false
    if (hasAnalyzedCurrentFile.value) {
      fileSelectorPanelExpanded.value = false
    }
  }
})

const ASR_STATE_KEY = 'checkpilot.asrExecution.state'

const restoreAsrState = () => {
  try {
    const saved = localStorage.getItem(ASR_STATE_KEY)
    if (!saved) return
    const state = JSON.parse(saved)
    if (state.executionMode) executionMode.value = state.executionMode
    if (typeof state.enableRecording === 'boolean') enableRecording.value = state.enableRecording
    if (typeof state.enableVerification === 'boolean') enableVerification.value = state.enableVerification
    if (typeof state.matchThreshold === 'number') matchThreshold.value = state.matchThreshold
  } catch {}
}

const persistAsrState = () => {
  try {
    localStorage.setItem(ASR_STATE_KEY, JSON.stringify({
      executionMode: executionMode.value,
      enableRecording: enableRecording.value,
      enableVerification: enableVerification.value,
      matchThreshold: matchThreshold.value,
    }))
  } catch {}
}

watch([executionMode, enableRecording, enableVerification, matchThreshold], persistAsrState, { deep: true })

onMounted(async () => {
  restoreAsrState()
  await loadCurrentDevice()
  await Promise.all([loadStatus(), loadExcelFiles(), loadAudioDevices(), loadAudioConfig()])
  loadColorVerifyConfig()
  // 注册全局“停止执行”回调，供右上角进度卡片按钮调用
  registerStopHandler('asr', stopAllExecution)
})

onUnmounted(() => {
  // 注意：不再在卸载时 abort 执行——组件被 keep-alive 缓存，离开页面时执行需继续。
  isBatchExecuting.value = false
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
  padding: 18px 20px;
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.excel-execution-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.9) rgba(226, 232, 240, 0.72);
}

.excel-file-panel,
.excel-section-card,
.excel-table-shell,
.excel-note-card {
  margin-bottom: 16px;
}

.excel-top-grid {
  display: grid;
  gap: 16px;
  align-items: stretch;
}

.excel-top-grid > * {
  height: 100%;
}

.excel-top-compact-card {
  padding: 14px 16px;
}

.excel-top-compact-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.excel-top-compact-title {
  margin: 6px 0 0;
  color: #111827;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.35;
  word-break: break-all;
}

.excel-top-compact-meta {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 0.82rem;
  line-height: 1.5;
}

.excel-file-item {
  padding: 0.75rem 0.875rem;
}

.excel-file-list {
  max-height: 240px;
  overflow-y: auto;
  padding-right: 4px;
}

.excel-section-card {
  padding: 16px;
  border-radius: 22px;
}

.excel-top-model-panel {
  min-height: 100%;
}

.excel-step-chip {
  padding: 0.45rem 0.7rem;
  border-radius: 14px;
  line-height: 1.35;
}

.excel-row-actions {
  gap: 0.5rem;
}

.excel-results-table th,
.excel-results-table td {
  padding: 0.65rem 0.75rem;
}

.excel-results-table .excel-row-actions .btn {
  min-width: 78px;
}

.excel-execution-page .btn {
  padding: 0.5rem 0.8rem;
  font-size: 0.875rem;
  line-height: 1.2;
}

.excel-execution-page .btn.btn-sm,
.excel-execution-page .btn-sm {
  padding: 0.375rem 0.7rem;
  font-size: 0.8125rem;
}

.excel-execution-page .form-input,
.excel-execution-page .form-select {
  min-height: 2.25rem;
  padding: 0.45rem 0.65rem;
  font-size: 0.875rem;
}

.excel-execution-page .form-label {
  margin-bottom: 0.25rem;
  font-size: 0.8125rem;
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

@media (max-width: 768px) {
  .excel-execution-page {
    padding: 14px;
  }

  .excel-section-card {
    padding: 14px;
    border-radius: 18px;
  }

  .excel-results-table th,
  .excel-results-table td {
    padding: 0.55rem 0.6rem;
  }
}

@media (min-width: 1280px) {
  .excel-top-grid {
    grid-template-columns: minmax(0, 1.02fr) minmax(0, 0.98fr);
  }
}

/* 指令动效（与图片执行一致） */
.excel-step-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.excel-step-sequence-collapsed {
  position: relative;
  display: flex;
  max-width: 100%;
  flex-wrap: nowrap;
  gap: 0.5rem;
  overflow: hidden;
  padding-right: 2.5rem;
}

.excel-step-sequence-collapsed::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 2.75rem;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.98) 68%);
  pointer-events: none;
}

.excel-step-sequence-collapsed .excel-step-command {
  flex-shrink: 0;
}

.excel-step-command {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.7rem;
  border: 1px solid rgba(226, 232, 240, 0.92);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.96);
  color: #475569;
  line-height: 1.35;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.92);
  transition: transform 0.18s ease, border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease, color 0.18s ease;
}

.excel-step-command-key {
  font-weight: 600;
  color: #0f172a;
}

.excel-step-command-meta {
  font-size: 0.72rem;
  color: #64748b;
  white-space: nowrap;
}

.excel-step-command-progress {
  border-radius: 999px;
  background: rgba(191, 219, 254, 0.95);
  padding: 0.15rem 0.45rem;
  font-size: 0.68rem;
  font-weight: 700;
  line-height: 1.1;
  color: #1d4ed8;
}

.excel-step-command-active {
  border-color: rgba(59, 130, 246, 0.34);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.18), rgba(14, 165, 233, 0.1));
  color: #0f172a;
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.08), 0 10px 24px rgba(59, 130, 246, 0.16);
  animation: excel-step-command-pulse 1.2s ease-in-out infinite;
}

.excel-step-command-active .excel-step-command-key {
  color: #1d4ed8;
}

.excel-step-command-active .excel-step-command-meta {
  color: #1e40af;
}

.excel-step-command-active .excel-step-command-progress {
  background: #2563eb;
  color: #fff;
}

@keyframes excel-step-command-pulse {
  0% {
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.08), 0 10px 24px rgba(59, 130, 246, 0.12);
  }
  50% {
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.16), 0 14px 30px rgba(59, 130, 246, 0.2);
  }
  100% {
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.08), 0 10px 24px rgba(59, 130, 246, 0.12);
  }
}
</style>