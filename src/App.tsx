import { useState, useEffect, useCallback } from 'react'

declare global {
  interface Window {
    api: {
      serverReady: () => Promise<boolean>
      getDashboard: () => Promise<any>
      getClientes: (p?: Record<string, string>) => Promise<{ data: any[]; total: number }>
      getPedidos: (p?: Record<string, string>) => Promise<{ data: any[]; total: number }>
      selectTxt: () => Promise<string[]>
      importChat: (path: string) => Promise<any>
      showInFinder: (path: string) => Promise<void>
    }
  }
}

type Tab = 'clientes' | 'pedidos' | 'importar'

interface ImportLog {
  file: string
  ok: boolean
  msg: string
}

const COP = (v: string | number) => {
  const n = Number(v) || 0
  return n === 0 ? '—' : `$${n.toLocaleString('es-CO')}`
}

const fecha = (s: string) => s ? s.slice(0, 10) : '—'

const Badge = ({ val }: { val: string }) => {
  const map: Record<string, string> = {
    activo: 'badge-green', frecuente: 'badge-gold', lead: 'badge-yellow',
    pausado: 'badge-gray', perdido: 'badge-red', pagado: 'badge-green',
    pendiente: 'badge-yellow', cancelado: 'badge-red', parcial: 'badge-orange',
  }
  return <span className={`badge ${map[val?.toLowerCase()] ?? 'badge-gray'}`}>{val || '—'}</span>
}

export default function App() {
  const [tab, setTab] = useState<Tab>('clientes')
  const [dash, setDash] = useState<any>({})
  const [clientes, setClientes] = useState<any[]>([])
  const [pedidos, setPedidos] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [serverOk, setServerOk] = useState(false)
  const [importLog, setImportLog] = useState<ImportLog[]>([])
  const [importing, setImporting] = useState(false)

  // Filtros clientes
  const [cq, setCq] = useState('')
  const [cEstado, setCEstado] = useState('')
  const [cPendiente, setCPendiente] = useState(false)

  // Filtros pedidos
  const [pq, setPq] = useState('')
  const [pEstado, setPEstado] = useState('')

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const [d, c, p] = await Promise.all([
        window.api.getDashboard(),
        window.api.getClientes(),
        window.api.getPedidos(),
      ])
      setDash(d)
      setClientes(c.data ?? [])
      setPedidos(p.data ?? [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const init = async () => {
      // Esperar servidor con reintentos
      for (let i = 0; i < 30; i++) {
        try {
          const ok = await window.api.serverReady()
          if (ok) { setServerOk(true); break }
        } catch {}
        await new Promise(r => setTimeout(r, 500))
      }
      await reload()
    }
    init()
  }, [reload])

  // Pedidos esta semana
  const hoy = new Date()
  const semanaMs = 7 * 24 * 60 * 60 * 1000
  const pedidosSemana = pedidos.filter(p => {
    const d = new Date(p.fecha_pedido || '')
    return !isNaN(d.getTime()) && hoy.getTime() - d.getTime() <= semanaMs
  }).length

  // Monto del mes
  const montoMes = pedidos
    .filter(p => {
      const d = new Date(p.fecha_pedido || '')
      return !isNaN(d.getTime()) && d.getMonth() === hoy.getMonth() && d.getFullYear() === hoy.getFullYear()
    })
    .reduce((s, p) => s + (Number(p.monto_total) || 0), 0)

  // Filtros aplicados en memoria
  const clientesFiltrados = clientes.filter(c => {
    if (cq && !c.nombre?.toLowerCase().includes(cq.toLowerCase()) && !c.telefono?.includes(cq)) return false
    if (cEstado && c.estado_relacion?.toLowerCase() !== cEstado) return false
    if (cPendiente && c.multimedia_pendiente?.toUpperCase() !== 'TRUE') return false
    return true
  })

  const pedidosFiltrados = pedidos.filter(p => {
    if (pq && !p.producto_servicio?.toLowerCase().includes(pq.toLowerCase()) &&
        !p._nombre_cliente?.toLowerCase().includes(pq.toLowerCase())) return false
    if (pEstado && p.estado_pago?.toLowerCase() !== pEstado) return false
    return true
  })

  const handleImport = async () => {
    const paths = await window.api.selectTxt()
    if (!paths.length) return
    setImporting(true)
    for (const fp of paths) {
      try {
        const res = await window.api.importChat(fp)
        const nombre = fp.split('/').pop() ?? fp
        setImportLog(l => [{ file: nombre, ok: res.ok ?? true, msg: res.detail ?? res.cliente_nombre ?? 'Importado' }, ...l])
      } catch (e: any) {
        setImportLog(l => [{ file: fp.split('/').pop() ?? fp, ok: false, msg: String(e) }, ...l])
      }
    }
    setImporting(false)
    await reload()
  }

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <img src="/icon.png" alt="" className="header-icon" />
          <h1 className="header-title">Money Chwats</h1>
          <span className={`status-dot ${serverOk ? 'ok' : 'err'}`} title={serverOk ? 'Servicio activo' : 'Servicio no responde'} />
        </div>
        <button className="btn-refresh" onClick={reload} disabled={loading} title="Actualizar datos">
          {loading ? '⟳' : '↺'}
        </button>
      </header>

      {/* ── Cards ── */}
      <div className="cards">
        <Card icon="👥" label="Total clientes" value={String(dash.clientes_total ?? clientes.length)} />
        <Card icon="📦" label="Pedidos esta semana" value={String(pedidosSemana)} />
        <Card icon="💵" label="Monto del mes" value={COP(montoMes)} green />
        <Card icon="⚠️" label="Pendientes revisión" value={String(dash.clientes_requieren_revision ?? 0)} warn />
      </div>

      {/* ── Tabs ── */}
      <div className="tabs">
        {(['clientes', 'pedidos', 'importar'] as Tab[]).map(t => (
          <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t === 'clientes' ? '👥 Clientes' : t === 'pedidos' ? '📦 Pedidos' : '📥 Importar'}
          </button>
        ))}
      </div>

      {/* ── Content ── */}
      <div className="content">
        {tab === 'clientes' && (
          <>
            <div className="filters">
              <input className="filter-input" placeholder="Buscar nombre o teléfono…" value={cq} onChange={e => setCq(e.target.value)} />
              <select className="filter-select" value={cEstado} onChange={e => setCEstado(e.target.value)}>
                <option value="">Todos los estados</option>
                <option value="activo">Activo</option>
                <option value="frecuente">Frecuente</option>
                <option value="lead">Lead</option>
                <option value="pausado">Pausado</option>
                <option value="perdido">Perdido</option>
              </select>
              <label className="filter-check">
                <input type="checkbox" checked={cPendiente} onChange={e => setCPendiente(e.target.checked)} />
                Solo con multimedia pendiente
              </label>
              <span className="filter-count">{clientesFiltrados.length} resultados</span>
            </div>
            <div className="table-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Nombre</th>
                    <th>Teléfono</th>
                    <th>Última compra</th>
                    <th>Pedidos</th>
                    <th>Monto total</th>
                    <th>Estado</th>
                    <th>Etiquetas</th>
                  </tr>
                </thead>
                <tbody>
                  {clientesFiltrados.length === 0 ? (
                    <tr><td colSpan={8} className="empty">No hay clientes registrados aún</td></tr>
                  ) : clientesFiltrados.map((c, i) => (
                    <tr key={c.cliente_id ?? i} className={i % 2 === 0 ? 'row-a' : 'row-b'}>
                      <td className="rank">{i + 1}</td>
                      <td className="name">
                        {c.nombre || c.nombre_contacto || '—'}
                        {c.requiere_revision?.toUpperCase() === 'TRUE' && <span className="flag" title="Requiere revisión"> ⚠</span>}
                        {c.multimedia_pendiente?.toUpperCase() === 'TRUE' && <span className="flag media" title="Multimedia pendiente"> 🎵</span>}
                      </td>
                      <td>{c.telefono || <span className="dim">sin tel.</span>}</td>
                      <td>{fecha(c.ultimo_mensaje_fecha)}</td>
                      <td className="num">{c.total_pedidos || '0'}</td>
                      <td className="num green">{COP(c.monto_total_pedidos)}</td>
                      <td><Badge val={c.estado_relacion} /></td>
                      <td className="tags">
                        {(c.etiquetas || '').split(';').filter(Boolean).map((e: string, j: number) => (
                          <span key={j} className="tag">{e.trim()}</span>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {tab === 'pedidos' && (
          <>
            <div className="filters">
              <input className="filter-input" placeholder="Buscar cliente o producto…" value={pq} onChange={e => setPq(e.target.value)} />
              <select className="filter-select" value={pEstado} onChange={e => setPEstado(e.target.value)}>
                <option value="">Todos los estados</option>
                <option value="pagado">Pagado</option>
                <option value="pendiente">Pendiente</option>
                <option value="parcial">Parcial</option>
                <option value="cancelado">Cancelado</option>
              </select>
              <span className="filter-count">{pedidosFiltrados.length} resultados</span>
            </div>
            <div className="table-wrap">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Cliente</th>
                    <th>Producto(s)</th>
                    <th>Monto</th>
                    <th>Fecha</th>
                    <th>Estado de pago</th>
                  </tr>
                </thead>
                <tbody>
                  {pedidosFiltrados.length === 0 ? (
                    <tr><td colSpan={6} className="empty">No hay pedidos registrados aún</td></tr>
                  ) : pedidosFiltrados.map((p, i) => (
                    <tr key={p.pedido_id ?? i} className={i % 2 === 0 ? 'row-a' : 'row-b'}>
                      <td className="rank">{i + 1}</td>
                      <td className="name">{p._nombre_cliente || p.cliente_id || '—'}</td>
                      <td>{p.producto_servicio || '—'}{p.cantidad && p.cantidad !== '1' ? ` ×${p.cantidad}` : ''}</td>
                      <td className="num green">{COP(p.monto_total)}</td>
                      <td>{fecha(p.fecha_pedido)}</td>
                      <td><Badge val={p.estado_pago} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {tab === 'importar' && (
          <div className="import-panel">
            <div className="import-hero">
              <p className="import-desc">
                Exporta la conversación desde WhatsApp (Ajustes → Chats → Exportar chat → Sin multimedia) y súbela aquí.
              </p>
              <button className="btn-import" onClick={handleImport} disabled={importing}>
                {importing ? 'Procesando…' : '📂 Seleccionar archivo(s) .txt'}
              </button>
            </div>

            {importLog.length > 0 && (
              <div className="import-log">
                <h3>Historial de importaciones</h3>
                {importLog.map((l, i) => (
                  <div key={i} className={`log-row ${l.ok ? 'log-ok' : 'log-err'}`}>
                    <span className="log-icon">{l.ok ? '✓' : '✗'}</span>
                    <span className="log-file">{l.file}</span>
                    <span className="log-msg">{l.msg}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="import-stats">
              <div className="stat-row"><span>Clientes con teléfono pendiente</span><b>{dash.clientes_telefono_pendiente ?? 0}</b></div>
              <div className="stat-row"><span>Clientes con multimedia pendiente</span><b>{dash.clientes_multimedia_pendiente ?? 0}</b></div>
              <div className="stat-row"><span>Audios omitidos (total)</span><b>{dash.audios_pendientes ?? 0}</b></div>
              <div className="stat-row"><span>Imágenes omitidas (total)</span><b>{dash.imagenes_pendientes ?? 0}</b></div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Card({ icon, label, value, green, warn }: { icon: string; label: string; value: string; green?: boolean; warn?: boolean }) {
  return (
    <div className="card">
      <div className="card-icon">{icon}</div>
      <div className="card-body">
        <div className={`card-value ${green ? 'green' : warn ? 'warn' : ''}`}>{value}</div>
        <div className="card-label">{label}</div>
      </div>
    </div>
  )
}
