import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('api', {
  serverReady: () => ipcRenderer.invoke('server-ready'),
  getDashboard: () => ipcRenderer.invoke('get-dashboard'),
  getClientes: (p?: Record<string, string>) => ipcRenderer.invoke('get-clientes', p ?? {}),
  getPedidos: (p?: Record<string, string>) => ipcRenderer.invoke('get-pedidos', p ?? {}),
  selectTxt: () => ipcRenderer.invoke('select-txt'),
  importChat: (path: string) => ipcRenderer.invoke('import-chat', path),
  showInFinder: (path: string) => ipcRenderer.invoke('show-in-finder', path),
  getCatalogo: () => ipcRenderer.invoke('get-catalogo'),
  saveProducto: (p: Record<string, string>) => ipcRenderer.invoke('save-producto', p),
  deleteProducto: (id: string) => ipcRenderer.invoke('delete-producto', id),
  deleteCliente: (id: string) => ipcRenderer.invoke('delete-cliente', id),
  deletePedido: (id: string) => ipcRenderer.invoke('delete-pedido', id),
  editCliente: (id: string, c: Record<string, string>) => ipcRenderer.invoke('edit-cliente', id, c),
  editPedido: (id: string, c: Record<string, string>) => ipcRenderer.invoke('edit-pedido', id, c),
  selectAgenda: () => ipcRenderer.invoke('select-agenda'),
  importAgenda: (path: string) => ipcRenderer.invoke('import-agenda', path),
  getContactos: () => ipcRenderer.invoke('get-contactos'),
  reanalizarCliente: (id: string) => ipcRenderer.invoke('reanalizar-cliente', id),
})
