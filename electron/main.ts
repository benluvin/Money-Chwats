import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import * as http from 'http'

app.setName('Money chWAt')

let mainWindow: BrowserWindow | null = null
let serverProcess: ChildProcess | null = null
let serverReady = false

// Herramienta personal: el servicio Python (con su venv de 358 MB y rutas
// absolutas) vive siempre en la carpeta real del proyecto. La app empaquetada
// apunta ahí en vez de copiarlo dentro del bundle.
const PROJECT_DIR = '/Users/daniel/Desktop/Money Chwats'
const ROOT = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..')
const DESKTOP_DIR = path.join(PROJECT_DIR, 'desktop')
const ASSETS_DIR = path.join(ROOT, 'assets')
const UVICORN_BIN = path.join(DESKTOP_DIR, '.venv', 'bin', 'uvicorn')
const API = 'http://127.0.0.1:5000'

function startServer() {
  serverProcess = spawn(UVICORN_BIN, ['app.main:app', '--host', '127.0.0.1', '--port', '5000'], {
    cwd: DESKTOP_DIR,
    stdio: 'pipe',
  })
  serverProcess.stdout?.on('data', (d: Buffer) => console.log('[srv]', d.toString().trimEnd()))
  serverProcess.stderr?.on('data', (d: Buffer) => console.log('[srv]', d.toString().trimEnd()))
  serverProcess.on('error', (e) => console.error('[srv] error:', e.message))
}

function waitForServer(maxMs = 20_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now()
    const check = () => {
      http.get(`${API}/health`, (res) => {
        if (res.statusCode === 200) resolve()
        else retry()
        res.resume()
      }).on('error', retry)
    }
    const retry = () => {
      if (Date.now() - start > maxMs) reject(new Error('Servidor no arrancó en tiempo'))
      else setTimeout(check, 400)
    }
    setTimeout(check, 800)
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 780,
    minWidth: 960,
    minHeight: 600,
    title: 'Money Chwats',
    icon: path.join(ASSETS_DIR, 'icon.png'),
    backgroundColor: '#1a1410',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

app.whenReady().then(async () => {
  // Ícono del Dock (macOS).
  if (process.platform === 'darwin' && app.dock) {
    app.dock.setIcon(path.join(ASSETS_DIR, 'icon.png'))
  }

  startServer()
  try {
    await waitForServer()
    serverReady = true
    console.log('[app] Servidor listo')
  } catch (e) {
    console.error('[app] Servidor no respondió:', e)
  }
  createWindow()
})

app.on('before-quit', () => {
  serverProcess?.kill('SIGTERM')
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// ── IPC handlers ──────────────────────────────────────────────────────────────

ipcMain.handle('server-ready', () => serverReady)

ipcMain.handle('get-dashboard', async () => {
  const res = await fetch(`${API}/dashboard`)
  return res.json()
})

ipcMain.handle('get-clientes', async (_e, params: Record<string, string> = {}) => {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`${API}/clientes${qs ? '?' + qs : ''}`)
  return res.json()
})

ipcMain.handle('get-pedidos', async (_e, params: Record<string, string> = {}) => {
  const qs = new URLSearchParams(params).toString()
  const res = await fetch(`${API}/pedidos${qs ? '?' + qs : ''}`)
  return res.json()
})

ipcMain.handle('select-txt', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    title: 'Seleccionar exportación de WhatsApp',
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: 'Exportación WhatsApp', extensions: ['txt', 'zip'] }],
  })
  return result.canceled ? [] : result.filePaths
})

ipcMain.handle('import-chat', async (_e, filePath: string) => {
  const res = await fetch(`${API}/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: filePath }),
  })
  return res.json()
})

ipcMain.handle('show-in-finder', async (_e, filePath: string) => {
  shell.showItemInFolder(filePath)
})

// ── Catálogo ────────────────────────────────────────────────────────────────
ipcMain.handle('get-catalogo', async () => {
  const res = await fetch(`${API}/catalogo`)
  return res.json()
})

ipcMain.handle('save-producto', async (_e, p: Record<string, string>) => {
  const res = await fetch(`${API}/catalogo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(p),
  })
  return res.json()
})

ipcMain.handle('delete-producto', async (_e, id: string) => {
  const res = await fetch(`${API}/catalogo/${encodeURIComponent(id)}`, { method: 'DELETE' })
  return res.json()
})

// ── Borrado de clientes / pedidos ─────────────────────────────────────────────
ipcMain.handle('delete-cliente', async (_e, id: string) => {
  const res = await fetch(`${API}/clientes/${encodeURIComponent(id)}`, { method: 'DELETE' })
  return res.json()
})

ipcMain.handle('delete-pedido', async (_e, id: string) => {
  const res = await fetch(`${API}/pedidos/${encodeURIComponent(id)}`, { method: 'DELETE' })
  return res.json()
})

ipcMain.handle('edit-cliente', async (_e, id: string, cambios: Record<string, string>) => {
  const res = await fetch(`${API}/clientes/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cambios),
  })
  return res.json()
})

ipcMain.handle('edit-pedido', async (_e, id: string, cambios: Record<string, string>) => {
  const res = await fetch(`${API}/pedidos/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cambios),
  })
  return res.json()
})

// ── Agenda de contactos ───────────────────────────────────────────────────────
ipcMain.handle('select-agenda', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    title: 'Seleccionar agenda de contactos',
    properties: ['openFile'],
    filters: [{ name: 'Agenda (vCard / Google CSV)', extensions: ['vcf', 'csv'] }],
  })
  return result.canceled ? null : result.filePaths[0]
})

ipcMain.handle('import-agenda', async (_e, path: string) => {
  const res = await fetch(`${API}/contactos/importar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  return res.json()
})

ipcMain.handle('get-contactos', async () => {
  const res = await fetch(`${API}/contactos`)
  return res.json()
})

ipcMain.handle('reanalizar-cliente', async (_e, id: string) => {
  const res = await fetch(`${API}/clientes/${encodeURIComponent(id)}/reanalizar`, { method: 'POST' })
  return res.json()
})
