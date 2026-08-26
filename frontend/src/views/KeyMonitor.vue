<template>
  <div class="card w-full key-monitor-page">
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <router-link to="/" class="btn btn-secondary btn-sm">
        {{ $t('common.chooseFeature') }}
      </router-link>
      <h2 class="mb-0">{{ $t('keyMonitor.title') }}</h2>
    </div>

    <div class="key-monitor-scroll key-monitor-scroll--split">
      <div v-if="!selectedDevice && devicePreviewSource !== DEVICE_PREVIEW_SOURCE_CAPTURE_CARD" class="bg-yellow-50 p-4 rounded-lg mb-6">
        <p class="text-warning mb-2">{{ $t('common.deviceRequired') }}</p>
        <router-link :to="{ path: '/', query: { panel: 'device-hub' } }" class="btn btn-primary">
          {{ $t('common.goDeviceManagement') }}
        </router-link>
      </div>
      <div class="key-monitor-layout">
        <div class="key-monitor-main w-full">
        <div class="rounded-xl border border-slate-200 bg-white p-5">

          <div v-if="tmsError" class="text-sm text-danger mb-3">{{ tmsError }}</div>
          <div v-else-if="!tmsLoadingProjects && tmsProjects.length === 0" class="text-sm text-gray-500 mb-3">
            {{ $t('keyMonitor.remoteProjectsEmpty') }}
          </div>

          <div class="grid gap-4 lg:grid-cols-2 lg:items-stretch">
            <div>
              <div class="grid gap-3 sm:grid-cols-2">
                <label class="grid gap-1 min-w-0">
                  <span class="text-sm font-medium text-gray-700">{{ $t('keyMonitor.remoteProject') }}</span>
                  <CustomSelect
                    v-model="selectedTmsProjectId"
                    :options="tmsProjectOptions"
                    :disabled="tmsLoadingProjects || tmsLoadingModules || tmsLoadingTestcases"
                    :placeholder="$t('keyMonitor.selectRemoteProject')"
                    @change="handleTmsProjectChange"
                  />
                </label>

                <label class="grid gap-1 min-w-0">
                  <span class="text-sm font-medium text-gray-700">{{ $t('keyMonitor.remoteModule') }}</span>
                  <CustomSelect
                    v-model="selectedTmsModuleValue"
                    :options="tmsModuleOptions"
                    :disabled="!selectedTmsProjectId || tmsLoadingModules || tmsLoadingTestcases"
                    :placeholder="$t('keyMonitor.selectRemoteModule')"
                    @change="handleTmsModuleChange"
                  />
                </label>

                <label class="grid gap-1 min-w-0">
                  <span class="text-sm font-medium text-gray-700">{{ $t('keyMonitor.remoteCaseSize') }}</span>
                  <CustomSelect
                    v-model="tmsPageSize"
                    :options="tmsPageSizeOptions"
                    @change="handleTmsPageSizeChange"
                  />
                </label>

                <label class="grid gap-1 min-w-0">
                  <span class="text-sm font-medium text-gray-700">{{ $t('keyMonitor.remoteCaseNumber') }}</span>
                  <CustomSelect
                    v-model="selectedTmsCaseNumber"
                    :options="tmsCaseNumberOptions"
                    :disabled="tmsLoadingTestcases || paginatedFilteredTmsCaseNumbers.length === 0"
                    :placeholder="$t('keyMonitor.selectRemoteCaseNumber')"
                  />
                  <span
                    v-if="tmsCaseNumberSubmittedKeyword && filteredTmsCaseNumbers.length === 0 && filteredTmsModules.length === 0"
                    class="text-xs text-rose-600"
                  >
                    {{ $t('keyMonitor.searchRemoteCaseNumberNoMatch') }}
                  </span>
                  <span
                    v-else-if="tmsCaseNumberSubmittedKeyword && filteredTmsCaseNumbers.length > 0"
                    class="text-xs text-emerald-600"
                  >
                    {{ $t('keyMonitor.searchResultsTotal', { total: filteredTmsCaseNumbers.length }) }}
                  </span>
                </label>
              </div>

              <div class="mt-3 grid gap-3 sm:grid-cols-2">
                <label class="grid gap-1 min-w-0">
                  <span class="text-sm font-medium text-gray-700">{{ $t('keyMonitor.manualCaseNumber') }}</span>
                  <input
                    v-model="manualCaseNumber"
                    type="text"
                    class="form-input text-sm"
                    :placeholder="$t('keyMonitor.manualCaseNumberPlaceholder')"
                    :disabled="!!selectedTmsCaseNumber"
                  >
                  <span v-if="selectedTmsCaseNumber" class="text-xs text-slate-400">
                    {{ $t('keyMonitor.manualCaseNumberDisabledHint') }}
                  </span>
                </label>
              </div>

              <div v-if="tmsCaseNumbers.length > 0" class="mt-3 text-sm text-gray-500">
                {{ $t('keyMonitor.remoteCasesCount', { count: tmsCaseNumbers.length, total: tmsTotal }) }}
              </div>

              <div class="mt-3 flex items-center gap-2">
                <input
                  v-model="tmsCaseNumberSearch"
                  type="search"
                  class="form-input text-sm flex-1"
                  :placeholder="$t('keyMonitor.searchRemoteCaseNumber')"
                  :disabled="tmsLoadingTestcases || tmsAllLoading || !selectedTmsProjectId"
                  @keydown.enter.prevent="submitTmsSearch"
                >
                <button
                  type="button"
                  class="btn btn-primary btn-sm"
                  @click="submitTmsSearch"
                  :disabled="tmsLoadingTestcases || tmsAllLoading || !selectedTmsProjectId"
                >
                  {{ tmsAllLoading ? $t('keyMonitor.searchingAllTestcases') : $t('common.searchAction') }}
                </button>
                <button
                  v-if="tmsCaseNumberSearch || tmsCaseNumberSubmittedKeyword"
                  type="button"
                  class="btn btn-secondary btn-sm"
                  @click="clearTmsSearchKeyword"
                  :title="$t('common.clear')"
                >
                  ×
                </button>
              </div>

              <div v-if="tmsTotalPages > 1" class="mt-3 flex flex-wrap items-center gap-2">
                <button
                  class="btn btn-secondary btn-sm"
                  :disabled="tmsCurrentPage <= 1 || tmsLoadingTestcases"
                  @click="goTmsPage(tmsCurrentPage - 1)"
                >
                  {{ $t('common.previousPage') }}
                </button>
                <span class="text-sm text-slate-600">
                  {{ tmsCurrentPage }} / {{ tmsTotalPages }}
                </span>
                <button
                  class="btn btn-secondary btn-sm"
                  :disabled="tmsCurrentPage >= tmsTotalPages || tmsLoadingTestcases"
                  @click="goTmsPage(tmsCurrentPage + 1)"
                >
                  {{ $t('common.nextPage') }}
                </button>
                <span class="text-xs text-slate-400">{{ $t('common.goTo') }}</span>
                <input
                  type="number"
                  :value="tmsCurrentPage"
                  class="form-input w-16 text-center text-sm"
                  :min="1"
                  :max="tmsTotalPages"
                  @keydown.enter="jumpTmsPage($event)"
                >
              </div>

            </div>

            <div class="rounded-lg border border-slate-200 bg-white p-3 h-full lg:overflow-y-auto">
              <div class="flex items-center justify-between gap-2 mb-2">
                <h4 class="text-sm font-semibold text-slate-900">
                  {{ $t('keyMonitor.testcaseDetailTitle') }}
                </h4>
                <span v-if="selectedTmsCaseNumber" class="text-xs text-slate-500 font-mono">
                  {{ selectedTmsCaseNumber }}
                </span>
                <span v-else-if="manualCaseNumber.trim()" class="text-xs text-amber-600 font-mono">
                  {{ manualCaseNumber.trim() }}
                </span>
              </div>

              <div v-if="!selectedTmsCaseNumber && !manualCaseNumber.trim()" class="text-xs text-gray-500">
                {{ $t('keyMonitor.testcaseDetailEmpty') }}
              </div>
              <div v-else-if="!selectedTestcaseDetail" class="text-xs text-gray-500">
                {{ $t('keyMonitor.testcaseDetailMissing') }}
              </div>
              <div v-else class="space-y-3">
                <div>
                  <div class="text-xs font-medium uppercase tracking-[0.14em] text-slate-500 mb-1">
                    {{ $t('keyMonitor.testcasePrecondition') }}
                  </div>
                  <p v-if="selectedTestcaseDetail.precondition" class="text-sm text-slate-700 whitespace-pre-wrap">
                    {{ selectedTestcaseDetail.precondition }}
                  </p>
                  <p v-else class="text-xs text-slate-400">{{ $t('keyMonitor.testcasePreconditionEmpty') }}</p>
                </div>

                <div class="space-y-4">
                  <div v-if="filteredTestcaseSteps.length > 0">
                    <div class="text-xs font-medium uppercase tracking-[0.14em] text-slate-500 mb-2">
                      {{ $t('keyMonitor.testcaseStepStep') }}
                    </div>
                    <ol class="space-y-1.5">
                      <li
                        v-for="(item, idx) in filteredTestcaseSteps"
                        :key="'step-' + idx"
                        class="flex gap-2 text-sm"
                      >
                        <span class="text-slate-400 font-mono shrink-0">{{ String(item.index).padStart(2, '0') }}.</span>
                        <span class="text-slate-700 whitespace-pre-wrap">{{ item.step }}</span>
                      </li>
                    </ol>
                  </div>
                  <div v-if="filteredTestcaseExpected.length > 0">
                    <div class="text-xs font-medium uppercase tracking-[0.14em] text-emerald-600 mb-2">
                      {{ $t('keyMonitor.testcaseStepExpected') }}
                    </div>
                    <ol class="space-y-1.5">
                      <li
                        v-for="(item, idx) in filteredTestcaseExpected"
                        :key="'exp-' + idx"
                        class="flex gap-2 text-sm"
                      >
                        <span class="text-slate-400 font-mono shrink-0">{{ String(item.index).padStart(2, '0') }}.</span>
                        <span class="text-slate-700 whitespace-pre-wrap">{{ item.expected }}</span>
                      </li>
                    </ol>
                  </div>
                  <p v-if="filteredTestcaseSteps.length === 0 && filteredTestcaseExpected.length === 0" class="text-xs text-slate-400">
                    {{ $t('keyMonitor.testcaseStepsEmpty') }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

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
            v-if="!keyMonitorActive && !isStarting"
            @click="startKeyMonitor"
            class="btn btn-secondary"
            :disabled="excelSavingSequence"
          >
            {{ $t('keyMonitor.start') }}
          </button>
          <button
            v-else
            @click="stopKeyMonitor"
            class="btn btn-danger"
            :disabled="excelSavingSequence"
          >
            {{ $t('keyMonitor.stop') }}
          </button>
          <button 
            @click="copySequence"
            class="btn btn-primary"
            :disabled="!workingSequence || keyMonitorActive || isStarting || excelSavingSequence"
            :title="$t('keyMonitor.copyTitle')"
          >
            {{ $t('keyMonitor.copySequence') }}
          </button>
          <button
            class="btn btn-secondary"
            @click="loadTmsProjects"
            :disabled="tmsLoadingProjects || tmsLoadingModules || tmsLoadingTestcases"
          >
            {{ tmsLoadingProjects ? $t('keyMonitor.refreshRemoteProjectsLoading') : $t('keyMonitor.refreshRemoteProjects') }}
          </button>
          <button
            class="btn btn-secondary"
            @click="loadExcelFiles"
            :disabled="excelLoadingFiles || excelUploading"
          >
            {{ excelLoadingFiles ? $t('keyMonitor.refreshExcelFilesLoading') : $t('keyMonitor.refreshExcelFiles') }}
          </button>
          <button
            type="button"
            class="btn btn-secondary cursor-pointer"
            :class="{ 'opacity-60 pointer-events-none': excelUploading }"
            :disabled="excelUploading"
            @click="handleUploadExcelClick"
          >
            {{ excelUploading ? $t('keyMonitor.uploadExcelLoading') : $t('keyMonitor.uploadExcel') }}
          </button>
        </div>
        <div class="key-monitor-main-body">
          <div class="key-monitor-main-content">
            <div class="rounded-xl border border-slate-200 bg-white p-5">
              <div class="grid gap-3">
                <CustomSelect
                  v-model="selectedExcelFile"
                  :options="excelFileOptions"
                  :disabled="excelLoadingFiles || excelUploading"
                  :placeholder="$t('keyMonitor.selectExcel')"
                  @change="handleExcelFileChange"
                />
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  class="btn btn-secondary btn-sm"
                  @click="saveSequenceToExcel"
                  :disabled="!selectedExcelFile || !workingSequence || excelLoadingRows || excelUploading || excelSavingSequence"
                >
                  {{ excelSavingSequence ? $t('keyMonitor.writingBack') : $t('keyMonitor.writeBack') }}
                </button>
                <label class="key-monitor-tts-switch" :title="$t('keyMonitor.ttsModeHint')">
                  <input v-model="ttsModeEnabled" type="checkbox" class="sr-only">
                  <span
                    class="key-monitor-tts-switch__track"
                    :class="{ 'key-monitor-tts-switch__track--active': ttsModeEnabled }"
                    aria-hidden="true"
                  >
                    <span
                      class="key-monitor-tts-switch__thumb"
                      :class="{ 'key-monitor-tts-switch__thumb--active': ttsModeEnabled }"
                    ></span>
                  </span>
                  <span class="text-sm text-slate-600">{{ $t('keyMonitor.ttsMode') }}</span>
                </label>
                <label class="key-monitor-tts-switch" :title="$t('keyMonitor.assertModeHint')">
                  <input v-model="assertModeEnabled" type="checkbox" class="sr-only">
                  <span
                    class="key-monitor-tts-switch__track"
                    :class="{ 'key-monitor-tts-switch__track--active': assertModeEnabled }"
                    aria-hidden="true"
                  >
                    <span
                      class="key-monitor-tts-switch__thumb"
                      :class="{ 'key-monitor-tts-switch__thumb--active': assertModeEnabled }"
                    ></span>
                  </span>
                  <span class="text-sm text-slate-600">{{ $t('keyMonitor.assertMode') }}</span>
                </label>
              </div>
              <div v-if="selectedExcelFile && !excelLoadingRows && excelRows.length === 0" class="mt-2 text-sm text-gray-500">
                {{ $t('keyMonitor.noParsedRows') }}
              </div>
              <div v-if="excelImportError" class="text-sm text-danger mt-2">
                {{ excelImportError }}
              </div>
              <div v-else-if="excelImportMessage" class="text-sm text-green-600 mt-2">
                {{ excelImportMessage }}
              </div>
            </div>
            <div v-if="keyMonitorActive || isStarting" class="border rounded p-3 bg-gray-50 min-h-[120px] font-mono text-sm whitespace-pre-wrap break-all w-full overflow-auto">
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
                <span class="text-gray-400">{{ $t('keyMonitor.monitorPlaceholder') }}</span>
              </template>
            </div>
            <textarea
              v-else
              v-model="editableSequence"
              @input="handleEditableSequenceInput"
              class="form-input min-h-[120px] font-mono text-sm w-full"
              :placeholder="$t('keyMonitor.editPlaceholder')"
            ></textarea>
            <div class="text-sm text-gray-500 mt-2" v-if="keyMonitorActive && !keyMonitorSequence">
              {{ $t('keyMonitor.monitoring') }}
            </div>
            <div class="text-sm text-danger mt-2" v-if="keyMonitorError">
              {{ keyMonitorError }}
            </div>

            <!-- 待写入列表模块 -->
            <div v-if="selectedExcelFile && pendingWriteList.length > 0" class="mt-4 border border-slate-200 rounded-lg overflow-hidden">
              <div class="bg-slate-50 px-3 py-2 flex items-center justify-between">
                <div class="text-sm font-semibold text-slate-700">
                  {{ $t('keyMonitor.pendingWrite.title') }}
                  <span class="text-xs font-normal text-slate-500 ml-1">({{ pendingWriteList.length }})</span>
                </div>
                <button
                  class="btn btn-primary btn-sm"
                  :disabled="pendingWriteLoading"
                  @click="flushPendingWriteList"
                >
                  {{ pendingWriteLoading ? $t('keyMonitor.pendingWrite.writing') : $t('keyMonitor.pendingWrite.flush') }}
                </button>
              </div>
              <div class="max-h-[300px] overflow-y-auto">
                <table class="w-full text-sm pending-write-table">
                  <thead class="bg-slate-100 sticky top-0">
                    <tr>
                      <th class="px-3 py-2 text-left font-medium text-slate-600">#</th>
                      <th class="px-3 py-2 text-left font-medium text-slate-600">testID</th>
                      <th class="px-3 py-2 text-left font-medium text-slate-600">preScript</th>
                      <th class="px-3 py-2 text-left font-medium text-slate-600">checkPic</th>
                      <th class="px-3 py-2 text-left font-medium text-slate-600">checkPoint</th>
                      <th class="px-3 py-2 text-center font-medium text-slate-600">{{ $t('keyMonitor.pendingWrite.action') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(item, index) in pendingWriteList" :key="index" class="border-t border-slate-100 hover:bg-slate-50">
                      <td class="px-3 py-2 text-slate-500">{{ index + 1 }}</td>
                      <td class="px-3 py-2">
                        <textarea
                          v-model="item.testID"
                          rows="1"
                          class="w-full bg-transparent border-0 border-b border-transparent hover:border-slate-300 focus:border-blue-500 outline-none font-mono text-xs py-0.5 px-0 resize-none overflow-hidden"
                          @blur="onPendingItemEdit(index, 'testID', $event.target.value)"
                          @input="autoResizeTextarea($event)"
                          :ref="el => { if (el) autoResizeTextarea({ target: el }) }"
                        ></textarea>
                      </td>
                      <td class="px-3 py-2">
                        <textarea
                          v-model="item.preScript"
                          rows="1"
                          class="w-full bg-transparent border-0 border-b border-transparent hover:border-slate-300 focus:border-blue-500 outline-none font-mono text-xs py-0.5 px-0 resize-none overflow-hidden"
                          @blur="onPendingItemEdit(index, 'preScript', $event.target.value)"
                          @input="autoResizeTextarea($event)"
                          :ref="el => { if (el) autoResizeTextarea({ target: el }) }"
                        ></textarea>
                      </td>
                      <td class="px-3 py-2">
                        <textarea
                          v-model="item.checkPic"
                          rows="1"
                          class="w-full bg-transparent border-0 border-b border-transparent hover:border-slate-300 focus:border-blue-500 outline-none font-mono text-xs py-0.5 px-0 resize-none overflow-hidden"
                          @blur="onPendingItemEdit(index, 'checkPic', $event.target.value)"
                          @input="autoResizeTextarea($event)"
                          :ref="el => { if (el) autoResizeTextarea({ target: el }) }"
                        ></textarea>
                      </td>
                      <td class="px-3 py-2">
                        <textarea
                          v-model="item.checkPoint"
                          rows="1"
                          class="w-full bg-transparent border-0 border-b border-transparent hover:border-slate-300 focus:border-blue-500 outline-none font-mono text-xs py-0.5 px-0 resize-none overflow-hidden"
                          @blur="onPendingItemEdit(index, 'checkPoint', $event.target.value)"
                          @input="autoResizeTextarea($event)"
                          :ref="el => { if (el) autoResizeTextarea({ target: el }) }"
                        ></textarea>
                      </td>
                      <td class="px-3 py-2 text-center">
                        <button
                          class="text-rose-500 hover:text-rose-700 text-xs"
                          @click="removePendingWriteItem(index)"
                        >
                          {{ $t('keyMonitor.pendingWrite.remove') }}
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
        </div>

        <aside class="key-monitor-aside">
          <div class="rounded-xl border border-slate-200 bg-white p-5">
          <div class="device-preview-panel device-preview-panel--fill">
              <div class="flex flex-wrap items-start justify-between gap-3 mb-4">
                <div>
                  <div class="text-sm font-semibold text-slate-900">{{ $t('keyMonitor.devicePreviewTitle') }}</div>
                  <div class="text-xs text-slate-500">{{ devicePreviewIdentityLabel }}</div>
                </div>
                <div class="flex flex-wrap gap-2">
                  <button
                    class="btn btn-secondary btn-sm"
                    @click="handleDevicePreviewRefresh"
                    :disabled="devicePreviewLoading"
                  >
                    {{ devicePreviewLoading ? $t('keyMonitor.devicePreviewRefreshing') : $t('keyMonitor.refreshDevicePreview') }}
                  </button>
                  <button
                    v-if="devicePreviewSelectionActive || devicePreviewSelectionCrop"
                    class="btn btn-secondary btn-sm"
                    @click="clearDevicePreviewSelection"
                  >
                    {{ $t('keyMonitor.cancelDevicePreviewSelection') }}
                  </button>
                  <button
                    class="btn btn-primary btn-sm"
                    @click="enqueueSelectedDevicePreview"
                    :disabled="!devicePreviewSelectionCrop || screenshotQueueSubmitting"
                  >
                    {{ $t('keyMonitor.enqueueDevicePreviewSelection') }}
                  </button>
                </div>
              </div>

              <div
                v-if="pendingScreenshotQueue.length > 0"
                class="mb-3 rounded-lg border border-blue-200 bg-blue-50 p-3"
              >
                <div class="flex items-center justify-between mb-2 gap-2 flex-wrap">
                  <span class="text-sm font-medium text-blue-700">
                    {{ $t('keyMonitor.screenshotQueueTitle', { count: pendingScreenshotQueue.length }) }}
                  </span>
                  <div class="flex gap-2">
                    <button
                      class="btn btn-secondary btn-sm"
                      :disabled="screenshotQueueSubmitting"
                      @click="clearScreenshotQueue"
                    >
                      {{ $t('keyMonitor.clearScreenshotQueue') }}
                    </button>
                    <button
                      class="btn btn-primary btn-sm"
                      :disabled="screenshotQueueSubmitting"
                      @click="submitScreenshotQueue"
                    >
                      {{ screenshotQueueSubmitting
                        ? $t('keyMonitor.submittingScreenshotQueue')
                        : $t('keyMonitor.submitScreenshotQueue') }}
                    </button>
                  </div>
                </div>
                <div class="flex gap-2 overflow-x-auto pb-1">
                  <div
                    v-for="(queueItem, queueIdx) in pendingScreenshotQueue"
                    :key="queueItem.id"
                    class="flex-shrink-0 w-32 rounded border border-slate-200 bg-white p-1 flex flex-col"
                  >
                    <img
                      :src="queueItem.thumbnail"
                      class="w-full h-20 object-cover rounded bg-slate-100"
                      :alt="queueItem.fileName"
                    >
                    <div class="text-[11px] text-slate-700 mt-1 truncate" :title="queueItem.fileName">
                      {{ queueItem.fileName }}
                    </div>
                    <div class="flex items-center justify-between mt-1 gap-1">
                      <button
                        type="button"
                        class="text-blue-600 disabled:text-slate-300 text-base leading-none"
                        :disabled="queueIdx === 0 || screenshotQueueSubmitting"
                        :title="$t('keyMonitor.moveScreenshotQueueUp')"
                        @click="moveScreenshotQueueItem(queueItem.id, -1)"
                      >
                        ←
                      </button>
                      <button
                        type="button"
                        class="text-rose-600 disabled:text-slate-300 text-sm"
                        :disabled="screenshotQueueSubmitting"
                        :title="$t('keyMonitor.removeScreenshotQueueItem')"
                        @click="removeScreenshotQueueItem(queueItem.id)"
                      >
                        ×
                      </button>
                      <button
                        type="button"
                        class="text-blue-600 disabled:text-slate-300 text-base leading-none"
                        :disabled="queueIdx === pendingScreenshotQueue.length - 1 || screenshotQueueSubmitting"
                        :title="$t('keyMonitor.moveScreenshotQueueDown')"
                        @click="moveScreenshotQueueItem(queueItem.id, 1)"
                      >
                        →
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div class="mb-3 flex flex-wrap gap-3 items-start">
                <label class="grid gap-1 min-w-[180px] flex-1 max-w-xs">
                  <span class="text-xs font-medium text-slate-600">{{ $t('keyMonitor.devicePreviewSourceLabel') }}</span>
                  <CustomSelect
                    v-model="devicePreviewSource"
                    :options="devicePreviewSourceOptions"
                  />
                </label>

                <template v-if="devicePreviewUsesCaptureCard">
                  <label class="grid gap-1 min-w-[200px] flex-1 max-w-sm">
                    <span class="text-xs font-medium text-slate-600">{{ $t('keyMonitor.captureCardDeviceLabel') }}</span>
                    <div class="flex gap-2">
                      <CustomSelect
                        :modelValue="captureCardActiveDeviceId"
                        :options="captureCardDeviceOptions"
                        :disabled="captureCardListLoading || captureCardSwitching"
                        class="flex-1 min-w-0"
                        @change="onCaptureCardDeviceSelectChange"
                      />
                      <button
                        type="button"
                        class="btn btn-secondary btn-sm whitespace-nowrap"
                        :disabled="captureCardListLoading || captureCardSwitching"
                        @click="loadCaptureCardDevices"
                      >
                        {{ captureCardListLoading ? $t('keyMonitor.captureCardScanning') : $t('keyMonitor.captureCardRescan') }}
                      </button>
                      <button
                        type="button"
                        class="btn btn-secondary btn-sm whitespace-nowrap"
                        :disabled="captureCardReleasing"
                        @click="releaseCaptureCard"
                      >
                        {{ captureCardReleasing ? $t('keyMonitor.captureCardReleasing') : $t('keyMonitor.captureCardRelease') }}
                      </button>
                    </div>
                    <span v-if="captureCardError" class="text-[11px] text-rose-600">{{ captureCardError }}</span>
                  </label>
                </template>
              </div>

              <div
                ref="devicePreviewFrameRef"
                class="device-preview-frame"
                :class="{
                  'device-preview-frame--selectable': devicePreviewUrl,
                  'device-preview-frame--selecting': devicePreviewSelectionActive,
                }"
                @pointerenter="handleDevicePreviewPointerEnter"
                @pointerleave="handleDevicePreviewPointerLeave"
                @pointerdown="beginDevicePreviewSelection"
                @pointermove="updateDevicePreviewSelection"
                @pointerup="finishDevicePreviewSelection"
                @pointercancel="finishDevicePreviewSelection"
              >
                <template v-if="devicePreviewUrl">
                  <img
                    ref="devicePreviewImageRef"
                    :src="devicePreviewUrl"
                    :alt="$t('keyMonitor.devicePreviewTitle')"
                    class="device-preview-image"
                    draggable="false"
                    @load="handleDevicePreviewImageLoad"
                    @error="handleDevicePreviewImageError"
                  >
                  <div v-if="devicePreviewSelectionRect" class="device-preview-selection-layer">
                    <div
                      class="device-preview-selection-box"
                      :style="devicePreviewSelectionStyle"
                    ></div>
                  </div>
                </template>
                <div v-else class="device-preview-state">
                  <span v-if="devicePreviewLoading">{{ $t('keyMonitor.devicePreviewLoading') }}</span>
                  <span v-else-if="devicePreviewError">{{ devicePreviewError }}</span>
                  <span v-else>{{ $t('keyMonitor.devicePreviewEmpty') }}</span>
                </div>
              </div>

              <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                <span>{{ devicePreviewFooterText }}</span>
                <span v-if="devicePreviewCapturedLabel">{{ $t('keyMonitor.devicePreviewCapturedAt', { time: devicePreviewCapturedLabel }) }}</span>
              </div>

              <label class="mt-3 grid gap-1">
                <span class="text-xs font-medium text-slate-600">{{ $t('keyMonitor.devicePreviewSaveDirLabel') }}</span>
                <input
                  v-model="devicePreviewSaveDir"
                  type="text"
                  class="form-input text-sm"
                  :placeholder="$t('keyMonitor.devicePreviewSaveDirPlaceholder')"
                >
              </label>

              <div v-if="devicePreviewSaveMessage" class="mt-2 text-xs text-green-600">
                {{ devicePreviewSaveMessage }}
              </div>

              <div v-if="devicePreviewError && devicePreviewUrl" class="mt-2 text-xs text-danger">
                {{ devicePreviewError }}
              </div>
          </div>
          </div>

          <!-- 纠错规则方案模块 -->
          <div v-if="!keyMonitorActive && !isStarting" class="mt-4 rounded-xl border border-slate-200 bg-white">
            <div
              class="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50 transition-colors"
              @click="schemePanelExpanded = !schemePanelExpanded"
            >
              <div class="text-sm font-semibold text-slate-700">
                {{ $t('keyMonitor.schemes.label') }}
                <span v-if="activeMappingSchemeName" class="text-xs font-normal text-slate-500 ml-2">
                  ({{ activeMappingSchemeName }})
                </span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs text-slate-500">
                  {{ schemePanelExpanded ? $t('keyMonitor.schemes.collapse') : $t('keyMonitor.schemes.expand') }}
                </span>
                <span class="text-lg text-slate-400 transition-transform" :class="{ 'rotate-180': schemePanelExpanded }">
                  ▼
                </span>
              </div>
            </div>

            <div v-if="schemePanelExpanded" class="px-4 pb-4 border-t border-slate-200">
              <div class="key-monitor-scheme-bar mt-3">
                <div class="key-monitor-scheme-tabs-wrap">
                  <div class="key-monitor-scheme-tabs">
                    <button
                      v-for="scheme in mappingSchemesList"
                      :key="scheme.name"
                      type="button"
                      class="key-monitor-scheme-tab"
                      :class="{ 'key-monitor-scheme-tab-active': scheme.is_active }"
                      :disabled="schemeBusy"
                      :title="$t('keyMonitor.schemes.tabTitle', { count: scheme.mapping_count })"
                      @click="activateMappingScheme(scheme.name)"
                    >
                      <span>{{ scheme.name }}</span>
                      <span v-if="scheme.is_active" class="key-monitor-scheme-active-badge">
                        {{ $t('keyMonitor.schemes.activeBadge') }}
                      </span>
                      <span v-else class="key-monitor-scheme-count">{{ scheme.mapping_count }}</span>
                    </button>
                  </div>
                </div>
                <div class="key-monitor-scheme-actions">
                  <button class="btn btn-secondary btn-sm" :disabled="schemeBusy" @click="openCreateSchemeModal">
                    {{ $t('keyMonitor.schemes.create') }}
                  </button>
                  <button
                    class="btn btn-secondary btn-sm"
                    :disabled="schemeBusy || !activeMappingSchemeName"
                    @click="openRenameSchemeModal"
                  >
                    {{ $t('keyMonitor.schemes.rename') }}
                  </button>
                  <button
                    class="btn btn-secondary btn-sm"
                    :disabled="schemeBusy || !activeMappingSchemeName"
                    @click="openDuplicateSchemeModal"
                  >
                    {{ $t('keyMonitor.schemes.duplicate') }}
                  </button>
                  <button
                    class="btn btn-secondary btn-sm"
                    :disabled="schemeBusy || !activeMappingSchemeName"
                    @click="exportActiveScheme"
                    :title="$t('keyMonitor.schemes.exportTitle')"
                  >
                    {{ $t('keyMonitor.schemes.export') }}
                  </button>
                  <button
                    class="btn btn-secondary btn-sm"
                    :disabled="schemeBusy || mappingSchemesList.length === 0"
                    @click="exportAllSchemes"
                    :title="$t('keyMonitor.schemes.exportAllTitle')"
                  >
                    {{ $t('keyMonitor.schemes.exportAll') }}
                  </button>
                  <button
                    class="btn btn-secondary btn-sm"
                    :disabled="schemeBusy"
                    @click="triggerSchemeImport"
                    :title="$t('keyMonitor.schemes.importTitle')"
                  >
                    {{ $t('keyMonitor.schemes.import') }}
                  </button>
                  <input
                    ref="schemeImportInputRef"
                    type="file"
                    accept="application/json,.json"
                    class="hidden"
                    @change="onSchemeImportFileChange"
                  >
                  <button
                    class="btn btn-danger btn-sm"
                    :disabled="schemeBusy || mappingSchemesList.length <= 1 || !activeMappingSchemeName"
                    @click="confirmDeleteScheme"
                  >
                    {{ $t('keyMonitor.schemes.delete') }}
                  </button>
                </div>
              </div>
              <div v-if="schemeError" class="text-sm text-danger mt-2">{{ schemeError }}</div>
              <div class="flex flex-wrap gap-2 items-center mt-3">
                <input
                  v-model="replaceSourceKey"
                  type="text"
                  list="monitor-source-commands"
                  class="form-input min-w-[180px]"
                  :placeholder="$t('keyMonitor.sourcePlaceholder')"
                >
                <datalist id="monitor-source-commands">
                  <option v-for="cmd in correctionSourceOptions" :key="cmd" :value="cmd"></option>
                </datalist>
                <input
                  v-model="replaceTargetKey"
                  type="text"
                  list="valid-monitor-keys"
                  class="form-input min-w-[180px]"
                  :placeholder="$t('keyMonitor.targetPlaceholder')"
                >
                <datalist id="valid-monitor-keys">
                  <option v-for="cmd in validMonitorTargets" :key="cmd" :value="cmd"></option>
                </datalist>
                <button class="btn btn-primary btn-sm" @click="saveCorrectionRule" :disabled="!replaceSourceKey || !replaceTargetKey.trim() || savingMapping">
                  {{ savingMapping ? $t('keyMonitor.savingRule') : $t('keyMonitor.saveRule') }}
                </button>
                <button class="btn btn-secondary btn-sm" @click="restoreCapturedSequence" :disabled="!sequenceDirty">
                  {{ $t('keyMonitor.restoreOriginal') }}
                </button>
              </div>
              <div v-if="detectedInvalidCommands.length > 0" class="text-sm text-yellow-700 mt-2">
                {{ $t('keyMonitor.invalidCommands', { commands: detectedInvalidCommands.join(',') }) }}
              </div>
              <div v-if="mappingError" class="text-sm text-danger mt-2">
                {{ mappingError }}
              </div>
              <div v-if="savedMappingsList.length > 0" class="mt-3">
                <div class="text-sm text-gray-700 mb-2">
                  {{ $t('keyMonitor.savedRulesIn', { name: activeMappingSchemeName || '—' }) }}
                </div>
                <div class="flex flex-col gap-2">
                  <div v-for="mapping in savedMappingsList" :key="mapping.source" class="flex flex-wrap items-center gap-2 text-sm bg-white border rounded px-3 py-2">
                    <span class="font-mono">{{ mapping.source }}</span>
                    <span>→</span>
                    <span class="font-mono text-primary">{{ mapping.target }}</span>
                    <button class="btn btn-secondary btn-sm ml-auto" @click="removeCorrectionRule(mapping.source)">
                      {{ $t('keyMonitor.deleteRule') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>

    <div v-if="schemeModalKind" class="key-monitor-modal-backdrop">
      <div class="key-monitor-modal-box">
        <h4 class="key-monitor-modal-title">
          {{ $t(`keyMonitor.schemes.modal.${schemeModalKind}.title`, schemeModalI18nParams) }}
        </h4>
        <p v-if="schemeModalKind === 'delete'" class="key-monitor-modal-body">
          {{ $t('keyMonitor.schemes.modal.delete.body', schemeModalI18nParams) }}
        </p>
        <template v-else-if="schemeModalKind === 'import'">
          <p class="key-monitor-modal-body">
            {{ $t('keyMonitor.schemes.modal.import.body', { name: pendingImportFileName }) }}
          </p>
          <p class="text-xs text-gray-500 mt-2">
            {{ $t('keyMonitor.schemes.modal.import.namesPreview', { names: pendingImportSchemeNames.join('、') }) }}
          </p>
          <div class="mt-3 grid gap-2">
            <label class="flex items-center gap-2 text-sm">
              <input type="radio" v-model="pendingImportConflict" value="rename">
              {{ $t('keyMonitor.schemes.modal.import.conflictRename') }}
            </label>
            <label class="flex items-center gap-2 text-sm">
              <input type="radio" v-model="pendingImportConflict" value="overwrite">
              {{ $t('keyMonitor.schemes.modal.import.conflictOverwrite') }}
            </label>
            <label class="flex items-center gap-2 text-sm">
              <input type="radio" v-model="pendingImportConflict" value="skip">
              {{ $t('keyMonitor.schemes.modal.import.conflictSkip') }}
            </label>
          </div>
          <div v-if="pendingImportNeedsName" class="mt-3">
            <label class="text-xs font-medium text-gray-700">
              {{ $t('keyMonitor.schemes.modal.import.nameLabel') }}
            </label>
            <input
              v-model="schemeModalInput"
              ref="schemeModalInputRef"
              class="form-input mt-1"
              :placeholder="$t('keyMonitor.schemes.modal.import.namePlaceholder')"
              maxlength="30"
              @keydown.enter="submitSchemeModal"
            >
          </div>
        </template>
        <input
          v-else
          v-model="schemeModalInput"
          ref="schemeModalInputRef"
          class="form-input mt-3"
          :placeholder="$t(`keyMonitor.schemes.modal.${schemeModalKind}.placeholder`)"
          maxlength="30"
          @keydown.enter="submitSchemeModal"
        >
        <div v-if="schemeModalError" class="text-sm text-danger mt-2">{{ schemeModalError }}</div>
        <div class="key-monitor-modal-footer">
          <button class="btn btn-secondary btn-sm" :disabled="schemeBusy" @click="closeSchemeModal">
            {{ $t('common.cancel') }}
          </button>
          <button
            class="btn"
            :class="schemeModalKind === 'delete' ? 'btn-danger' : 'btn-primary'"
            :disabled="schemeModalSubmitDisabled"
            @click="submitSchemeModal"
          >
            {{ schemeModalSubmitLabel }}
          </button>
        </div>
      </div>
    </div>

    <UploadExcelConfirmModal
      :visible="uploadConfirmVisible"
      @confirm="confirmUpload"
      @cancel="cancelUpload"
    />

    <div v-if="assertModalVisible" class="key-monitor-modal-backdrop">
      <div class="key-monitor-modal-box">
        <h4 class="key-monitor-modal-title">{{ $t('keyMonitor.assertModal.title') }}</h4>
        <p class="key-monitor-modal-body">{{ $t('keyMonitor.assertModal.body') }}</p>
        <input
          v-model="assertModalFormat"
          class="form-input mt-3"
          :placeholder="$t('keyMonitor.assertModal.placeholder')"
          @keydown.enter="confirmAssertModal"
        >
        <div class="key-monitor-modal-footer">
          <button class="btn btn-secondary btn-sm" @click="cancelAssertModal">
            {{ $t('common.cancel') }}
          </button>
          <button class="btn btn-primary btn-sm" @click="confirmAssertModal">
            {{ $t('keyMonitor.assertModal.confirm') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 直接写入 Assert 的弹窗 -->
    <div v-if="directAssertModalVisible" class="key-monitor-modal-backdrop">
      <div class="key-monitor-modal-box">
        <h4 class="key-monitor-modal-title">{{ $t('keyMonitor.directAssertModal.title') }}</h4>
        <p class="key-monitor-modal-body">{{ $t('keyMonitor.directAssertModal.body') }}</p>
        <input
          v-model="directAssertModalFormat"
          class="form-input mt-3"
          :placeholder="$t('keyMonitor.directAssertModal.placeholder')"
          @keydown.enter="confirmDirectAssertModal"
        >
        <div class="key-monitor-modal-footer">
          <button class="btn btn-secondary btn-sm" @click="cancelDirectAssertModal">
            {{ $t('common.cancel') }}
          </button>
          <button class="btn btn-primary btn-sm" @click="confirmDirectAssertModal">
            {{ $t('keyMonitor.directAssertModal.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import CustomSelect from '../components/CustomSelect.vue'
import UploadExcelConfirmModal from '../components/UploadExcelConfirmModal.vue'
import { useUploadExcelConfirm } from '../composables/useUploadExcelConfirm.js'
import { showAlert as alert } from '../stores/dialogStore'

const DEVICE_STATUS_EVENT = 'checkpilot:device-updated'
const PLATFORM_AUTH_EVENT = 'checkpilot:platform-auth-updated'
const DEVICE_PREVIEW_REFRESH_INTERVAL = 3000
const DEVICE_PREVIEW_SAVE_DIR_STORAGE_KEY = 'checkpilot:device-preview-save-dir'
const DEVICE_PREVIEW_SOURCE_STORAGE_KEY = 'checkpilot:device-preview-source'
const KEY_MONITOR_TTS_MODE_STORAGE_KEY = 'checkpilot:key-monitor-tts-mode'
const DEVICE_PREVIEW_SOURCE_ADB = 'adb'
const DEVICE_PREVIEW_SOURCE_CAPTURE_CARD = 'capture_card'
const DEVICE_PREVIEW_SOURCE_SCRCPY = 'scrcpy'
const DEVICE_PREVIEW_MODE_SNAPSHOT = 'snapshot'
const DEVICE_PREVIEW_MODE_STREAM = 'stream'
const { t } = useI18n({ useScope: 'global' })

const VALID_MONITOR_KEYS = new Set([
  'OK', 'HOME', 'BACK', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'MENU', 'SETTING',
  'DIGITAL0', 'DIGITAL1', 'DIGITAL2', 'DIGITAL3', 'DIGITAL4', 'DIGITAL5', 'DIGITAL6', 'DIGITAL7', 'DIGITAL8', 'DIGITAL9',
  'APPS', 'POWER', 'SOURCE', 'CHUP', 'CHDOWN', 'EXIT', 'LIBRARY', 'TV_AV', 'VOLUMEUP', 'VOLUMEDOWN',
  'NETFLIX', 'YOUTUBE', 'PRIME_VIDEO', 'PRIME_VII', 'ACTION3', 'ACTIONS', 'FILES', 'RED', 'GREEN', 'YELLOW', 'BLUE',
  'INFORMATION', 'MUTE', 'DISCOVERY', 'ASSERT', 'NOTASSERT'
])
const defaultValidMonitorKeys = Array.from(VALID_MONITOR_KEYS)
  .filter(key => !['PRIME_VII', 'ACTIONS'].includes(key))
  .sort()

const selectedDevice = ref('')
const devicePreviewFrameRef = ref(null)
const devicePreviewImageRef = ref(null)
const devicePreviewUrl = ref('')
const devicePreviewSource = ref(DEVICE_PREVIEW_SOURCE_ADB)
const devicePreviewLabel = ref('')
const devicePreviewMode = ref(DEVICE_PREVIEW_MODE_SNAPSHOT)
const devicePreviewStreamVersion = ref(0)
const devicePreviewLoading = ref(false)
const devicePreviewError = ref('')
const devicePreviewCapturedAt = ref(0)
const devicePreviewSaveDir = ref('')

// 采集卡设备选择
const captureCardDevicesList = ref([])
const captureCardActiveDeviceId = ref(null)
const captureCardListLoading = ref(false)
const captureCardSwitching = ref(false)
const captureCardReleasing = ref(false)
const captureCardError = ref('')
let captureCardListLoaded = false
const devicePreviewHovering = ref(false)
const devicePreviewSelectionActive = ref(false)
const devicePreviewSelectionRect = ref(null)
const devicePreviewSelectionCrop = ref(null)
const devicePreviewSaving = ref(false)
// 截图队列：用户点"加入队列"后图片暂存在前端，可删除/调序，最后批量提交才真正落盘
const pendingScreenshotQueue = ref([])
const screenshotQueueSubmitting = ref(false)
const devicePreviewSaveMessage = ref('')
const keyMonitorActive = ref(false)
const keyMonitorSequence = ref('')
const editableSequence = ref('')
const keyMonitorError = ref('')
let statusTimer = null
let devicePreviewTimer = null
let devicePreviewRequestActive = false
let statusPollingRequestActive = false
let devicePreviewSelectionPointerId = null
let devicePreviewSelectionStartPoint = null
const apiUnavailable = ref(false)
const isStarting = ref(false)
const replaceSourceKey = ref('')
const replaceTargetKey = ref('')
const sequenceDirty = ref(false)
const savedMappings = ref({})
const savingMapping = ref(false)
const mappingError = ref('')
const validMonitorTargets = ref(defaultValidMonitorKeys)

// 纠错规则方案管理
const mappingSchemesList = ref([])
const activeMappingSchemeName = ref('')
const schemeBusy = ref(false)
const schemeError = ref('')
const schemePanelExpanded = ref(false)
const schemeModalKind = ref('') // '' | 'create' | 'rename' | 'duplicate' | 'delete' | 'import'
const schemeModalInput = ref('')
const schemeModalError = ref('')
const schemeModalTargetName = ref('')
const schemeModalInputRef = ref(null)

// 导入相关
const schemeImportInputRef = ref(null)
const pendingImportFile = ref(null)
const pendingImportPayload = ref(null)
const pendingImportConflict = ref('rename')
const excelFiles = ref([])
const selectedExcelFile = ref('')
const excelRows = ref([])
const excelLoadingFiles = ref(false)
const excelLoadingRows = ref(false)
const excelUploading = ref(false)
const excelUploadInput = ref(null)
const excelSavingSequence = ref(false)
const ttsModeEnabled = ref(false)
const assertModeEnabled = ref(false)
const latestWrittenCheckPicName = ref('')
const latestWrittenExcelRowIndex = ref(null)
const excelImportError = ref('')
const excelImportMessage = ref('')

// 同一 caseID 写入次数追踪 & assert 格式弹窗
const caseWriteCounts = ref({})
const assertModalVisible = ref(false)
const assertModalFormat = ref('Assert/1/1')
const assertModalResolve = ref(null)

// 待写入列表
const pendingWriteList = ref([])
const pendingWriteLoading = ref(false)
// 直接写入 Assert 的弹窗（区别于保存时的弹窗）
const directAssertModalVisible = ref(false)
const directAssertModalFormat = ref('Assert/1/1')
const directAssertModalResolve = ref(null)
const tmsProjects = ref([])
const selectedTmsProjectId = ref('')
const tmsModules = ref([])
const selectedTmsModuleValue = ref('')
const tmsPageSize = ref(20)
const tmsCurrentPage = ref(1)
const tmsCaseNumbers = ref([])
const tmsTestcaseDetails = ref([])
const selectedTmsCaseNumber = ref('')
const manualCaseNumber = ref('')
const tmsCaseNumberSearch = ref('')
const tmsCaseNumberSubmittedKeyword = ref('')
// 搜索时跨页用例全集（仅当前 project+module 维度，切换时清掉）
const tmsAllCaseNumbers = ref([])
const tmsAllTestcaseDetails = ref([])
const tmsAllLoading = ref(false)
const tmsAllLoaded = ref(false)
// 全集加载的代次 token：每次开始一次新的全集加载就 +1，
// 旧的 await 循环看到 token 不一致就立刻返回，避免并发 race 把陈旧数据写回 ref。
let tmsAllLoadingId = 0
// 用于在搜索后自动弹出下拉面板的 select 引用
const tmsModuleSelectRef = ref(null)
const tmsCaseNumberSelectRef = ref(null)
const tmsTotal = ref(0)
const tmsLoadingProjects = ref(false)
const tmsLoadingModules = ref(false)
const tmsLoadingTestcases = ref(false)
const tmsError = ref('')
const devicePreviewIsLiveStream = computed(() => devicePreviewMode.value === DEVICE_PREVIEW_MODE_STREAM)
const devicePreviewCapturedLabel = computed(() => {
  if (devicePreviewIsLiveStream.value || !devicePreviewCapturedAt.value) {
    return ''
  }

  return new Date(devicePreviewCapturedAt.value).toLocaleString()
})
const devicePreviewUsesCaptureCard = computed(() => devicePreviewSource.value === DEVICE_PREVIEW_SOURCE_CAPTURE_CARD)
const devicePreviewUsesScrcpy = computed(() => devicePreviewSource.value === DEVICE_PREVIEW_SOURCE_SCRCPY)
const canLoadDevicePreview = computed(() => devicePreviewUsesCaptureCard.value || devicePreviewUsesScrcpy.value || Boolean(selectedDevice.value))
const devicePreviewIdentityLabel = computed(() => {
  if (devicePreviewLabel.value) {
    return devicePreviewLabel.value
  }
  if (devicePreviewUsesCaptureCard.value) {
    return t('keyMonitor.devicePreviewCaptureCardLabel')
  }
  if (devicePreviewUsesScrcpy.value) {
    return `scrcpy · ${selectedDevice.value || ''}`
  }
  return selectedDevice.value || ''
})
const devicePreviewInteractionLocked = computed(() => {
  if (devicePreviewUsesCaptureCard.value || devicePreviewUsesScrcpy.value) {
    return devicePreviewSelectionActive.value || Boolean(devicePreviewSelectionCrop.value)
  }

  return devicePreviewHovering.value || devicePreviewSelectionActive.value || Boolean(devicePreviewSelectionCrop.value)
})
const devicePreviewSelectionStyle = computed(() => {
  if (!devicePreviewSelectionRect.value) {
    return null
  }

  return {
    left: `${devicePreviewSelectionRect.value.x}px`,
    top: `${devicePreviewSelectionRect.value.y}px`,
    width: `${devicePreviewSelectionRect.value.width}px`,
    height: `${devicePreviewSelectionRect.value.height}px`,
  }
})
const devicePreviewFooterText = computed(() => {
  if (devicePreviewSelectionCrop.value) {
    return t('keyMonitor.devicePreviewSelectionReady', {
      width: devicePreviewSelectionCrop.value.width,
      height: devicePreviewSelectionCrop.value.height,
    })
  }

  if (devicePreviewHovering.value || devicePreviewSelectionActive.value) {
    return t('keyMonitor.devicePreviewSelectionHint')
  }

  if (devicePreviewUsesCaptureCard.value && devicePreviewIsLiveStream.value) {
    return t('keyMonitor.devicePreviewLiveStream')
  }

  return t('keyMonitor.devicePreviewAutoRefresh')
})
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
const schemeModalI18nParams = computed(() => ({
  name: schemeModalTargetName.value || activeMappingSchemeName.value || ''
}))
const schemeModalSubmitLabel = computed(() => {
  switch (schemeModalKind.value) {
    case 'create': return t('keyMonitor.schemes.modal.create.submit')
    case 'rename': return t('keyMonitor.schemes.modal.rename.submit')
    case 'duplicate': return t('keyMonitor.schemes.modal.duplicate.submit')
    case 'delete': return t('keyMonitor.schemes.modal.delete.submit')
    case 'import': return t('keyMonitor.schemes.modal.import.submit')
    default: return ''
  }
})
const schemeModalSubmitDisabled = computed(() => {
  if (schemeBusy.value) return true
  if (schemeModalKind.value === 'delete') return false
  if (schemeModalKind.value === 'import') {
    if (!pendingImportPayload.value) return true
    if (pendingImportNeedsName.value && !schemeModalInput.value.trim()) return true
    return false
  }
  return !schemeModalInput.value.trim()
})

// Select options computed properties
const tmsProjectOptions = computed(() => [
  { value: '', label: t('keyMonitor.selectRemoteProject') },
  ...tmsProjects.value.map((project) => ({
    value: String(project.id),
    label: project.name,
  })),
])

const tmsModuleOptions = computed(() => [
  { value: '', label: t('keyMonitor.selectRemoteModule') },
  ...filteredTmsModules.value.map((moduleItem) => ({
    value: moduleItem.value,
    label: formatTmsModuleLabel(moduleItem),
  })),
])

const tmsPageSizeOptions = computed(() => [
  { value: 10, label: '10' },
  { value: 20, label: '20' },
  { value: 50, label: '50' },
  { value: 100, label: '100' },
])

const tmsCaseNumberOptions = computed(() => [
  { value: '', label: t('keyMonitor.selectRemoteCaseNumber') },
  ...paginatedFilteredTmsCaseNumbers.value.map((caseNumber) => ({
    value: caseNumber,
    label: caseNumber,
  })),
])

const excelFileOptions = computed(() => [
  { value: '', label: t('keyMonitor.selectExcel') },
  ...excelFiles.value.map((file) => ({
    value: file,
    label: file,
  })),
])

const devicePreviewSourceOptions = computed(() => [
  { value: DEVICE_PREVIEW_SOURCE_ADB, label: t('keyMonitor.devicePreviewSourceAdb') },
  { value: DEVICE_PREVIEW_SOURCE_CAPTURE_CARD, label: t('keyMonitor.devicePreviewSourceCaptureCard') },
  { value: DEVICE_PREVIEW_SOURCE_SCRCPY, label: t('keyMonitor.devicePreviewSourceScrcpy') },
])

const captureCardDeviceOptions = computed(() => {
  if (captureCardDevicesList.value.length === 0) {
    return [{ value: captureCardActiveDeviceId.value, label: captureCardListLoading.value ? t('keyMonitor.captureCardScanning') : t('keyMonitor.captureCardNoDevices') }]
  }
  return captureCardDevicesList.value.map((dev) => ({
    value: dev.device_id,
    label: dev.label,
  }))
})

const pendingImportFileName = computed(() => pendingImportFile.value?.name || '')
const pendingImportSchemeNames = computed(() => {
  const payload = pendingImportPayload.value
  if (!payload || !payload.schemes || typeof payload.schemes !== 'object') return []
  return Object.keys(payload.schemes)
})
// 扁平格式（"未命名方案"）必须由用户给名字
const pendingImportNeedsName = computed(() => {
  return pendingImportSchemeNames.value.length === 0
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

function applyTtsMarker(sequence) {
  const commands = normalizeCommandSequence(sequence)
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => item.toUpperCase() !== 'TTS')

  if (commands.length === 0) {
    return ''
  }

  commands.splice(Math.max(commands.length - 1, 0), 0, 'TTS')
  return commands.join(',')
}

const clearExcelImportStatus = () => {
  excelImportError.value = ''
  excelImportMessage.value = ''
}

const buildSequenceForExcelWrite = (sequence) => {
  const normalized = normalizeCommandSequence(sequence)
  if (!normalized) {
    return ''
  }

  return ttsModeEnabled.value ? applyTtsMarker(normalized) : normalized
}

const notifyPlatformAuthStatusChange = () => {
  window.dispatchEvent(new CustomEvent(PLATFORM_AUTH_EVENT))
}

const resetDevicePreviewSelection = () => {
  devicePreviewSelectionActive.value = false
  devicePreviewSelectionRect.value = null
  devicePreviewSelectionCrop.value = null
  devicePreviewSelectionPointerId = null
  devicePreviewSelectionStartPoint = null
}

const clearDevicePreview = () => {
  devicePreviewUrl.value = ''
  devicePreviewLabel.value = ''
  devicePreviewMode.value = DEVICE_PREVIEW_MODE_SNAPSHOT
  devicePreviewError.value = ''
  devicePreviewCapturedAt.value = 0
  devicePreviewHovering.value = false
  devicePreviewSaveMessage.value = ''
  resetDevicePreviewSelection()
}

const buildCaptureCardStreamUrl = () => {
  return `/api/devices/preview/stream?source=${encodeURIComponent(DEVICE_PREVIEW_SOURCE_CAPTURE_CARD)}&stream=${devicePreviewStreamVersion.value}`
}

const startCaptureCardLivePreview = () => {
  if (!devicePreviewUsesCaptureCard.value || !canLoadDevicePreview.value || devicePreviewInteractionLocked.value) {
    return
  }

  devicePreviewStreamVersion.value += 1
  devicePreviewMode.value = DEVICE_PREVIEW_MODE_STREAM
  devicePreviewLoading.value = true
  devicePreviewCapturedAt.value = 0
  devicePreviewLabel.value = t('keyMonitor.devicePreviewCaptureCardLabel')
  devicePreviewError.value = ''
  devicePreviewSaveMessage.value = ''
  devicePreviewUrl.value = buildCaptureCardStreamUrl()
}

const buildScrcpyStreamUrl = () => {
  return `/api/devices/preview/stream?source=${encodeURIComponent(DEVICE_PREVIEW_SOURCE_SCRCPY)}&stream=${devicePreviewStreamVersion.value}`
}

const startScrcpyLivePreview = () => {
  if (!devicePreviewUsesScrcpy.value || !canLoadDevicePreview.value || devicePreviewInteractionLocked.value) {
    return
  }

  devicePreviewStreamVersion.value += 1
  devicePreviewMode.value = DEVICE_PREVIEW_MODE_STREAM
  devicePreviewLoading.value = true
  devicePreviewCapturedAt.value = 0
  devicePreviewLabel.value = `scrcpy · ${selectedDevice.value || ''}`
  devicePreviewError.value = ''
  devicePreviewSaveMessage.value = ''
  devicePreviewUrl.value = buildScrcpyStreamUrl()
}

const stopDevicePreviewPolling = () => {
  if (devicePreviewTimer) {
    clearInterval(devicePreviewTimer)
    devicePreviewTimer = null
  }
}

const startDevicePreviewPolling = () => {
  stopDevicePreviewPolling()
  if (!canLoadDevicePreview.value || devicePreviewInteractionLocked.value) {
    return
  }

  if (devicePreviewUsesCaptureCard.value) {
    startCaptureCardLivePreview()
    return
  }

  if (devicePreviewUsesScrcpy.value) {
    startScrcpyLivePreview()
    return
  }

  devicePreviewTimer = setInterval(() => {
    void fetchDevicePreview({ silent: true })
  }, DEVICE_PREVIEW_REFRESH_INTERVAL)
}

const fetchDevicePreview = async ({ silent = false } = {}) => {
  if (!canLoadDevicePreview.value || devicePreviewRequestActive) {
    return
  }

  devicePreviewRequestActive = true
  devicePreviewLoading.value = !silent
  devicePreviewMode.value = DEVICE_PREVIEW_MODE_SNAPSHOT

  try {
    const response = await fetch(`/api/devices/preview?source=${encodeURIComponent(devicePreviewSource.value)}`)
    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      if (response.status === 400 && !devicePreviewUsesCaptureCard.value) {
        selectedDevice.value = ''
        clearDevicePreview()
        return
      }
      throw new Error(data.detail || t('keyMonitor.alerts.loadDevicePreviewFailed'))
    }

    // scrcpy 返回 jpeg_base64 而非 screenshot_url
    if (data.jpeg_base64) {
      devicePreviewUrl.value = `data:image/jpeg;base64,${data.jpeg_base64}`
    } else if (typeof data.screenshot_url === 'string' && data.screenshot_url) {
      devicePreviewUrl.value = data.screenshot_url
    } else {
      throw new Error(t('keyMonitor.alerts.loadDevicePreviewFailed'))
    }
    devicePreviewCapturedAt.value = Number(data.captured_at) || 0
    devicePreviewLabel.value = typeof data.preview_label === 'string' ? data.preview_label : ''
    if (!devicePreviewUsesCaptureCard.value) {
      selectedDevice.value = data.device || selectedDevice.value
    }
    devicePreviewError.value = ''
    devicePreviewSaveMessage.value = ''
    resetDevicePreviewSelection()
  } catch (error) {
    if (!devicePreviewUrl.value || !silent) {
      devicePreviewError.value = error.message || t('keyMonitor.alerts.loadDevicePreviewFailed')
    }
  } finally {
    devicePreviewLoading.value = false
    devicePreviewRequestActive = false
  }
}

const handleDevicePreviewRefresh = async () => {
  devicePreviewSaveMessage.value = ''
  resetDevicePreviewSelection()

  if (devicePreviewUsesCaptureCard.value && !devicePreviewInteractionLocked.value) {
    startCaptureCardLivePreview()
    return
  }

  if (devicePreviewUsesScrcpy.value && !devicePreviewInteractionLocked.value) {
    startScrcpyLivePreview()
    return
  }

  await fetchDevicePreview()
}

const clearDevicePreviewSelection = () => {
  devicePreviewSaveMessage.value = ''
  devicePreviewError.value = ''
  resetDevicePreviewSelection()
}

const handleDevicePreviewPointerEnter = () => {
  if (!devicePreviewUrl.value) {
    return
  }
  devicePreviewHovering.value = true
}

const handleDevicePreviewPointerLeave = () => {
  devicePreviewHovering.value = false
}

const getDevicePreviewMetrics = () => {
  const frame = devicePreviewFrameRef.value
  const image = devicePreviewImageRef.value
  if (!frame || !image || !image.complete || !image.naturalWidth || !image.naturalHeight) {
    return null
  }

  const bounds = frame.getBoundingClientRect()
  const scale = Math.min(bounds.width / image.naturalWidth, bounds.height / image.naturalHeight)
  const renderedWidth = image.naturalWidth * scale
  const renderedHeight = image.naturalHeight * scale
  const offsetX = (bounds.width - renderedWidth) / 2
  const offsetY = (bounds.height - renderedHeight) / 2

  return {
    bounds,
    scale,
    offsetX,
    offsetY,
    renderedWidth,
    renderedHeight,
    naturalWidth: image.naturalWidth,
    naturalHeight: image.naturalHeight,
  }
}

const getDevicePreviewPoint = (event, metrics) => {
  const relativeX = event.clientX - metrics.bounds.left
  const relativeY = event.clientY - metrics.bounds.top

  if (
    relativeX < metrics.offsetX ||
    relativeX > metrics.offsetX + metrics.renderedWidth ||
    relativeY < metrics.offsetY ||
    relativeY > metrics.offsetY + metrics.renderedHeight
  ) {
    return null
  }

  return { x: relativeX, y: relativeY }
}

const clampDevicePreviewPoint = (event, metrics) => {
  const relativeX = event.clientX - metrics.bounds.left
  const relativeY = event.clientY - metrics.bounds.top

  return {
    x: Math.min(metrics.offsetX + metrics.renderedWidth, Math.max(metrics.offsetX, relativeX)),
    y: Math.min(metrics.offsetY + metrics.renderedHeight, Math.max(metrics.offsetY, relativeY)),
  }
}

const updateDevicePreviewSelectionGeometry = (startPoint, endPoint, metrics) => {
  const x = Math.min(startPoint.x, endPoint.x)
  const y = Math.min(startPoint.y, endPoint.y)
  const width = Math.abs(endPoint.x - startPoint.x)
  const height = Math.abs(endPoint.y - startPoint.y)

  devicePreviewSelectionRect.value = { x, y, width, height }

  const cropX = Math.max(0, Math.round((x - metrics.offsetX) / metrics.scale))
  const cropY = Math.max(0, Math.round((y - metrics.offsetY) / metrics.scale))
  const cropWidth = Math.min(
    metrics.naturalWidth - cropX,
    Math.round(width / metrics.scale)
  )
  const cropHeight = Math.min(
    metrics.naturalHeight - cropY,
    Math.round(height / metrics.scale)
  )

  if (cropWidth < 4 || cropHeight < 4) {
    devicePreviewSelectionCrop.value = null
    return
  }

  devicePreviewSelectionCrop.value = {
    x: cropX,
    y: cropY,
    width: cropWidth,
    height: cropHeight,
  }
}

const handleDevicePreviewImageLoad = () => {
  devicePreviewLoading.value = false
  if (devicePreviewIsLiveStream.value || devicePreviewSelectionActive.value) {
    return
  }

  resetDevicePreviewSelection()
}

const handleDevicePreviewImageError = () => {
  devicePreviewLoading.value = false
  devicePreviewError.value = devicePreviewUsesCaptureCard.value
    ? t('keyMonitor.alerts.loadCaptureCardPreviewFailed')
    : t('keyMonitor.alerts.loadDevicePreviewFailed')
}

const beginDevicePreviewSelection = (event) => {
  if (!devicePreviewUrl.value) {
    return
  }

  const metrics = getDevicePreviewMetrics()
  if (!metrics) {
    return
  }

  const startPoint = getDevicePreviewPoint(event, metrics)
  if (!startPoint) {
    return
  }

  event.preventDefault()
  event.currentTarget?.setPointerCapture?.(event.pointerId)
  devicePreviewSelectionPointerId = event.pointerId
  devicePreviewSelectionStartPoint = startPoint
  devicePreviewSelectionActive.value = true
  devicePreviewSaveMessage.value = ''
  devicePreviewError.value = ''
  updateDevicePreviewSelectionGeometry(startPoint, startPoint, metrics)
}

const updateDevicePreviewSelection = (event) => {
  if (!devicePreviewSelectionActive.value || devicePreviewSelectionPointerId !== event.pointerId || !devicePreviewSelectionStartPoint) {
    return
  }

  const metrics = getDevicePreviewMetrics()
  if (!metrics) {
    return
  }

  const currentPoint = clampDevicePreviewPoint(event, metrics)
  updateDevicePreviewSelectionGeometry(devicePreviewSelectionStartPoint, currentPoint, metrics)
}

const finishDevicePreviewSelection = (event) => {
  if (!devicePreviewSelectionActive.value || devicePreviewSelectionPointerId !== event.pointerId) {
    return
  }

  const metrics = getDevicePreviewMetrics()
  if (metrics && devicePreviewSelectionStartPoint) {
    const endPoint = clampDevicePreviewPoint(event, metrics)
    updateDevicePreviewSelectionGeometry(devicePreviewSelectionStartPoint, endPoint, metrics)
  }

  event.currentTarget?.releasePointerCapture?.(event.pointerId)
  devicePreviewSelectionActive.value = false
  devicePreviewSelectionPointerId = null
  devicePreviewSelectionStartPoint = null

  if (!devicePreviewSelectionCrop.value) {
    devicePreviewSelectionRect.value = null
  }
}

// 把 "<stem>-<数字>.png" 的尾部数字后缀剥掉，得到原始 base 名。
// 用于"再次保存截图"时不被上一次冲突避让产生的 -N 后缀污染：
// 上次保存因为冲突被命名为 SETTING-1.png，前端缓存到 latestWrittenCheckPicName；
// 用户删掉旧文件后再保存，应该从 SETTING.png 开始而不是继续接力 SETTING-1.png。
const stripNumericFilenameSuffix = (filename) => {
  const value = String(filename || '')
  const lastDot = value.lastIndexOf('.')
  const stem = lastDot >= 0 ? value.slice(0, lastDot) : value
  const ext = lastDot >= 0 ? value.slice(lastDot) : ''
  const cleanedStem = stem.replace(/-\d+$/, '')
  return `${cleanedStem}${ext}`
}

const buildDevicePreviewSelectionFilename = () => {
  const preferredFileName = String(latestWrittenCheckPicName.value || '').trim()
  if (preferredFileName) {
    // 用 base 名作为请求文件名，把上次冲突避让加的 -N 剥掉，避免"删了旧文件还是 -N"
    return stripNumericFilenameSuffix(preferredFileName)
  }

  const stamp = new Date(devicePreviewCapturedAt.value || Date.now())
  const pad = (value) => String(value).padStart(2, '0')
  const timestamp = [
    stamp.getFullYear(),
    pad(stamp.getMonth() + 1),
    pad(stamp.getDate()),
    '_',
    pad(stamp.getHours()),
    pad(stamp.getMinutes()),
    pad(stamp.getSeconds()),
  ].join('')

  const caseNumber = String(effectiveCaseNumber.value || '').trim()
  if (caseNumber) {
    return `${caseNumber.replace(/[\\/:*?"<>|]/g, '_')}.png`
  }

  return `${timestamp}.png`
}

// 根据队列里的位置生成预期文件名：第 0 项 = base.png，第 N 项 = base-N.png。
// base 优先用上次写回 Excel 的 checkPic（剥掉 -N 后缀作为 stem），再退到 case_number / 时间戳。
const buildQueueItemFilename = (queueIndex) => {
  const baseName = stripNumericFilenameSuffix(buildDevicePreviewSelectionFilename())
  if (queueIndex <= 0) return baseName

  const dotIndex = baseName.lastIndexOf('.')
  const stem = dotIndex >= 0 ? baseName.slice(0, dotIndex) : baseName
  const ext = dotIndex >= 0 ? baseName.slice(dotIndex) : '.png'
  return `${stem}-${queueIndex}${ext}`
}

// 把当前框选画面渲染到 canvas → 取 base64，再连同候选文件名 / 缩略图入队。
// 不立即落盘，落盘在 submitScreenshotQueue。
const enqueueSelectedDevicePreview = async () => {
  if (!devicePreviewSelectionCrop.value || screenshotQueueSubmitting.value) {
    return
  }

  const image = devicePreviewImageRef.value
  if (!image || !image.complete) {
    devicePreviewError.value = t('keyMonitor.alerts.saveDevicePreviewSelectionFailed')
    return
  }

  devicePreviewSaveMessage.value = ''
  devicePreviewError.value = ''

  try {
    const crop = devicePreviewSelectionCrop.value
    const canvas = document.createElement('canvas')
    canvas.width = crop.width
    canvas.height = crop.height

    const context = canvas.getContext('2d')
    if (!context) {
      throw new Error(t('keyMonitor.alerts.saveDevicePreviewSelectionFailed'))
    }

    context.drawImage(image, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height)

    const dataUrl = canvas.toDataURL('image/png')
    const imageBase64 = dataUrl.split(',')[1]
    if (!imageBase64) {
      throw new Error(t('keyMonitor.alerts.saveDevicePreviewSelectionFailed'))
    }

    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const fileName = buildQueueItemFilename(pendingScreenshotQueue.value.length)
    pendingScreenshotQueue.value.push({
      id,
      base64: imageBase64,
      thumbnail: dataUrl,
      fileName,
    })

    devicePreviewSaveMessage.value = t('keyMonitor.screenshotEnqueued', { name: fileName })
    resetDevicePreviewSelection()
  } catch (error) {
    devicePreviewError.value = error.message || t('keyMonitor.alerts.saveDevicePreviewSelectionFailed')
  }
}

// 调序后重新按位置命名：第 0 项 base.png，其它 -1 -2 ...
const renameScreenshotQueue = () => {
  pendingScreenshotQueue.value.forEach((item, index) => {
    item.fileName = buildQueueItemFilename(index)
  })
}

const removeScreenshotQueueItem = (id) => {
  const index = pendingScreenshotQueue.value.findIndex((item) => item.id === id)
  if (index < 0) return
  pendingScreenshotQueue.value.splice(index, 1)
  renameScreenshotQueue()
}

const moveScreenshotQueueItem = (id, direction) => {
  const arr = pendingScreenshotQueue.value
  const index = arr.findIndex((item) => item.id === id)
  if (index < 0) return
  const target = index + direction
  if (target < 0 || target >= arr.length) return
  ;[arr[index], arr[target]] = [arr[target], arr[index]]
  renameScreenshotQueue()
}

const clearScreenshotQueue = () => {
  pendingScreenshotQueue.value = []
}

// 按队列顺序批量调 /api/devices/preview/save，全部 overwrite=true 严格按队列文件名落盘。
const submitScreenshotQueue = async () => {
  if (pendingScreenshotQueue.value.length === 0 || screenshotQueueSubmitting.value) {
    return
  }

  screenshotQueueSubmitting.value = true
  devicePreviewSaveMessage.value = ''
  devicePreviewError.value = ''

  const failed = []
  let savedCount = 0

  try {
    for (const item of [...pendingScreenshotQueue.value]) {
      try {
        const response = await fetch('/api/devices/preview/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image_base64: item.base64,
            file_name: item.fileName,
            save_dir: devicePreviewSaveDir.value.trim() || undefined,
            overwrite: true,
          }),
        })
        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
          throw new Error(data.detail || t('keyMonitor.alerts.saveDevicePreviewSelectionFailed'))
        }
        savedCount += 1
      } catch (error) {
        failed.push({ ...item, error: error.message || t('keyMonitor.alerts.saveDevicePreviewSelectionFailed') })
      }
    }

    // 把没成功的留在队列里供用户重试，成功的丢掉
    pendingScreenshotQueue.value = failed.map(({ error: _err, ...rest }) => rest)
    renameScreenshotQueue()

    if (failed.length > 0) {
      devicePreviewError.value = t('keyMonitor.alerts.screenshotQueuePartialFailed', {
        success: savedCount,
        failed: failed.length,
      })
    } else if (savedCount > 0) {
      devicePreviewSaveMessage.value = t('keyMonitor.screenshotQueueSaved', { count: savedCount })
    }
  } finally {
    screenshotQueueSubmitting.value = false
  }
}

const clearTmsTestcaseResults = ({ clearAll = true } = {}) => {
  tmsCaseNumbers.value = []
  tmsTestcaseDetails.value = []
  selectedTmsCaseNumber.value = ''
  tmsTotal.value = 0
  if (clearAll) {
    tmsAllCaseNumbers.value = []
    tmsAllTestcaseDetails.value = []
    tmsAllLoaded.value = false
    // 翻新 loading token：让任何还在 await 的旧 loadAllTmsTestcases 循环立刻退出，
    // 避免它把旧 project/module 的数据写回 ref。
    tmsAllLoadingId += 1
  }
}

// 用例库 / 模块切换或登录态变化时，把搜索关键字也一起重置到初始状态。
const resetTmsSearchAndResults = () => {
  tmsCaseNumberSearch.value = ''
  tmsCaseNumberSubmittedKeyword.value = ''
  clearTmsTestcaseResults()
}

const selectedTestcaseDetail = computed(() => {
  if (!selectedTmsCaseNumber.value) return null
  const list = Array.isArray(tmsTestcaseDetails.value) ? tmsTestcaseDetails.value : []
  const inPage = list.find((item) => item && item.case_number === selectedTmsCaseNumber.value)
  if (inPage) return inPage

  // 当前页没有，退到跨页全集里找（搜索后选中跨页结果时会用到）
  const allList = Array.isArray(tmsAllTestcaseDetails.value) ? tmsAllTestcaseDetails.value : []
  return allList.find((item) => item && item.case_number === selectedTmsCaseNumber.value) || null
})

// 有效用例编号：优先使用 TMS 下拉选中的，其次使用手动输入的
const effectiveCaseNumber = computed(() => {
  const tms = String(selectedTmsCaseNumber.value || '').trim()
  if (tms) return tms
  return String(manualCaseNumber.value || '').trim()
})

// 用例编号下拉最多展示条数
const MAX_DISPLAY_CASE_NUMBERS = 100

const filteredTmsCaseNumbers = computed(() => {
  const keyword = String(tmsCaseNumberSubmittedKeyword.value || '').trim().toLowerCase()
  // 关键字为空：保持原来的当前页展示
  if (!keyword) {
    return Array.isArray(tmsCaseNumbers.value) ? tmsCaseNumbers.value : []
  }

  // 关键字非空：在跨页全集里筛，全集还没加载则退化到当前页
  const sourceCaseNumbers = tmsAllLoaded.value
    ? (Array.isArray(tmsAllCaseNumbers.value) ? tmsAllCaseNumbers.value : [])
    : (Array.isArray(tmsCaseNumbers.value) ? tmsCaseNumbers.value : [])
  const sourceDetails = tmsAllLoaded.value
    ? (Array.isArray(tmsAllTestcaseDetails.value) ? tmsAllTestcaseDetails.value : [])
    : (Array.isArray(tmsTestcaseDetails.value) ? tmsTestcaseDetails.value : [])

  const moduleByCaseNumber = new Map()
  sourceDetails.forEach((item) => {
    if (!item || !item.case_number) return
    moduleByCaseNumber.set(item.case_number, String(item.module || '').toLowerCase())
  })

  const matched = sourceCaseNumbers.filter((caseNumber) => {
    const lowered = String(caseNumber || '').toLowerCase()
    if (lowered.includes(keyword)) return true
    const moduleLabel = moduleByCaseNumber.get(caseNumber) || ''
    return moduleLabel.includes(keyword)
  })

  return matched
})

// 搜索模式下的客户端分页：将 filteredTmsCaseNumbers 按 tmsPageSize 切片
const paginatedFilteredTmsCaseNumbers = computed(() => {
  const keyword = String(tmsCaseNumberSubmittedKeyword.value || '').trim().toLowerCase()
  // 非搜索模式直接返回（服务端分页，filteredTmsCaseNumbers 本身就是当前页数据）
  if (!keyword) {
    return filteredTmsCaseNumbers.value
  }
  // 搜索模式：对全量搜索结果做客户端分页
  const size = normalizeTmsPageSize()
  const start = (tmsCurrentPage.value - 1) * size
  return filteredTmsCaseNumbers.value.slice(start, start + size)
})

// 搜索结果是否被截断（用于提示用户缩小搜索范围）
const tmsCaseNumberResultsTruncated = computed(() => {
  const keyword = String(tmsCaseNumberSubmittedKeyword.value || '').trim().toLowerCase()
  if (!keyword) return false

  const sourceCaseNumbers = tmsAllLoaded.value
    ? (Array.isArray(tmsAllCaseNumbers.value) ? tmsAllCaseNumbers.value : [])
    : (Array.isArray(tmsCaseNumbers.value) ? tmsCaseNumbers.value : [])
  const sourceDetails = tmsAllLoaded.value
    ? (Array.isArray(tmsAllTestcaseDetails.value) ? tmsAllTestcaseDetails.value : [])
    : (Array.isArray(tmsTestcaseDetails.value) ? tmsTestcaseDetails.value : [])

  const moduleByCaseNumber = new Map()
  sourceDetails.forEach((item) => {
    if (!item || !item.case_number) return
    moduleByCaseNumber.set(item.case_number, String(item.module || '').toLowerCase())
  })

  let count = 0
  for (const caseNumber of sourceCaseNumbers) {
    const lowered = String(caseNumber || '').toLowerCase()
    if (lowered.includes(keyword)) { count++; continue }
    const moduleLabel = moduleByCaseNumber.get(caseNumber) || ''
    if (moduleLabel.includes(keyword)) { count++ }
    if (count > MAX_DISPLAY_CASE_NUMBERS) return true
  }
  return false
})

// 模块下拉的模糊筛选：关键字非空时显示满足以下任一条件的模块
//   1. 模块自身的 name/value 含关键字
//   2. 该模块下存在用例编号 / 模块名命中关键字（即用例搜索结果"所属"的模块）
// 这样用户输入用例编号搜索时，对应用例所在的模块也会保留在模块下拉里，便于切换查看。
const filteredTmsModules = computed(() => {
  const list = Array.isArray(tmsModules.value) ? tmsModules.value : []
  const keyword = String(tmsCaseNumberSubmittedKeyword.value || '').trim().toLowerCase()
  if (!keyword) return list

  // 用例编号搜索命中后，detail.module 里保存的"模块标签"集合
  const detailList = tmsAllLoaded.value
    ? (Array.isArray(tmsAllTestcaseDetails.value) ? tmsAllTestcaseDetails.value : [])
    : (Array.isArray(tmsTestcaseDetails.value) ? tmsTestcaseDetails.value : [])
  const matchedModuleLabels = new Set()
  detailList.forEach((detail) => {
    if (!detail || !detail.case_number) return
    const caseNumberLower = String(detail.case_number).toLowerCase()
    const moduleLabelLower = String(detail.module || '').toLowerCase()
    if (caseNumberLower.includes(keyword) || moduleLabelLower.includes(keyword)) {
      if (detail.module) matchedModuleLabels.add(String(detail.module).toLowerCase())
    }
  })

  const filtered = list.filter((item) => {
    if (!item) return false
    const name = String(item.name || '').toLowerCase()
    const value = String(item.value || '').toLowerCase()
    if (name.includes(keyword) || value.includes(keyword)) return true
    // 通过用例命中的 module 标签反查：detail.module 一般等于 module 的 value 或 formatTmsModuleLabel 输出
    if (matchedModuleLabels.has(name) || matchedModuleLabels.has(value)) return true
    return false
  })

  // 确保当前选中的模块始终保留在列表中，避免浏览器因选项被移除而自动将 select 重置为空值
  const selected = selectedTmsModuleValue.value
  if (selected && !filtered.some((item) => item && item.value === selected)) {
    const original = list.find((item) => item && item.value === selected)
    if (original) filtered.unshift(original)
  }

  return filtered
})

const filteredTestcaseSteps = computed(() => {
  const steps = selectedTestcaseDetail.value?.steps
  if (!Array.isArray(steps)) return []
  return steps
    .map((s, i) => ({ index: i + 1, step: (s?.step || '').trim() }))
    .filter(item => item.step)
})

const filteredTestcaseExpected = computed(() => {
  const steps = selectedTestcaseDetail.value?.steps
  if (!Array.isArray(steps)) return []
  return steps
    .map((s, i) => ({ index: i + 1, expected: (s?.expected || '').trim() }))
    .filter(item => item.expected)
})

const tmsTotalPages = computed(() => {
  const keyword = String(tmsCaseNumberSubmittedKeyword.value || '').trim().toLowerCase()
  const size = normalizeTmsPageSize()
  if (!size) return 1

  // 搜索模式：总页数基于搜索结果总数（客户端分页）
  if (keyword) {
    const filteredCount = filteredTmsCaseNumbers.value.length
    return Math.max(1, Math.ceil(filteredCount / size))
  }

  // 非搜索模式：总页数基于服务端返回的总数
  const total = tmsTotal.value
  if (!total) return 1
  return Math.max(1, Math.ceil(total / size))
})

const normalizeTmsPageSize = () => {
  const parsedSize = Number(tmsPageSize.value)
  if (!Number.isFinite(parsedSize)) {
    tmsPageSize.value = 20
    return 20
  }

  const normalizedSize = Math.min(100, Math.max(1, Math.trunc(parsedSize)))
  tmsPageSize.value = normalizedSize
  return normalizedSize
}

const canAutoLoadTmsCaseNumbers = () => {
  return Boolean(selectedTmsProjectId.value && selectedTmsModuleValue.value)
}

const maybeLoadTmsTestcases = async () => {
  if (!canAutoLoadTmsCaseNumbers()) {
    clearTmsTestcaseResults()
    return
  }

  await loadTmsTestcases()
}

const fetchTmsPayload = async (url, fallbackMessage) => {
  console.log(`[TMS] 发起请求: ${url}`)
  let response
  try {
    response = await fetch(url)
  } catch (networkError) {
    console.error(`[TMS] 网络错误: ${url}`, networkError)
    // 网络异常也可能意味着会话出问题，让 App / Home 拉一次登录态自修正
    notifyPlatformAuthStatusChange()
    throw networkError
  }

  const data = await response.json().catch(() => ({}))
  console.log(`[TMS] 响应状态: ${response.status}`, data)

  if (!response.ok || data?.status === 'error') {
    console.error(`[TMS] 请求失败: ${url}`, data)
    // 仅在失败时派发事件；成功时不派发，避免每次正常请求都触发一次
    // /api/platform-auth/status 的全局拉取，导致后端日志被刷屏。
    notifyPlatformAuthStatusChange()
    throw new Error(data?.detail || data?.message || fallbackMessage)
  }

  console.log(`[TMS] 请求成功: ${url}`)
  return data
}

const formatTmsModuleLabel = (moduleItem) => {
  const moduleName = String(moduleItem?.name || '').trim()
  const moduleValue = String(moduleItem?.value || '').trim()
  if (!moduleValue) {
    return moduleName
  }

  return moduleValue === moduleName ? moduleName : moduleValue
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

const handleDeviceStatusChange = (event) => {
  const device = typeof event?.detail?.device === 'string' ? event.detail.device : ''
  if (device) {
    selectedDevice.value = device
    return
  }

  void loadCurrentDevice()
}

watch(selectedDevice, (device) => {
  if (devicePreviewUsesCaptureCard.value) {
    if (!canLoadDevicePreview.value) {
      stopDevicePreviewPolling()
      clearDevicePreview()
      return
    }

    if (!devicePreviewUrl.value && !devicePreviewInteractionLocked.value) {
      startDevicePreviewPolling()
    }
    return
  }

  if (!device && !devicePreviewUsesCaptureCard.value) {
    stopDevicePreviewPolling()
    clearDevicePreview()
    return
  }

  if (!canLoadDevicePreview.value) {
    stopDevicePreviewPolling()
    clearDevicePreview()
    return
  }

  clearDevicePreview()
  void fetchDevicePreview()
  startDevicePreviewPolling()
})

watch(devicePreviewSource, (source) => {
  const validSources = [DEVICE_PREVIEW_SOURCE_CAPTURE_CARD, DEVICE_PREVIEW_SOURCE_SCRCPY]
  const normalized = validSources.includes(source) ? source : DEVICE_PREVIEW_SOURCE_ADB
  devicePreviewSource.value = normalized

  try {
    window.localStorage.setItem(DEVICE_PREVIEW_SOURCE_STORAGE_KEY, normalized)
  } catch {}

  stopDevicePreviewPolling()
  clearDevicePreview()
  if (!canLoadDevicePreview.value) {
    return
  }

  if (devicePreviewUsesCaptureCard.value) {
    void ensureCaptureCardDevicesLoaded()
    startDevicePreviewPolling()
    return
  }

  void fetchDevicePreview()
  startDevicePreviewPolling()
})

const ensureCaptureCardDevicesLoaded = async () => {
  if (captureCardListLoaded || captureCardListLoading.value) {
    return
  }
  await loadCaptureCardDevices()
}

const loadCaptureCardDevices = async () => {
  captureCardListLoading.value = true
  captureCardError.value = ''
  try {
    const response = await fetch('/api/devices/capture-card/devices')
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.detail || t('keyMonitor.alerts.loadCaptureCardDevicesFailed'))
    }
    captureCardDevicesList.value = Array.isArray(data.devices) ? data.devices : []
    if (data.active_device && Number.isInteger(data.active_device.device_id)) {
      captureCardActiveDeviceId.value = data.active_device.device_id
    }
    captureCardListLoaded = true
  } catch (error) {
    captureCardError.value = error?.message || t('keyMonitor.alerts.loadCaptureCardDevicesFailed')
  } finally {
    captureCardListLoading.value = false
  }
}

const onCaptureCardDeviceSelectChange = async (value) => {
  const next = Number(value)
  if (!Number.isFinite(next) || next === captureCardActiveDeviceId.value) {
    return
  }
  await switchCaptureCardDevice(next)
}

const switchCaptureCardDevice = async (deviceId) => {
  captureCardSwitching.value = true
  captureCardError.value = ''
  try {
    const response = await fetch('/api/devices/capture-card/active', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: Number(deviceId) }),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.detail || t('keyMonitor.alerts.switchCaptureCardDeviceFailed'))
    }
    if (data.active_device && Number.isInteger(data.active_device.device_id)) {
      captureCardActiveDeviceId.value = data.active_device.device_id
    }
    // 切换成功立即刷新画面
    if (devicePreviewUsesCaptureCard.value) {
      stopDevicePreviewPolling()
      clearDevicePreview()
      void fetchDevicePreview()
      startDevicePreviewPolling()
    }
  } catch (error) {
    captureCardError.value = error?.message || t('keyMonitor.alerts.switchCaptureCardDeviceFailed')
  } finally {
    captureCardSwitching.value = false
  }
}

const releaseCaptureCard = async () => {
  captureCardReleasing.value = true
  captureCardError.value = ''
  try {
    const response = await fetch('/api/devices/capture-card/release', { method: 'POST' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data?.detail || t('keyMonitor.alerts.releaseCaptureCardFailed'))
    }
    // 释放后停止预览流
    stopDevicePreviewPolling()
    clearDevicePreview()
    devicePreviewSaveMessage.value = t('keyMonitor.captureCardReleased')
  } catch (error) {
    captureCardError.value = error?.message || t('keyMonitor.alerts.releaseCaptureCardFailed')
  } finally {
    captureCardReleasing.value = false
  }
}

watch(selectedTmsCaseNumber, () => {
  latestWrittenCheckPicName.value = ''
  latestWrittenExcelRowIndex.value = null
})

watch(manualCaseNumber, () => {
  latestWrittenCheckPicName.value = ''
  latestWrittenExcelRowIndex.value = null
})

// 跨页拉取当前 project + module 下的所有用例（按 size=100 迭代），缓存到全集 ref。
// 仅在搜索时按需触发，切换 project / module 会清空。
// 全集走 full 模式（含 precondition + steps），保证用户选中跨页搜索结果时
// 详情面板能立刻显示完整步骤；代价是首次拉全集略大，可接受。
// 用 tmsAllLoadingId 做代次 token：进入新一次加载 +1，旧循环检测到 id 变化立刻丢弃结果。
const loadAllTmsTestcases = async () => {
  if (!selectedTmsProjectId.value || !selectedTmsModuleValue.value) {
    console.log('[TMS All Testcases] 跳过加载: 缺少project_id或module')
    return
  }
  if (tmsAllLoaded.value) {
    console.log('[TMS All Testcases] 跳过加载: 全集已加载')
    return
  }

  console.log(`[TMS All Testcases] 开始加载全集: project=${selectedTmsProjectId.value}, module=${selectedTmsModuleValue.value}`)

  // 抢占 token：旧循环看到不再是当前代次时会自动放弃
  tmsAllLoadingId += 1
  const myLoadingId = tmsAllLoadingId
  tmsAllLoading.value = true

  try {
    const aggregatedCaseNumbers = []
    const aggregatedDetails = []
    const seenCaseNumbers = new Set()
    const seenDetailKeys = new Set()
    // 上游 TMS 安全策略：单次 size 最大 100，超过会被限流并触发安全告警，
    // 因此本地也限制为 100 与上游对齐。
    const pageSize = 100
    let page = 1
    let total = 0

    const projectIdSnapshot = selectedTmsProjectId.value
    const moduleValueSnapshot = selectedTmsModuleValue.value

    while (true) {
      console.log(`[TMS All Testcases] 加载第 ${page} 页`)
      const data = await fetchTmsPayload(
        `/api/platform-auth/testcases?project_ids=${encodeURIComponent(projectIdSnapshot)}&module=${encodeURIComponent(moduleValueSnapshot)}&size=${pageSize}&page=${page}`,
        t('keyMonitor.alerts.loadRemoteTestcasesFailed')
      )

      // race 保护：本次循环已经过期（用户切了 project / module 或重新点了搜索），直接退出
      if (myLoadingId !== tmsAllLoadingId) {
        console.log('[TMS All Testcases] 检测到新的加载请求，放弃当前加载')
        return
      }

      const pageCaseNumbers = Array.isArray(data?.case_numbers) ? data.case_numbers : []
      const pageDetails = Array.isArray(data?.testcases) ? data.testcases : []
      total = Number.isFinite(Number(data?.total)) ? Number(data.total) : total

      console.log(`[TMS All Testcases] 第 ${page} 页: 获取用例数=${pageCaseNumbers.length}, 总数=${total}`)

      pageCaseNumbers.forEach((cn) => {
        const trimmed = String(cn || '').trim()
        if (!trimmed || seenCaseNumbers.has(trimmed)) return
        seenCaseNumbers.add(trimmed)
        aggregatedCaseNumbers.push(trimmed)
      })
      pageDetails.forEach((detail) => {
        if (!detail || !detail.case_number) return
        if (seenDetailKeys.has(detail.case_number)) return
        seenDetailKeys.add(detail.case_number)
        aggregatedDetails.push(detail)
      })

      if (pageCaseNumbers.length === 0) break
      if (pageCaseNumbers.length < pageSize) break
      if (total > 0 && aggregatedCaseNumbers.length >= total) break
      // 安全上限：size=100 下最多拉 100 页（10000 条），防止上游异常时无限循环
      if (page >= 100) break
      page += 1
    }

    // 写回前再做一次代次校验，防止 break 后赶上 token 翻新
    if (myLoadingId !== tmsAllLoadingId) return

    console.log(`[TMS All Testcases] 全集加载完成: 用例数=${aggregatedCaseNumbers.length}, 详情数=${aggregatedDetails.length}`)

    tmsAllCaseNumbers.value = aggregatedCaseNumbers
    tmsAllTestcaseDetails.value = aggregatedDetails
    tmsAllLoaded.value = true
  } catch (error) {
    console.error('[TMS All Testcases] 加载失败:', error)
    if (myLoadingId !== tmsAllLoadingId) return
    tmsAllLoaded.value = false
    tmsError.value = error?.message || t('keyMonitor.alerts.loadRemoteTestcasesFailed')
  } finally {
    if (myLoadingId === tmsAllLoadingId) {
      tmsAllLoading.value = false
    }
  }
}

// 用户按回车或点搜索按钮：把当前关键字"提交"为已生效关键字。
// 模块下拉和用例编号下拉都会按这个关键字做模糊筛选；
// 用例编号搜索范围跨整个 project+module 用例全集（按需懒加载），不受当前页 size 限制。
// 不再自动选第一项 / 自动切模块，让用户从下拉里手动选。
const submitTmsSearch = async () => {
  const keyword = String(tmsCaseNumberSearch.value || '').trim()
  tmsCaseNumberSubmittedKeyword.value = keyword
  tmsCurrentPage.value = 1

  if (!keyword) return

  // 选了模块时按需把该模块的用例全集拉回来，让用例编号下拉的模糊筛选能跨页生效
  if (selectedTmsProjectId.value && selectedTmsModuleValue.value) {
    if (!tmsAllLoaded.value && !tmsAllLoading.value) {
      await loadAllTmsTestcases()
    }
  }

  // 搜索完成后自动弹出对应的下拉面板，让用户直接在筛选结果里挑选。
  // 优先弹用例编号下拉（如果有匹配），否则弹模块下拉。
  await nextTick()
  openMatchedTmsDropdown()
}

// 调用 select.showPicker() 弹出下拉。仅现代浏览器支持（Chrome 99+ / Edge / Electron 内置）。
// 浏览器不支持时降级到 focus，至少把焦点移到下拉框，便于键盘选择。
const openMatchedTmsDropdown = () => {
  let target = null
  if (filteredTmsCaseNumbers.value.length > 0 && tmsCaseNumberSelectRef.value) {
    target = tmsCaseNumberSelectRef.value
  } else if (filteredTmsModules.value.length > 0 && tmsModuleSelectRef.value) {
    target = tmsModuleSelectRef.value
  }

  if (!target) return

  try {
    if (typeof target.showPicker === 'function') {
      target.showPicker()
      return
    }
  } catch (err) {
    // 某些浏览器在没有用户手势时会抛 NotAllowedError，忽略并 fallback
  }
  if (typeof target.focus === 'function') {
    target.focus()
  }
}

const clearTmsSearchKeyword = async () => {
  tmsCaseNumberSearch.value = ''
  tmsCaseNumberSubmittedKeyword.value = ''
  tmsCurrentPage.value = 1
  await loadTmsTestcases()
}

watch(devicePreviewInteractionLocked, (locked) => {
  if (locked) {
    // 用户进入框选/已有 crop 时只停掉自动轮询。
    // 历史实现还会去抓一帧"snapshot"覆盖到画面 url 上，但这会触发 <img> 重新加载、
    // 同时 fetchDevicePreview 末尾的 resetDevicePreviewSelection() 会把刚画的选框
    // 立刻清掉——表现就是"按住左键后框选栏直接消失"。已废弃。
    stopDevicePreviewPolling()
    return
  }

  if (canLoadDevicePreview.value) {
    startDevicePreviewPolling()
  }
})

watch(devicePreviewSaveDir, (value) => {
  try {
    const normalized = String(value || '').trim()
    if (normalized) {
      window.localStorage.setItem(DEVICE_PREVIEW_SAVE_DIR_STORAGE_KEY, normalized)
    } else {
      window.localStorage.removeItem(DEVICE_PREVIEW_SAVE_DIR_STORAGE_KEY)
    }
  } catch {}
})

watch(ttsModeEnabled, (enabled) => {
  try {
    window.localStorage.setItem(KEY_MONITOR_TTS_MODE_STORAGE_KEY, enabled ? '1' : '0')
  } catch {}
})

onMounted(async () => {
  window.addEventListener(DEVICE_STATUS_EVENT, handleDeviceStatusChange)
  try {
    devicePreviewSaveDir.value = window.localStorage.getItem(DEVICE_PREVIEW_SAVE_DIR_STORAGE_KEY) || ''
    const storedPreviewSource = window.localStorage.getItem(DEVICE_PREVIEW_SOURCE_STORAGE_KEY) || ''
    const validStoredSources = [DEVICE_PREVIEW_SOURCE_CAPTURE_CARD, DEVICE_PREVIEW_SOURCE_SCRCPY]
    devicePreviewSource.value = validStoredSources.includes(storedPreviewSource)
      ? storedPreviewSource
      : DEVICE_PREVIEW_SOURCE_ADB
    ttsModeEnabled.value = window.localStorage.getItem(KEY_MONITOR_TTS_MODE_STORAGE_KEY) === '1'
  } catch {}
  await loadCurrentDevice()
  await loadCorrectionRules()
  await loadExcelFiles()
  await loadTmsProjects()
  if (devicePreviewSource.value === DEVICE_PREVIEW_SOURCE_CAPTURE_CARD) {
    void ensureCaptureCardDevicesLoaded()
  }
  startStatusPolling()
})

onBeforeUnmount(() => {
  stopStatusPolling()
  stopDevicePreviewPolling()
  window.removeEventListener(DEVICE_STATUS_EVENT, handleDeviceStatusChange)
})

const loadCurrentDevice = async () => {
  try {
    const response = await fetch('/api/devices/current')
    const data = await response.json()
    selectedDevice.value = data.device
  } catch {
    selectedDevice.value = ''
  }
}

const loadTmsProjects = async () => {
  console.log('[TMS Projects] 开始加载项目列表')
  tmsLoadingProjects.value = true
  tmsError.value = ''

  try {
    const data = await fetchTmsPayload('/api/platform-auth/projects', t('keyMonitor.alerts.loadRemoteProjectsFailed'))
    tmsProjects.value = Array.isArray(data.projects) ? data.projects : []
    console.log(`[TMS Projects] 加载成功: 项目数=${tmsProjects.value.length}`)

    if (!tmsProjects.value.some(project => String(project.id) === selectedTmsProjectId.value)) {
      selectedTmsProjectId.value = ''
      tmsModules.value = []
      selectedTmsModuleValue.value = ''
      resetTmsSearchAndResults()
    }
  } catch (error) {
    console.error('[TMS Projects] 加载失败:', error)
    tmsProjects.value = []
    selectedTmsProjectId.value = ''
    tmsModules.value = []
    selectedTmsModuleValue.value = ''
    resetTmsSearchAndResults()
    tmsError.value = error.message || t('keyMonitor.alerts.loadRemoteProjectsFailed')
  } finally {
    tmsLoadingProjects.value = false
  }
}

const loadTmsModules = async () => {
  if (!selectedTmsProjectId.value) {
    console.log('[TMS Modules] 跳过加载: 缺少project_id')
    tmsModules.value = []
    selectedTmsModuleValue.value = ''
    resetTmsSearchAndResults()
    return
  }

  console.log(`[TMS Modules] 开始加载模块列表: project=${selectedTmsProjectId.value}`)
  tmsLoadingModules.value = true
  tmsError.value = ''
  try {
    const data = await fetchTmsPayload(
      `/api/platform-auth/modules?project_ids=${encodeURIComponent(selectedTmsProjectId.value)}`,
      t('keyMonitor.alerts.loadRemoteModulesFailed')
    )
    tmsModules.value = Array.isArray(data.modules) ? data.modules : []
    console.log(`[TMS Modules] 加载成功: 模块数=${tmsModules.value.length}`)

    if (!tmsModules.value.some(moduleItem => moduleItem?.value === selectedTmsModuleValue.value)) {
      selectedTmsModuleValue.value = ''
    }
    clearTmsTestcaseResults()
  } catch (error) {
    console.error('[TMS Modules] 加载失败:', error)
    tmsModules.value = []
    selectedTmsModuleValue.value = ''
    resetTmsSearchAndResults()
    tmsError.value = error.message || t('keyMonitor.alerts.loadRemoteModulesFailed')
  } finally {
    tmsLoadingModules.value = false
  }
}

const handleTmsProjectChange = async () => {
  selectedTmsModuleValue.value = ''
  tmsModules.value = []
  tmsError.value = ''
  tmsCurrentPage.value = 1
  resetTmsSearchAndResults()
  await loadTmsModules()
}

const handleTmsModuleChange = async () => {
  tmsError.value = ''
  tmsCurrentPage.value = 1
  // 切模块时保留搜索关键字：用户可能在用关键字筛模块和用例下拉。
  clearTmsTestcaseResults()
  await maybeLoadTmsTestcases()
  // 切完模块后，如果搜索框里还有已生效的关键字，按需把新模块的用例全集拉回来，
  // 用例编号下拉就能基于新模块继续做模糊筛选。
  if (
    tmsCaseNumberSubmittedKeyword.value
    && selectedTmsProjectId.value
    && selectedTmsModuleValue.value
    && !tmsAllLoaded.value
    && !tmsAllLoading.value
  ) {
    await loadAllTmsTestcases()
  }
}

const handleTmsPageSizeChange = async () => {
  normalizeTmsPageSize()
  tmsError.value = ''
  tmsCurrentPage.value = 1

  // 搜索模式下数据已全量加载，切换页大小只需重置页码（客户端分页）
  const keyword = String(tmsCaseNumberSubmittedKeyword.value || '').trim().toLowerCase()
  if (keyword) return

  await maybeLoadTmsTestcases()
}

const goTmsPage = async (page) => {
  const p = Math.max(1, Math.min(page, tmsTotalPages.value))
  if (p === tmsCurrentPage.value) return
  tmsCurrentPage.value = p

  // 搜索模式下数据已全量加载，只需切换页码即可（客户端分页）
  const keyword = String(tmsCaseNumberSubmittedKeyword.value || '').trim().toLowerCase()
  if (keyword) return

  await loadTmsTestcases()
}

const jumpTmsPage = (event) => {
  const target = Number(event?.target?.value)
  if (!Number.isFinite(target)) return
  goTmsPage(Math.trunc(target))
}

const loadTmsTestcases = async () => {
  if (!selectedTmsProjectId.value || !selectedTmsModuleValue.value) {
    console.log('[TMS Testcases] 跳过加载: 缺少project_id或module')
    return
  }

  console.log(`[TMS Testcases] 开始加载: project=${selectedTmsProjectId.value}, module=${selectedTmsModuleValue.value}, page=${tmsCurrentPage.value}, size=${tmsPageSize.value}`)

  tmsLoadingTestcases.value = true
  tmsError.value = ''
  // 仅清当前页相关数据，保留搜索全集（换页 / 改 size 时不该让搜索状态失效）
  clearTmsTestcaseResults({ clearAll: false })

  try {
    const normalizedSize = normalizeTmsPageSize()
    const url = `/api/platform-auth/testcases?project_ids=${encodeURIComponent(selectedTmsProjectId.value)}&module=${encodeURIComponent(selectedTmsModuleValue.value)}&size=${normalizedSize}&page=${tmsCurrentPage.value}`
    console.log(`[TMS Testcases] 请求URL: ${url}`)

    const data = await fetchTmsPayload(url, t('keyMonitor.alerts.loadRemoteTestcasesFailed'))

    tmsCaseNumbers.value = Array.isArray(data.case_numbers) ? data.case_numbers : []
    tmsTestcaseDetails.value = Array.isArray(data.testcases) ? data.testcases : []

    console.log(`[TMS Testcases] 加载成功: 用例数=${tmsCaseNumbers.value.length}, 总数=${data.total}`)

    if (!tmsCaseNumbers.value.includes(selectedTmsCaseNumber.value)) {
      selectedTmsCaseNumber.value = ''
    }
    tmsTotal.value = Number.isFinite(Number(data.total)) ? Number(data.total) : tmsCaseNumbers.value.length
  } catch (error) {
    console.error('[TMS Testcases] 加载失败:', error)
    clearTmsTestcaseResults({ clearAll: false })
    tmsError.value = error.message || t('keyMonitor.alerts.loadRemoteTestcasesFailed')
  } finally {
    tmsLoadingTestcases.value = false
  }
}

const loadExcelFiles = async () => {
  excelLoadingFiles.value = true
  clearExcelImportStatus()
  try {
    const response = await fetch('/api/excel/files')
    if (!response.ok) {
      throw new Error(t('keyMonitor.alerts.loadExcelFilesFailed'))
    }
    const data = await response.json()
    excelFiles.value = Array.isArray(data.files) ? data.files : []

    if (selectedExcelFile.value && !excelFiles.value.includes(selectedExcelFile.value)) {
      selectedExcelFile.value = ''
      excelRows.value = []
    }
  } catch (error) {
    excelImportError.value = error.message || t('keyMonitor.alerts.loadExcelFilesFailed')
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
      throw new Error(data.detail || t('keyMonitor.alerts.readExcelFailed'))
    }

    const data = await response.json()
    excelRows.value = Array.isArray(data.valid_rows) ? data.valid_rows : []

    if (excelRows.value.length === 0) {
      excelImportError.value = t('keyMonitor.alerts.noValidRows')
      return
    }
  } catch (error) {
    excelRows.value = []
    excelImportError.value = error.message || t('keyMonitor.alerts.readExcelFailed')
  } finally {
    excelLoadingRows.value = false
  }
}

const handleExcelFileChange = async () => {
  excelRows.value = []
  latestWrittenExcelRowIndex.value = null
  caseWriteCounts.value = {}
  clearExcelImportStatus()
  await analyzeSelectedExcel()
}

const {
  uploadConfirmVisible,
  requestUpload: requestUploadExcelConfirm,
  confirmUpload,
  cancelUpload,
} = useUploadExcelConfirm()

const handleUploadExcelClick = () => {
  if (excelUploading.value) return
  requestUploadExcelConfirm(() => {
    excelUploadInput.value?.click()
  })
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
      throw new Error(data.detail || t('keyMonitor.alerts.uploadExcelFailed'))
    }

    excelImportMessage.value = data.message || t('keyMonitor.alerts.uploadExcelSuccess')
    await loadExcelFiles()
    selectedExcelFile.value = data.filename || file.name
    await analyzeSelectedExcel()
  } catch (error) {
    excelImportError.value = error.message || t('keyMonitor.alerts.uploadExcelFailed')
  } finally {
    if (event.target) {
      event.target.value = ''
    }
    excelUploading.value = false
  }
}

const stopStatusPolling = () => {
  if (statusTimer) {
    clearTimeout(statusTimer)
    statusTimer = null
  }
  statusPollingRequestActive = false
}

const startStatusPolling = () => {
  if (statusTimer) {
    return
  }

  // 自适应轮询频率：监听中 200ms 保持实时；未监听 5s 一次降低请求噪音。
  // 用 setTimeout 递归而不是 setInterval，每次结束时根据最新状态决定下一次的间隔。
  const tick = async () => {
    statusTimer = null
    if (statusPollingRequestActive) {
      // 还在请求中（理论上不会发生，因为 tick 自己会等 fetch 结束）
      // 直接重排下一次
      const interval = keyMonitorActive.value ? 200 : 5000
      statusTimer = setTimeout(tick, interval)
      return
    }

    statusPollingRequestActive = true
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
        keyMonitorError.value = t('keyMonitor.alerts.apiUnavailable')
        stopStatusPolling()
        return
      }
    } catch {
    } finally {
      statusPollingRequestActive = false
    }

    // 排下一次：监听中跑 200ms，未监听跑 5s
    const interval = keyMonitorActive.value ? 200 : 5000
    statusTimer = setTimeout(tick, interval)
  }

  tick()
}

const startKeyMonitor = async () => {
  startStatusPolling()
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
      keyMonitorError.value = data?.detail || t('keyMonitor.alerts.startFailed')
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
      throw new Error(t('keyMonitor.alerts.loadMappingsFailed'))
    }
    const data = await res.json()
    applySchemeResponse(data)
    const mappings = savedMappings.value
    keyMonitorSequence.value = applyCorrectionMappingsToSequence(keyMonitorSequence.value, mappings)
    editableSequence.value = applyCorrectionMappingsToSequence(editableSequence.value, mappings)
    sequenceDirty.value = editableSequence.value !== keyMonitorSequence.value
    mappingError.value = ''
  } catch (error) {
    mappingError.value = error.message || t('keyMonitor.alerts.loadMappingsFailed')
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

const stopMonitorForWrite = async () => {
  if (!keyMonitorActive.value && !isStarting.value) {
    return normalizeCommandSequence(workingSequence.value)
  }

  const res = await fetch('/api/keymonitor/stop', { method: 'POST' })
  const data = await res.json().catch(() => ({}))

  if (!res.ok) {
    throw new Error(data.detail || t('keyMonitor.alerts.writeFailed'))
  }

  keyMonitorActive.value = false
  isStarting.value = false

  const finalizedSequence = applyCorrectionMappingsToSequence(data.sequence || '')
  syncCapturedSequence(finalizedSequence)
  return normalizeCommandSequence(finalizedSequence)
}

const clearMonitorContent = async () => {
  try {
    await fetch('/api/keymonitor/clear', { method: 'POST' })
  } catch {}

  syncCapturedSequence('')
  keyMonitorError.value = ''
}

const copySequence = async () => {
  if (keyMonitorActive.value || isStarting.value) {
    await alert(t('keyMonitor.alerts.copyBlocked'))
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
    await alert(t('keyMonitor.alerts.copySuccess'))
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

// 弹窗让用户确认/修改 assert 格式，返回用户选择的格式字符串（取消则返回 null）
const promptAssertFormat = (defaultFormat = 'Assert/1/1') => {
  return new Promise((resolve) => {
    assertModalFormat.value = defaultFormat
    assertModalVisible.value = true
    assertModalResolve.value = resolve
  })
}

// 向后端查询指定 case 在 Excel 中的当前状态（是否存在、assert 次数等）
const fetchCaseState = async (fileName, caseNumber) => {
  if (!fileName || !caseNumber) return null
  try {
    const resp = await fetch(`/api/excel/case_state?file_name=${encodeURIComponent(fileName)}&case_number=${encodeURIComponent(caseNumber)}`)
    if (!resp.ok) return null
    return await resp.json()
  } catch {
    return null
  }
}

// 在脚本末尾插入/覆盖 Assert 指令，直接写入 Excel
const insertAssertToSequence = async () => {
  if (!selectedExcelFile.value) {
    excelImportError.value = t('keyMonitor.alerts.selectExcelFirst')
    return
  }
  if (!effectiveCaseNumber.value) {
    excelImportError.value = t('keyMonitor.alerts.selectCaseFirst')
    return
  }

  // 如果正在监控，先停止
  if (keyMonitorActive.value || isStarting.value) {
    await stopMonitorForWrite()
  }

  const assertFormat = await promptDirectAssertFormat('Assert/1/1')
  if (assertFormat === null) return

  try {
    const resp = await fetch('/api/excel/append_assert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_name: selectedExcelFile.value,
        case_number: effectiveCaseNumber.value,
        assert_format: assertFormat,
      })
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(data.detail || t('keyMonitor.alerts.writeFailed'))

    excelImportError.value = ''
    excelImportMessage.value = data.message || t('keyMonitor.alerts.writeSuccess', { file: selectedExcelFile.value })
    if (selectedExcelFile.value) await analyzeSelectedExcel()
  } catch (e) {
    excelImportError.value = e.message || t('keyMonitor.alerts.writeFailed')
  }
}

const confirmAssertModal = () => {
  const format = assertModalFormat.value.trim() || 'Assert/1/1'
  assertModalVisible.value = false
  if (assertModalResolve.value) {
    assertModalResolve.value(format)
    assertModalResolve.value = null
  }
}

const cancelAssertModal = () => {
  assertModalVisible.value = false
  if (assertModalResolve.value) {
    assertModalResolve.value(null)
    assertModalResolve.value = null
  }
}

// 直接写入 Assert 的弹窗逻辑
const promptDirectAssertFormat = (defaultFormat = 'Assert/1/1') => {
  return new Promise((resolve) => {
    directAssertModalFormat.value = defaultFormat
    directAssertModalVisible.value = true
    directAssertModalResolve.value = resolve
  })
}

const confirmDirectAssertModal = async () => {
  const format = directAssertModalFormat.value.trim()
  // 用户输入为空则显示警告，不允许为空
  if (!format) {
    await alert(t('keyMonitor.directAssertModal.emptyWarning'))
    return
  }
  directAssertModalVisible.value = false
  if (directAssertModalResolve.value) {
    directAssertModalResolve.value(format)
    directAssertModalResolve.value = null
  }
}

const cancelDirectAssertModal = () => {
  directAssertModalVisible.value = false
  if (directAssertModalResolve.value) {
    directAssertModalResolve.value(null)
    directAssertModalResolve.value = null
  }
}

const saveSequenceToExcel = async () => {
  const shouldResumeMonitoring = keyMonitorActive.value || isStarting.value

  if (!selectedExcelFile.value) {
    excelImportError.value = t('keyMonitor.alerts.selectExcelFirst')
    return
  }
  if (!normalizeCommandSequence(workingSequence.value)) {
    excelImportError.value = t('keyMonitor.alerts.noWritableSequence')
    return
  }

  try {
    const sequence = buildSequenceForExcelWrite(await stopMonitorForWrite())

    // 如果需要恢复监听，立即设置状态，避免按钮闪烁
    if (shouldResumeMonitoring) {
      isStarting.value = true
    }

    if (!sequence) {
      throw new Error(t('keyMonitor.alerts.noWritableSequence'))
    }

    // 根据 Assert/TTS 模式决定写入逻辑
    const currentCaseKey = effectiveCaseNumber.value || ''
    let assertFormat = undefined

    if (assertModeEnabled.value) {
      // Assert 模式激活：弹出 Assert 弹窗，允许多次写入
      assertFormat = await promptDirectAssertFormat('Assert/1/1')

      // 用户取消则不写入
      if (assertFormat === null) {
        if (shouldResumeMonitoring) {
          await startKeyMonitor()
        }
        return
      }

      // 用户输入为空则不插入 Assert（assertFormat 保持 undefined）
      if (!assertFormat || assertFormat.trim() === '') {
        assertFormat = undefined
      }

      // 更新缓存
      const previousCount = caseWriteCounts.value[currentCaseKey] || 0
      caseWriteCounts.value = { ...caseWriteCounts.value, [currentCaseKey]: previousCount + 1 }
    } else if (ttsModeEnabled.value) {
      // TTS 模式激活：允许多次写入同一 caseID（每次自动插入 TTS 标记）
      const previousCount = caseWriteCounts.value[currentCaseKey] || 0
      caseWriteCounts.value = { ...caseWriteCounts.value, [currentCaseKey]: previousCount + 1 }
    } else {
      // Assert/TTS 模式均未激活：不允许重复写入同一 caseID
      const previousCount = caseWriteCounts.value[currentCaseKey] || 0
      if (previousCount >= 1) {
        throw new Error(t('keyMonitor.alerts.caseAlreadyWritten'))
      }
      caseWriteCounts.value = { ...caseWriteCounts.value, [currentCaseKey]: 1 }
    }

    // 构建本次写入的 preScript 片段
    let prescriptSegment = sequence
    if (assertFormat) {
      prescriptSegment = `${sequence},${assertFormat}`
    }

    // 计算本次的 checkPoint 片段
    const assertCount = assertFormat ? parseInt(assertFormat.split('/')[1]) || 1 : 0
    const checkPointSegment = assertCount > 0 ? Array(assertCount).fill('(1,1)').join(',') : '(1,1)'

    // 计算本次的 checkPic 片段
    const caseStem = currentCaseKey || 'screenshot'
    let checkPicSegment = ''
    if (assertCount > 0) {
      // 查找已存在的记录，确定当前已有多少张图片
      const existingIndex = pendingWriteList.value.findIndex(item => item.case_number === (currentCaseKey || undefined))
      const existingCheckPic = existingIndex >= 0 ? pendingWriteList.value[existingIndex].checkPic : ''
      const existingCount = existingCheckPic ? existingCheckPic.split(',').filter(p => p.trim()).length : 0
      const newPics = []
      for (let i = 0; i < assertCount; i++) {
        const idx = existingCount + i
        newPics.push(idx === 0 ? `${caseStem}.png` : `${caseStem}-${idx}.png`)
      }
      checkPicSegment = newPics.join(',')
    } else {
      checkPicSegment = `${caseStem}.png`
    }

    // 查找是否已存在同一 caseID 的记录
    const existingIndex = pendingWriteList.value.findIndex(item => item.case_number === (currentCaseKey || undefined))

    if (existingIndex >= 0) {
      // 追加到已存在的记录
      const existing = pendingWriteList.value[existingIndex]
      existing.preScript = existing.preScript
        ? `${existing.preScript},${prescriptSegment}`
        : prescriptSegment
      existing.checkPic = existing.checkPic
        ? `${existing.checkPic},${checkPicSegment}`
        : checkPicSegment
      existing.checkPoint = existing.checkPoint
        ? `${existing.checkPoint},${checkPointSegment}`
        : checkPointSegment
      // sequence 和 assert_format 保持最新的
      existing.sequence = sequence
      existing.assert_format = assertFormat || undefined
      excelImportMessage.value = t('keyMonitor.alerts.updatedInPendingWrite')
    } else {
      // 添加新记录
      pendingWriteList.value.push({
        file_name: selectedExcelFile.value,
        testID: currentCaseKey || '',
        preScript: prescriptSegment,
        checkPic: checkPicSegment,
        checkPoint: checkPointSegment,
        sequence: sequence,
        case_number: currentCaseKey || undefined,
        assert_format: assertFormat || undefined,
      })
      excelImportMessage.value = t('keyMonitor.alerts.addedToPendingWrite')
    }

    await clearMonitorContent()

    excelImportError.value = ''

    // 自动恢复监听
    if (shouldResumeMonitoring) {
      await startKeyMonitor()
    }
  } catch (error) {
    excelImportError.value = error.message || t('keyMonitor.alerts.writeFailed')
  }
}

// 删除待写入列表中的某一项
const removePendingWriteItem = (index) => {
  pendingWriteList.value.splice(index, 1)
}

// 编辑待写入列表中的某一项
const onPendingItemEdit = (index, field, value) => {
  const item = pendingWriteList.value[index]
  if (!item) return

  // 更新字段值
  item[field] = value

  // 如果编辑的是 preScript，需要重新解析并更新 checkPoint
  if (field === 'preScript') {
    // 解析 preScript 中所有 Assert 的 x 值之和
    const parts = value.split(',')
    let totalAssertCount = 0

    for (const part of parts) {
      const trimmed = part.trim()
      const match = trimmed.match(/^Assert\/(\d+)\/\d+$/)
      if (match) {
        totalAssertCount += parseInt(match[1]) || 0
      }
    }

    // 重新计算 checkPoint
    if (totalAssertCount > 0) {
      item.checkPoint = Array(totalAssertCount).fill('(1,1)').join(',')
    } else {
      item.checkPoint = '(1,1)'
    }
  }

  // 如果编辑的是 case_number（通过 testID），需要更新 case_number
  if (field === 'testID') {
    item.case_number = value || undefined
  }
}

// 自动调整 textarea 高度
const autoResizeTextarea = (event) => {
  const textarea = event.target
  textarea.style.height = 'auto'
  textarea.style.height = textarea.scrollHeight + 'px'
}

// 监听 pendingWriteList 变化，自动调整 textarea 高度
watch(pendingWriteList, () => {
  nextTick(() => {
    const textareas = document.querySelectorAll('.pending-write-table textarea')
    textareas.forEach(textarea => {
      textarea.style.height = 'auto'
      textarea.style.height = textarea.scrollHeight + 'px'
    })
  })
}, { deep: true })

// 一键写入所有待写入的数据
const flushPendingWriteList = async () => {
  if (pendingWriteList.value.length === 0) return

  pendingWriteLoading.value = true
  excelSavingSequence.value = true
  stopStatusPolling()
  clearExcelImportStatus()

  let successCount = 0
  let failCount = 0
  const failedItems = []

  try {
    for (const item of pendingWriteList.value) {
      try {
        const response = await fetch('/api/excel/append_sequence', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_name: item.file_name,
            sequence: item.preScript,
            case_number: item.case_number,
            check_pic: item.checkPic,
            check_point: item.checkPoint,
          })
        })

        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
          throw new Error(data.detail || t('keyMonitor.alerts.writeFailed'))
        }

        successCount++
      } catch (error) {
        failCount++
        failedItems.push(item)
        console.error('Write failed:', error)
      }
    }

    if (selectedExcelFile.value) {
      await analyzeSelectedExcel()
    }

    // 只保留失败的项目，成功写入的移除
    pendingWriteList.value = failedItems
    // 只有全部成功时才清空计数
    if (failCount === 0) {
      caseWriteCounts.value = {}
    }

    excelImportError.value = ''
    if (failCount === 0) {
      excelImportMessage.value = t('keyMonitor.alerts.writeAllSuccess', { count: successCount })
    } else if (successCount === 0) {
      excelImportError.value = t('keyMonitor.alerts.writeFailed')
    } else {
      excelImportMessage.value = t('keyMonitor.alerts.writePartialSuccess', { success: successCount, failed: failCount })
    }
  } catch (error) {
    excelImportError.value = error.message || t('keyMonitor.alerts.writeFailed')
  } finally {
    pendingWriteLoading.value = false
    excelSavingSequence.value = false
    startStatusPolling()
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
      throw new Error(data?.message || data?.detail || t('keyMonitor.alerts.saveRuleFailed'))
    }

    savedMappings.value = data.mappings || {}
    validMonitorTargets.value = (data.valid_targets && data.valid_targets.length > 0)
      ? data.valid_targets
      : defaultValidMonitorKeys
    if (data.active_scheme || data.schemes) {
      applySchemeResponse(data, { syncSavedMappings: false })
    }
    keyMonitorSequence.value = data.latest_sequence || replaceCommandInSequence(keyMonitorSequence.value, sourceKey, targetKey)
    editableSequence.value = replaceCommandInSequence(editableSequence.value, sourceKey, targetKey)
    sequenceDirty.value = editableSequence.value !== keyMonitorSequence.value
    replaceSourceKey.value = ''
    replaceTargetKey.value = ''
    mappingError.value = ''
  } catch (error) {
    mappingError.value = error.message || t('keyMonitor.alerts.saveRuleFailed')
  } finally {
    savingMapping.value = false
  }
}

const removeCorrectionRule = async (sourceKey) => {
  try {
    const res = await fetch(`/api/keymonitor/mappings/${encodeURIComponent(sourceKey)}`, { method: 'DELETE' })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || data.success === false) {
      throw new Error(data?.message || data?.detail || t('keyMonitor.alerts.deleteRuleFailed'))
    }
    savedMappings.value = data.mappings || {}
    if (data.active_scheme || data.schemes) {
      applySchemeResponse(data, { syncSavedMappings: false })
    }
    mappingError.value = ''
  } catch (error) {
    mappingError.value = error.message || t('keyMonitor.alerts.deleteRuleFailed')
  }
}

// ───────────────────── 纠错规则方案管理 ─────────────────────

function applySchemeResponse(data, { syncSavedMappings = true } = {}) {
  if (syncSavedMappings) {
    savedMappings.value = data.mappings || {}
  }
  validMonitorTargets.value = (data.valid_targets && data.valid_targets.length > 0)
    ? data.valid_targets
    : defaultValidMonitorKeys
  if (typeof data.active_scheme === 'string') {
    activeMappingSchemeName.value = data.active_scheme
  }
  if (Array.isArray(data.schemes)) {
    mappingSchemesList.value = data.schemes
  }
}

const activateMappingScheme = async (name) => {
  if (!name || schemeBusy.value || name === activeMappingSchemeName.value) {
    return
  }
  schemeBusy.value = true
  schemeError.value = ''
  try {
    const res = await fetch(`/api/keymonitor/mapping-schemes/${encodeURIComponent(name)}/activate`, {
      method: 'PUT'
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(data?.detail || t('keyMonitor.schemes.alerts.activateFailed'))
    }
    applySchemeResponse(data)
    keyMonitorSequence.value = applyCorrectionMappingsToSequence(keyMonitorSequence.value)
    editableSequence.value = applyCorrectionMappingsToSequence(editableSequence.value)
    sequenceDirty.value = editableSequence.value !== keyMonitorSequence.value
  } catch (error) {
    schemeError.value = error.message || t('keyMonitor.schemes.alerts.activateFailed')
  } finally {
    schemeBusy.value = false
  }
}

const openCreateSchemeModal = () => {
  schemeModalKind.value = 'create'
  schemeModalInput.value = ''
  schemeModalError.value = ''
  schemeModalTargetName.value = ''
  void nextTick(() => schemeModalInputRef.value?.focus())
}

const openRenameSchemeModal = () => {
  if (!activeMappingSchemeName.value) return
  schemeModalKind.value = 'rename'
  schemeModalInput.value = activeMappingSchemeName.value
  schemeModalError.value = ''
  schemeModalTargetName.value = activeMappingSchemeName.value
  void nextTick(() => schemeModalInputRef.value?.focus())
}

const openDuplicateSchemeModal = () => {
  if (!activeMappingSchemeName.value) return
  schemeModalKind.value = 'duplicate'
  schemeModalInput.value = `${activeMappingSchemeName.value}-copy`
  schemeModalError.value = ''
  schemeModalTargetName.value = activeMappingSchemeName.value
  void nextTick(() => schemeModalInputRef.value?.focus())
}

const confirmDeleteScheme = () => {
  if (!activeMappingSchemeName.value || mappingSchemesList.value.length <= 1) {
    return
  }
  schemeModalKind.value = 'delete'
  schemeModalInput.value = ''
  schemeModalError.value = ''
  schemeModalTargetName.value = activeMappingSchemeName.value
}

const closeSchemeModal = () => {
  schemeModalKind.value = ''
  schemeModalInput.value = ''
  schemeModalError.value = ''
  schemeModalTargetName.value = ''
  pendingImportFile.value = null
  pendingImportPayload.value = null
  pendingImportConflict.value = 'rename'
}

const submitSchemeModal = async () => {
  if (schemeBusy.value) {
    return
  }

  // import 走单独路径；其他几种 modal 都需要非空 input，但 delete 不需要
  if (schemeModalKind.value !== 'delete' && schemeModalKind.value !== 'import') {
    const trimmed = schemeModalInput.value.trim()
    if (!trimmed) {
      schemeModalError.value = t('keyMonitor.schemes.alerts.nameRequired')
      return
    }
  }
  if (schemeModalKind.value === 'import' && pendingImportNeedsName.value && !schemeModalInput.value.trim()) {
    schemeModalError.value = t('keyMonitor.schemes.alerts.nameRequired')
    return
  }

  schemeBusy.value = true
  schemeModalError.value = ''
  try {
    let res
    let data = {}
    const trimmedName = schemeModalInput.value.trim()
    switch (schemeModalKind.value) {
      case 'create':
        res = await fetch('/api/keymonitor/mapping-schemes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: trimmedName })
        })
        data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data?.detail || t('keyMonitor.schemes.alerts.createFailed'))
        }
        applySchemeResponse(data)
        // 创建完直接激活到新方案，方便用户立刻编辑
        await activateMappingScheme(trimmedName)
        break

      case 'rename':
        res = await fetch(`/api/keymonitor/mapping-schemes/${encodeURIComponent(schemeModalTargetName.value)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_name: trimmedName })
        })
        data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data?.detail || t('keyMonitor.schemes.alerts.renameFailed'))
        }
        applySchemeResponse(data)
        break

      case 'duplicate':
        res = await fetch(`/api/keymonitor/mapping-schemes/${encodeURIComponent(schemeModalTargetName.value)}/duplicate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_name: trimmedName })
        })
        data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data?.detail || t('keyMonitor.schemes.alerts.duplicateFailed'))
        }
        applySchemeResponse(data)
        await activateMappingScheme(trimmedName)
        break

      case 'delete':
        res = await fetch(`/api/keymonitor/mapping-schemes/${encodeURIComponent(schemeModalTargetName.value)}`, {
          method: 'DELETE'
        })
        data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data?.detail || t('keyMonitor.schemes.alerts.deleteFailed'))
        }
        applySchemeResponse(data)
        keyMonitorSequence.value = applyCorrectionMappingsToSequence(keyMonitorSequence.value)
        editableSequence.value = applyCorrectionMappingsToSequence(editableSequence.value)
        sequenceDirty.value = editableSequence.value !== keyMonitorSequence.value
        break

      case 'import': {
        const formData = new FormData()
        formData.append('file', pendingImportFile.value)
        formData.append('conflict', pendingImportConflict.value)
        if (trimmedName) {
          formData.append('scheme_name', trimmedName)
        }
        res = await fetch('/api/keymonitor/mapping-schemes/import', {
          method: 'POST',
          body: formData,
        })
        data = await res.json().catch(() => ({}))
        if (!res.ok) {
          throw new Error(data?.detail || t('keyMonitor.schemes.alerts.importFailed'))
        }
        applySchemeResponse(data)
        // 给用户一段反馈，说明导入了哪些方案
        const summary = []
        if (Array.isArray(data.imported) && data.imported.length) summary.push(t('keyMonitor.schemes.alerts.importSummaryImported', { names: data.imported.join('、') }))
        if (Array.isArray(data.renamed) && data.renamed.length) summary.push(t('keyMonitor.schemes.alerts.importSummaryRenamed', { names: data.renamed.map((r) => `${r.original}→${r.saved_as}`).join('、') }))
        if (Array.isArray(data.skipped) && data.skipped.length) summary.push(t('keyMonitor.schemes.alerts.importSummarySkipped', { names: data.skipped.join('、') }))
        if (summary.length) schemeError.value = summary.join('；')
        break
      }
    }
    closeSchemeModal()
  } catch (error) {
    schemeModalError.value = error.message || t('keyMonitor.schemes.alerts.requestFailed')
  } finally {
    schemeBusy.value = false
  }
}

const parseAttachmentFilename = (response, fallback) => {
  // 解析后端 Content-Disposition；优先 RFC 5987 的 filename*=UTF-8''…
  const header = response?.headers?.get?.('Content-Disposition') || ''
  const utfMatch = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch) {
    try {
      return decodeURIComponent(utfMatch[1].trim().replace(/^"|"$/g, ''))
    } catch {}
  }
  const plainMatch = header.match(/filename="?([^";]+)"?/i)
  if (plainMatch) {
    return plainMatch[1].trim()
  }
  return fallback
}

const exportActiveScheme = async () => {
  if (!activeMappingSchemeName.value) return
  schemeError.value = ''
  try {
    const res = await fetch(`/api/keymonitor/mapping-schemes/${encodeURIComponent(activeMappingSchemeName.value)}/export`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail || t('keyMonitor.schemes.alerts.exportFailed'))
    }
    const fallback = `key-monitor-${activeMappingSchemeName.value}.json`
    const filename = parseAttachmentFilename(res, fallback)
    const blob = await res.blob()
    triggerBrowserDownload(blob, filename)
  } catch (error) {
    schemeError.value = error?.message || t('keyMonitor.schemes.alerts.exportFailed')
  }
}

const exportAllSchemes = async () => {
  schemeError.value = ''
  try {
    const res = await fetch('/api/keymonitor/mapping-schemes/export-all')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data?.detail || t('keyMonitor.schemes.alerts.exportFailed'))
    }
    const filename = parseAttachmentFilename(res, 'key-monitor-all-schemes.json')
    const blob = await res.blob()
    triggerBrowserDownload(blob, filename)
  } catch (error) {
    schemeError.value = error?.message || t('keyMonitor.schemes.alerts.exportFailed')
  }
}

const triggerBrowserDownload = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const triggerSchemeImport = () => {
  schemeError.value = ''
  // 重置 input 的 value，保证选同一个文件也能再次触发 change
  if (schemeImportInputRef.value) {
    schemeImportInputRef.value.value = ''
  }
  schemeImportInputRef.value?.click()
}

const onSchemeImportFileChange = async (event) => {
  const file = event?.target?.files?.[0]
  if (!file) return
  schemeError.value = ''
  try {
    const text = await file.text()
    let payload
    try {
      payload = JSON.parse(text)
    } catch (parseError) {
      throw new Error(t('keyMonitor.schemes.alerts.importInvalidJson'))
    }
    pendingImportFile.value = file
    pendingImportPayload.value = payload
    pendingImportConflict.value = 'rename'
    // 扁平格式默认给一个建议名（用文件名去掉扩展名）
    if (pendingImportNeedsName.value) {
      const stem = file.name.replace(/\.json$/i, '').slice(0, 30)
      schemeModalInput.value = stem
    } else {
      schemeModalInput.value = ''
    }
    schemeModalKind.value = 'import'
    schemeModalError.value = ''
    schemeModalTargetName.value = ''
    void nextTick(() => {
      if (pendingImportNeedsName.value) {
        schemeModalInputRef.value?.focus()
      }
    })
  } catch (error) {
    schemeError.value = error?.message || t('keyMonitor.schemes.alerts.importInvalidJson')
  }
}

function compressAdjacent(seq) {
  const parts = seq.split(',').map(s => s.trim()).filter(Boolean)
  const out = []
  // 随机次数段既不作为合并源，也不作为后续数字段的合并目标
  let lastIsRandom = false
  for (const part of parts) {
    const segs = part.split('/')
    if (segs.length < 3) {
      out.push(part)
      lastIsRandom = false
      continue
    }
    const key = segs[0]
    if (/^[xX](?::\d+)?$/.test((segs[1] || '').trim())) {
      out.push(part)
      lastIsRandom = true
      continue
    }
    const cnt = parseInt(segs[1], 10) || 1
    const delay = segs[2]
    if (delay === '*' || isNaN(cnt)) {
      out.push(`${key}/${cnt}/${delay}`)
      lastIsRandom = false
      continue
    }
    const last = out.length > 0 ? out[out.length - 1] : null
    if (last && !lastIsRandom) {
      const lastSegs = last.split('/')
      if (lastSegs.length >= 3 && lastSegs[0] === key && lastSegs[2] === delay) {
        const lastCnt = parseInt(lastSegs[1], 10) || 1
        out[out.length - 1] = `${key}/${lastCnt + cnt}/${delay}`
        continue
      }
    }
    out.push(`${key}/${cnt}/${delay}`)
    lastIsRandom = false
  }
  return out.join(',')
}
</script>

<style scoped>
.key-monitor-scheme-bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px dashed rgba(146, 64, 14, 0.25);
}
.key-monitor-scheme-tabs-wrap { flex: 1; min-width: 0; }
.key-monitor-scheme-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.key-monitor-scheme-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 9999px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  color: #475569;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s, color 0.15s;
}
.key-monitor-scheme-tab:hover:not(:disabled) {
  border-color: #94a3b8;
  background: #f8fafc;
}
.key-monitor-scheme-tab:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.key-monitor-scheme-tab-active {
  border-color: #0071e3;
  background: rgba(0, 113, 227, 0.08);
  color: #0071e3;
  font-weight: 600;
}
.key-monitor-scheme-active-badge {
  display: inline-block;
  padding: 1px 6px;
  background: #dcfce7;
  color: #15803d;
  border-radius: 9999px;
  font-size: 0.66rem;
  font-weight: 700;
}
.key-monitor-scheme-count {
  display: inline-block;
  padding: 1px 6px;
  background: #f1f5f9;
  color: #64748b;
  border-radius: 9999px;
  font-size: 0.68rem;
}
.key-monitor-scheme-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.key-monitor-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.key-monitor-modal-box {
  background: #fff;
  border-radius: 16px;
  padding: 24px 28px;
  min-width: 320px;
  max-width: 440px;
  width: 100%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.18);
}
.key-monitor-modal-title {
  font-size: 1rem;
  font-weight: 700;
  margin: 0 0 4px;
}
.key-monitor-modal-body {
  margin: 10px 0 0;
  color: #4b5563;
  font-size: 0.9rem;
}
.key-monitor-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}

.key-monitor-page {
  flex: 1;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 28px 32px;
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.key-monitor-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.9) rgba(226, 232, 240, 0.72);
}

/* 桌面下让左右两列共享同一个滚动容器，避免出现"双滚动条 / sticky 不生效"问题 */
.key-monitor-scroll--split {
  display: flex;
  flex-direction: column;
}

.key-monitor-layout {
  display: flex;
  flex-direction: column;
  gap: 24px;
  align-items: stretch;
}

.key-monitor-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.key-monitor-main-body {
  display: block;
}

.key-monitor-main-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* sticky 的 aside：在 lg 及以上让设备画面"贴在视口顶部"持续可见 */
.key-monitor-aside {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.device-preview-panel--fill {
  display: flex;
  flex-direction: column;
}

@media (min-width: 1280px) {
  .key-monitor-layout {
    flex-direction: row;
    align-items: flex-start;
    gap: 18px;
  }

  .key-monitor-main {
    flex: 1 1 0;
    min-width: 0;
  }

  .key-monitor-aside {
    flex: 0 0 auto;
    /* 50vw 让画面占到接近一半屏宽，比之前 38vw 提升约 30%；
       下限 560px 保证窄屏也能看清，上限 1100px 防止超大屏过宽。 */
    width: clamp(560px, 50vw, 1100px);
    position: sticky;
    top: 0;
    align-self: flex-start;
    max-height: calc(100vh - 110px);
    display: flex;
    flex-direction: column;
    gap: 16px;
    /* 加了截图队列等控件后，aside 内总高度可能超过视口，让自身可滚动 */
    overflow-y: auto;
  }

  .device-preview-panel--fill {
    flex: 0 0 auto;
    min-height: 0;
  }

  /* 锁 16:9，frame 高度由宽度推导，画面就能彻底贴满，不再被 letterbox 吃掉。 */
  .device-preview-panel--fill .device-preview-frame {
    flex: 0 0 auto;
    width: 100%;
    aspect-ratio: 16 / 9;
    min-height: 240px;
    /* 兜底：如果用户视口非常矮，限制 frame 高度避免被挤出 aside 范围 */
    max-height: calc(100vh - 280px);
  }
}

@media (min-width: 1536px) {
  .key-monitor-aside {
    width: clamp(680px, 48vw, 1180px);
  }
}

.key-monitor-scroll::-webkit-scrollbar {
  width: 10px;
}

.key-monitor-scroll::-webkit-scrollbar-track {
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.72);
}

.key-monitor-scroll::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.9);
  background-clip: padding-box;
}

.device-preview-panel {
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.98) 0%, rgba(241, 245, 249, 0.92) 100%);
  padding: 16px;
}

.key-monitor-tts-switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  cursor: pointer;
  user-select: none;
}

.key-monitor-tts-switch__track {
  position: relative;
  width: 42px;
  height: 24px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.45);
  transition: background-color 0.2s ease;
}

.key-monitor-tts-switch__track--active {
  background: rgba(59, 130, 246, 0.9);
}

.key-monitor-tts-switch__thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.24);
  transition: transform 0.2s ease;
}

.key-monitor-tts-switch__thumb--active {
  transform: translateX(18px);
}

.device-preview-frame {
  position: relative;
  min-height: 320px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 18px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at top, rgba(59, 130, 246, 0.12), transparent 55%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.96) 0%, rgba(30, 41, 59, 0.98) 100%);
}

.device-preview-frame--selectable {
  cursor: crosshair;
  touch-action: none;
  user-select: none;
}

.device-preview-frame--selecting {
  cursor: crosshair;
}

.device-preview-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.device-preview-selection-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.device-preview-selection-box {
  position: absolute;
  border: 2px solid rgba(56, 189, 248, 0.95);
  background: rgba(56, 189, 248, 0.18);
  box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.26);
  border-radius: 8px;
}

.device-preview-state {
  padding: 24px;
  text-align: center;
  color: rgba(226, 232, 240, 0.88);
  font-size: 0.95rem;
  line-height: 1.5;
}

@media (min-width: 1280px) {
  .device-preview-panel:not(.device-preview-panel--fill) .device-preview-frame {
    min-height: 520px;
  }
}
</style>

