// 共用的"上传 Excel 前提示用户文件会生成副本"确认逻辑。
// 用户勾选"不再提示"后会写入 localStorage，下次直接跳过 modal。
import { ref } from 'vue'

const STORAGE_KEY = 'excel-upload-confirm-skip'

const readSkip = () => {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

const writeSkip = (skip) => {
  try {
    if (skip) {
      window.localStorage.setItem(STORAGE_KEY, '1')
    } else {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // localStorage 不可用就退化到当前会话
  }
}

export function useUploadExcelConfirm() {
  const visible = ref(false)
  // 用户点确认后要执行的实际"打开文件选择对话框"动作
  let pendingAction = null

  // 调用方传入"真正打开 file input 的函数"。如果用户已经勾选了"不再提示"则直接执行；
  // 否则弹出 modal，用户点确认才执行。
  const requestUpload = (action) => {
    if (typeof action !== 'function') return
    if (readSkip()) {
      action()
      return
    }
    pendingAction = action
    visible.value = true
  }

  const confirmUpload = ({ dontShowAgain } = {}) => {
    if (dontShowAgain) writeSkip(true)
    visible.value = false
    const action = pendingAction
    pendingAction = null
    if (typeof action === 'function') action()
  }

  const cancelUpload = () => {
    visible.value = false
    pendingAction = null
  }

  return {
    uploadConfirmVisible: visible,
    requestUpload,
    confirmUpload,
    cancelUpload,
  }
}
