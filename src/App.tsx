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
      getCatalogo: () => Promise<{ data: any[]; total: number }>
      saveProducto: (p: Record<string, string>) => Promise<any>
      deleteProducto: (id: string) => Promise<any>
      deleteCliente: (id: string) => Promise<any>
      deletePedido: (id: string) => Promise<any>
      editCliente: (id: string, cambios: Record<string, string>) => Promise<any>
      editPedido: (id: string, cambios: Record<string, string>) => Promise<any>
      selectAgenda: () => Promise<string | null>
      importAgenda: (path: string) => Promise<any>
      getContactos: () => Promise<{ data: any[]; total: number }>
      reanalizarCliente: (id: string) => Promise<any>
    }
  }
}

type Tab = 'clientes' | 'pedidos' | 'catalogo' | 'contactos'

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

  // Filtros clientes
  const [cq, setCq] = useState('')
  const [cPendiente, setCPendiente] = useState(false)

  // Filtros pedidos
  const [pq, setPq] = useState('')
  const [pEstado, setPEstado] = useState('')

  // Catálogo
  const [catalogo, setCatalogo] = useState<any[]>([])
  const [nProd, setNProd] = useState({ nombre: '', precio: '', descripcion: '' })

  // Agenda de contactos
  const [contactos, setContactos] = useState<any[]>([])
  const [cont_q, setContQ] = useState('')
  const [importandoAgenda, setImportandoAgenda] = useState(false)

  // Edición inline
  const [editCid, setEditCid] = useState<string | null>(null)
  const [draftC, setDraftC] = useState<Record<string, string>>({})
  const [editPid, setEditPid] = useState<string | null>(null)
  const [draftP, setDraftP] = useState<Record<string, string>>({})

  const reload = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [d, c, p, cat, con] = await Promise.all([
        window.api.getDashboard(),
        window.api.getClientes(),
        window.api.getPedidos(),
        window.api.getCatalogo(),
        window.api.getContactos(),
      ])
      setDash(d)
      setClientes(c.data ?? [])
      setPedidos(p.data ?? [])
      setCatalogo(cat.data ?? [])
      setContactos(con.data ?? [])
    } catch (e) {
      console.error(e)
    } finally {
      if (!silent) setLoading(false)
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

  // Auto-refresco: el vigilante puede importar un chat en cualquier momento,
  // así que recargamos las tablas cada 5 s sin que el usuario haga nada.
  useEffect(() => {
    const id = setInterval(() => {
      // No refrescar mientras el usuario edita una fila (no perder su borrador).
      if (editCid || editPid) return
      reload(true)
    }, 5000)
    return () => clearInterval(id)
  }, [reload, editCid, editPid])

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
    if (cq && !c.nombre?.toLowerCase().includes(cq.toLowerCase()) && !c.telefono_completo?.includes(cq)) return false
    if (cPendiente && c.multimedia_pendiente?.toUpperCase() !== 'TRUE') return false
    return true
  })

  const pedidosFiltrados = pedidos.filter(p => {
    if (pq && !p.producto_servicio?.toLowerCase().includes(pq.toLowerCase()) &&
        !p._nombre_cliente?.toLowerCase().includes(pq.toLowerCase())) return false
    if (pEstado && p.estado_pedido?.toLowerCase() !== pEstado.toLowerCase()) return false
    return true
  })

  // Estados de pedido presentes en los datos (para el filtro).
  const estadosPedido = Array.from(
    new Set(pedidos.map(p => (p.estado_pedido || '').trim()).filter(Boolean))
  ).sort()

  // Última compra POR CLIENTE = fecha del pedido más reciente. Si no tiene
  // pedidos, no hay última compra ("—"). NO usamos la fecha del último mensaje.
  const ultimaCompraPorCliente: Record<string, string> = {}
  for (const p of pedidos) {
    const cid = p.cliente_id
    const f = (p.fecha_pedido || '').slice(0, 10)
    if (!cid || !f) continue
    if (!ultimaCompraPorCliente[cid] || f > ultimaCompraPorCliente[cid]) {
      ultimaCompraPorCliente[cid] = f
    }
  }

  const borrarCliente = async (c: any) => {
    if (!confirm(`¿Borrar a "${c.nombre || 'sin nombre'}" y todos sus pedidos?`)) return
    await window.api.deleteCliente(c.cliente_id)
    await reload()
  }

  const [reanalizando, setReanalizando] = useState<string | null>(null)
  const reanalizar = async (cliente_id: string) => {
    setReanalizando(cliente_id)
    try {
      await window.api.reanalizarCliente(cliente_id)
    } catch (e) {
      alert('No se pudo reanalizar: ' + e)
    } finally {
      setReanalizando(null)
      await reload()
    }
  }

  const borrarPedido = async (p: any) => {
    if (!confirm('¿Borrar este pedido?')) return
    await window.api.deletePedido(p.pedido_id)
    await reload()
  }

  const agregarProducto = async () => {
    if (!nProd.nombre.trim()) return
    await window.api.saveProducto(nProd)
    setNProd({ nombre: '', precio: '', descripcion: '' })
    await reload()
  }

  const borrarProducto = async (id: string) => {
    if (!confirm('¿Borrar este producto del catálogo?')) return
    await window.api.deleteProducto(id)
    await reload()
  }

  // ── Edición de clientes ──
  const startEditCliente = (c: any) => {
    setEditCid(c.cliente_id)
    setDraftC({ nombre: c.nombre || '', telefono_completo: c.telefono_completo || '' })
  }
  const saveCliente = async () => {
    if (!editCid) return
    await window.api.editCliente(editCid, draftC)
    setEditCid(null)
    await reload()
  }

  // ── Edición de pedidos ──
  const startEditPedido = (p: any) => {
    setEditPid(p.pedido_id)
    setDraftP({
      producto_servicio: p.producto_servicio || '',
      cantidad: p.cantidad || '',
      monto_total: p.monto_total || '',
      fecha_pedido: (p.fecha_pedido || '').slice(0, 10),
      estado_pedido: p.estado_pedido || '',
    })
  }
  const savePedido = async () => {
    if (!editPid) return
    await window.api.editPedido(editPid, draftP)
    setEditPid(null)
    await reload()
  }

  const importarAgenda = async () => {
    const path = await window.api.selectAgenda()
    if (!path) return
    setImportandoAgenda(true)
    try {
      const r = await window.api.importAgenda(path)
      if (r?.ok) {
        alert(`Agenda importada: ${r.nuevos} contactos nuevos (total ${r.total}).`)
      } else {
        alert('No se pudo importar: ' + (r?.detail ?? 'error'))
      }
    } catch (e) {
      alert('Error importando agenda: ' + e)
    } finally {
      setImportandoAgenda(false)
      await reload()
    }
  }

  const contactosFiltrados = contactos.filter(c =>
    !cont_q || c.nombre?.toLowerCase().includes(cont_q.toLowerCase()) || (c.telefono || '').includes(cont_q)
  )

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <img src="/icon.png" alt="" className="header-icon" />
          <h1 className="header-title">Money Chwats</h1>
          <span className={`status-dot ${serverOk ? 'ok' : 'err'}`} title={serverOk ? 'Servicio activo' : 'Servicio no responde'} />
        </div>
        <button className="btn-refresh" onClick={() => reload()} disabled={loading} title="Actualizar datos">
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
        {(['clientes', 'pedidos', 'catalogo', 'contactos'] as Tab[]).map(t => (
          <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t === 'clientes' ? '👥 Clientes' : t === 'pedidos' ? '📦 Pedidos' : t === 'catalogo' ? '📕 Catálogo' : '📇 Contactos'}
          </button>
        ))}
      </div>

      {/* ── Content ── */}
      <div className="content">
        {tab === 'clientes' && (
          <>
            <div className="filters">
              <input className="filter-input" placeholder="Buscar nombre o teléfono…" value={cq} onChange={e => setCq(e.target.value)} />
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
                    <th>Creado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {clientesFiltrados.length === 0 ? (
                    <tr><td colSpan={8} className="empty">No hay clientes registrados aún</td></tr>
                  ) : clientesFiltrados.map((c, i) => {
                    const editando = editCid === c.cliente_id
                    return (
                    <tr key={c.cliente_id ?? i} className={i % 2 === 0 ? 'row-a' : 'row-b'}>
                      <td className="rank">{i + 1}</td>
                      <td className="name">
                        {editando ? (
                          <input className="cell-input" value={draftC.nombre} autoFocus
                            onChange={e => setDraftC({ ...draftC, nombre: e.target.value })} />
                        ) : (
                          <>
                            {c.nombre || c.nombre_contacto || '—'}
                            {c.estado_analisis === 'pendiente' && <span className="flag analizando" title="Analizando…"> 🔄</span>}
                            {c.estado_analisis === 'fallback' && <span className="flag" title="Análisis offline (Nemotron no respondió) — pulsa Actualizar"> ⚡</span>}
                            {c.editado_manualmente === 'true' && <span className="flag edited" title="Editado a mano"> ✎</span>}
                            {c.requiere_revision?.toUpperCase() === 'TRUE' && <span className="flag" title="Requiere revisión"> ⚠</span>}
                            {c.multimedia_pendiente?.toUpperCase() === 'TRUE' && <span className="flag media" title="Multimedia pendiente"> 🎵</span>}
                          </>
                        )}
                      </td>
                      <td>
                        {editando ? (
                          <input className="cell-input" value={draftC.telefono_completo} placeholder="teléfono"
                            onChange={e => setDraftC({ ...draftC, telefono_completo: e.target.value })} />
                        ) : (c.telefono_completo || <span className="dim">sin tel.</span>)}
                      </td>
                      <td>{ultimaCompraPorCliente[c.cliente_id] || <span className="dim">—</span>}</td>
                      <td className="num">{c.total_pedidos_detectados || '0'}</td>
                      <td className="num green">{COP(c.monto_total_pedidos)}</td>
                      <td className="dim">{(c.fecha_creacion || '').replace('T', ' ').slice(0, 16) || '—'}</td>
                      <td className="acciones">
                        {editando ? (
                          <>
                            <button className="btn-ok" title="Guardar" onClick={saveCliente}>✓</button>
                            <button className="btn-del" title="Cancelar" onClick={() => setEditCid(null)}>✕</button>
                          </>
                        ) : (
                          <>
                            <button className="btn-edit" title="Actualizar (re-analizar con IA)" disabled={reanalizando === c.cliente_id} onClick={() => reanalizar(c.cliente_id)}>{reanalizando === c.cliente_id ? '⏳' : '🔄'}</button>
                            <button className="btn-edit" title="Editar" onClick={() => startEditCliente(c)}>✎</button>
                            <button className="btn-del" title="Borrar cliente" onClick={() => borrarCliente(c)}>🗑</button>
                          </>
                        )}
                      </td>
                    </tr>
                  )})}
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
                {estadosPedido.map(e => <option key={e} value={e}>{e}</option>)}
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
                    <th>Estado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {pedidosFiltrados.length === 0 ? (
                    <tr><td colSpan={7} className="empty">No hay pedidos registrados aún</td></tr>
                  ) : pedidosFiltrados.map((p, i) => {
                    const editando = editPid === p.pedido_id
                    return (
                    <tr key={p.pedido_id ?? i} className={i % 2 === 0 ? 'row-a' : 'row-b'}>
                      <td className="rank">{i + 1}</td>
                      <td className="name">{p._nombre_cliente || p.cliente_id || '—'}</td>
                      <td>
                        {editando ? (
                          <div className="cell-pair">
                            <input className="cell-input" value={draftP.producto_servicio} autoFocus placeholder="producto"
                              onChange={e => setDraftP({ ...draftP, producto_servicio: e.target.value })} />
                            <input className="cell-input cell-qty" value={draftP.cantidad} placeholder="cant."
                              onChange={e => setDraftP({ ...draftP, cantidad: e.target.value })} />
                          </div>
                        ) : (<>{p.producto_servicio || '—'}{p.cantidad && p.cantidad !== '1' ? ` ×${p.cantidad}` : ''}</>)}
                      </td>
                      <td className="num green">
                        {editando ? (
                          <input className="cell-input cell-num" value={draftP.monto_total} placeholder="0"
                            onChange={e => setDraftP({ ...draftP, monto_total: e.target.value.replace(/[^\d.]/g, '') })} />
                        ) : COP(p.monto_total)}
                      </td>
                      <td>
                        {editando ? (
                          <input className="cell-input" type="date" value={draftP.fecha_pedido}
                            onChange={e => setDraftP({ ...draftP, fecha_pedido: e.target.value })} />
                        ) : fecha(p.fecha_pedido)}
                      </td>
                      <td>
                        {editando ? (
                          <input className="cell-input" value={draftP.estado_pedido} placeholder="estado"
                            onChange={e => setDraftP({ ...draftP, estado_pedido: e.target.value })} />
                        ) : <Badge val={p.estado_pedido} />}
                      </td>
                      <td className="acciones">
                        {editando ? (
                          <>
                            <button className="btn-ok" title="Guardar" onClick={savePedido}>✓</button>
                            <button className="btn-del" title="Cancelar" onClick={() => setEditPid(null)}>✕</button>
                          </>
                        ) : (
                          <>
                            <button className="btn-edit" title="Actualizar (re-analizar el cliente con IA)" disabled={reanalizando === p.cliente_id} onClick={() => reanalizar(p.cliente_id)}>{reanalizando === p.cliente_id ? '⏳' : '🔄'}</button>
                            <button className="btn-edit" title="Editar" onClick={() => startEditPedido(p)}>✎</button>
                            <button className="btn-del" title="Borrar pedido" onClick={() => borrarPedido(p)}>🗑</button>
                          </>
                        )}
                      </td>
                    </tr>
                  )})}
                </tbody>
              </table>
            </div>
          </>
        )}

        {tab === 'catalogo' && (
          <>
            <div className="filters cat-form">
              <input className="filter-input" placeholder="Producto…" value={nProd.nombre}
                onChange={e => setNProd({ ...nProd, nombre: e.target.value })} />
              <input className="filter-input" style={{ maxWidth: 140 }} placeholder="Precio (COP)" value={nProd.precio}
                onChange={e => setNProd({ ...nProd, precio: e.target.value.replace(/[^\d.]/g, '') })} />
              <input className="filter-input" placeholder="Descripción breve" value={nProd.descripcion}
                onChange={e => setNProd({ ...nProd, descripcion: e.target.value })}
                onKeyDown={e => e.key === 'Enter' && agregarProducto()} />
              <button className="btn-add" onClick={agregarProducto} disabled={!nProd.nombre.trim()}>+ Añadir</button>
            </div>
            <div className="table-wrap">
              <table className="tabla">
                <thead>
                  <tr><th>#</th><th>Producto</th><th>Precio</th><th>Descripción</th><th></th></tr>
                </thead>
                <tbody>
                  {catalogo.length === 0 ? (
                    <tr><td colSpan={5} className="empty">Catálogo vacío. Añade tus productos arriba — el análisis de pedidos los usará como referencia.</td></tr>
                  ) : catalogo.map((p, i) => (
                    <tr key={p.producto_id ?? i} className={i % 2 === 0 ? 'row-a' : 'row-b'}>
                      <td className="rank">{i + 1}</td>
                      <td className="name">{p.nombre}</td>
                      <td className="num green">{COP(p.precio)}</td>
                      <td>{p.descripcion || <span className="dim">—</span>}</td>
                      <td className="acciones"><button className="btn-del" title="Borrar producto" onClick={() => borrarProducto(p.producto_id)}>🗑</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {tab === 'contactos' && (
          <>
            <div className="filters">
              <input className="filter-input" placeholder="Buscar en la agenda…" value={cont_q} onChange={e => setContQ(e.target.value)} />
              <button className="btn-add" onClick={importarAgenda} disabled={importandoAgenda}>
                {importandoAgenda ? 'Importando…' : '📇 Importar agenda (.vcf / Google .csv)'}
              </button>
              <span className="filter-count">{contactosFiltrados.length} de {contactos.length}</span>
            </div>
            <div className="table-wrap">
              <table className="tabla">
                <thead>
                  <tr><th>#</th><th>Nombre</th><th>Teléfono</th></tr>
                </thead>
                <tbody>
                  {contactos.length === 0 ? (
                    <tr><td colSpan={3} className="empty">
                      Agenda vacía. Importa tus contactos (vCard del iPhone/Mac, o CSV de Google Contacts).
                      Sirven de referencia: cuando un chat coincida por nombre o número, se completa el teléfono solo.
                    </td></tr>
                  ) : contactosFiltrados.map((c, i) => (
                    <tr key={i} className={i % 2 === 0 ? 'row-a' : 'row-b'}>
                      <td className="rank">{i + 1}</td>
                      <td className="name">{c.nombre || <span className="dim">—</span>}</td>
                      <td>{c.telefono || <span className="dim">—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
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
