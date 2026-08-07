// 程序风格对话框 store（替代浏览器原生 alert / confirm / prompt）
// 返回 Promise：alert 确认后 resolve()；confirm resolve(true/false)；
// prompt resolve(输入值) / 取消 resolve(null)。
import { reactive } from 'vue'

export const dialogState = reactive({
  visible: false,
  type: 'alert', // 'alert' | 'confirm' | 'prompt'
  title: '',
  message: '',
  confirmText: '',
  cancelText: '',
  placeholder: '',
  inputValue: '',
  _resolve: null,
})

// 兼容字符串（直接作为 message）或对象两种传参，方便迁移原生 alert/confirm/prompt。
function _normalize(opts) {
  if (typeof opts === 'string') {
    return { message: opts }
  }
  return opts || {}
}

export function showAlert(opts) {
  const o = _normalize(opts)
  return _open('alert', {
    title: o.title || '',
    message: o.message || '',
    confirmText: o.confirmText || '确定',
    cancelText: '',
    placeholder: '',
    defaultValue: '',
  })
}

export function showConfirm(opts) {
  const o = _normalize(opts)
  return _open('confirm', {
    title: o.title || '',
    message: o.message || '',
    confirmText: o.confirmText || '确定',
    cancelText: o.cancelText || '取消',
    placeholder: '',
    defaultValue: '',
  })
}

export function showPrompt(opts) {
  const o = _normalize(opts)
  return _open('prompt', {
    title: o.title || '',
    message: o.message || '',
    confirmText: o.confirmText || '确定',
    cancelText: o.cancelText || '取消',
    placeholder: o.placeholder || '',
    defaultValue: o.defaultValue || '',
  })
}

function _open(type, opts) {
  return new Promise((resolve) => {
    Object.assign(dialogState, {
      visible: true,
      type,
      title: opts.title || '',
      message: opts.message || '',
      confirmText: opts.confirmText || '确定',
      cancelText: opts.cancelText || '取消',
      placeholder: opts.placeholder || '',
      inputValue: opts.defaultValue || '',
      _resolve: resolve,
    })
  })
}

export function dialogOk() {
  const resolve = dialogState._resolve
  if (!resolve) return
  if (dialogState.type === 'alert') {
    resolve()
  } else if (dialogState.type === 'confirm') {
    resolve(true)
  } else {
    resolve(dialogState.inputValue)
  }
  _close()
}

export function dialogCancel() {
  const resolve = dialogState._resolve
  if (!resolve) return
  if (dialogState.type === 'confirm') {
    resolve(false)
  } else {
    resolve(null)
  }
  _close()
}

function _close() {
  dialogState.visible = false
  dialogState._resolve = null
}
