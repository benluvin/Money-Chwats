import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('api', {
  serverReady: () => ipcRenderer.invoke('server-ready'),
  getDashboard: () => ipcRenderer.invoke('get-dashboard'),
  getClientes: (p?: Record<string, string>) => ipcRenderer.invoke('get-clientes', p ?? {}),
  getPedidos: (p?: Record<string, string>) => ipcRenderer.invoke('get-pedidos', p ?? {}),
  selectTxt: () => ipcRenderer.invoke('select-txt'),
  importChat: (path: string) => ipcRenderer.invoke('import-chat', path),
  showInFinder: (path: string) => ipcRenderer.invoke('show-in-finder', path),
})
