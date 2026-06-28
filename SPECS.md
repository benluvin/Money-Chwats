# Money Chwats — Especificaciones (versión sencilla)

> Qué hace cada parte de la app, con qué tecnología, y qué necesita tu computador
> para que funcione. Escrito para que cualquiera lo entienda, sin tecnicismos.

---

## En una frase

Tomas una foto larga de un chat de WhatsApp → la app la lee → la convierte en
dos tablas: **Clientes** y **Pedidos**.

---

## Las piezas (servicios)

### 1. Extensión del navegador — "El fotógrafo"
- **Qué hace:** captura toda la conversación abierta en WhatsApp Web (hace scroll
  solo y une los pedazos en una sola imagen larga). La manda a la app.
- **Tecnología:** extensión de Google Chrome.
- **Necesita:** el navegador Chrome abierto. Casi no consume recursos.
- **Internet:** solo para ver WhatsApp Web (normal).

### 2. Servicio de escritorio — "El coordinador"
- **Qué hace:** recibe la imagen, la guarda, y dirige todo el proceso (llama al
  lector, al estructurador y guarda las tablas). Es el cerebro organizador.
- **Tecnología:** un pequeño programa en Python que corre en tu propio computador.
- **Necesita:** muy poca RAM (~100–200 MB). Corre en cualquier PC, incluso de 4 GB.
- **Internet:** no (vive solo en tu máquina, en `127.0.0.1`).

### 3. Lector de imágenes (OCR) — "Los ojos"
- **Qué hace:** convierte la imagen del chat en texto, y deduce quién habla
  (negocio a la derecha, cliente a la izquierda).
- **Tecnología:** RapidOCR (un lector liviano que corre en el procesador, sin
  tarjeta gráfica especial).
- **Necesita:** ~300–600 MB de RAM mientras lee. Tarda ~7 segundos por chat.
  Corre bien en PC de 4 GB. **No necesita internet ni GPU.**

### 4. Capa de blindaje — "El censor"
- **Qué hace:** antes de mandar algo a internet, tapa los datos personales
  (teléfonos, correos, direcciones y nombres conocidos) con códigos. Los datos
  reales nunca salen de tu computador.
- **Tecnología:** reglas locales (sin internet, sin IA).
- **Necesita:** nada relevante. Es instantáneo.

### 5. Estructurador — "El analista"
Convierte el texto en datos ordenados. Tiene **3 modos** (eliges uno):

| Modo | Dónde corre | Internet | RAM | Calidad |
| --- | --- | --- | --- | --- |
| **Reglas** | Tu PC | No | Nada | Básica (cuentas, montos) |
| **Nemotron** | Nube (OpenRouter) | Sí | Nada (corre afuera) | Alta (resumen, etiquetas) |
| **Local** | Tu PC (Ollama) | No | ~1–2 GB | Media (solo PC holgados) |

- **Tecnología:** Nemotron es un modelo de IA grande que vive en internet; solo
  le mandamos texto (ya blindado) y nos devuelve los datos ordenados.
- **Necesita (modo Nemotron):** internet y una clave gratuita de OpenRouter.
  Tarda ~15–70 segundos según la hora.

### 6. Las tablas (almacenamiento) — "El archivador"
- **Qué hace:** guarda todo en tu computador, en archivos que abres con Excel.
  - **Clientes:** una fila por cliente, con un código único (ID).
  - **Pedidos:** una fila por pedido, que apunta al ID del cliente.
  - También guarda la imagen original y el texto leído, como evidencia.
- **Tecnología:** archivos CSV (Excel) + imágenes PNG.
- **Necesita:** espacio en disco. Nada de RAM especial.

---

## Qué necesita tu computador (resumen)

| Para... | Mínimo |
| --- | --- |
| Capturar + leer + guardar (todo local) | PC de **4 GB de RAM**, sin tarjeta gráfica |
| Análisis inteligente con Nemotron | Lo anterior **+ internet** + clave de OpenRouter |
| Análisis inteligente sin internet | PC de **8 GB+** (modo local con Ollama) |

> Importante: la app **NO** usa modelos de IA pesados dentro de tu computador.
> Por eso corre liviana. La parte "pesada" (Nemotron) ocurre en internet.

---

## Flujo del proceso (base para el BPMN)

**Participantes (carriles):** Usuario · Extensión · Servicio de escritorio ·
Lector OCR · Blindaje · Estructurador · Nube (Nemotron) · Tablas.

1. **Usuario** abre un chat en WhatsApp Web y dispara la captura.
2. **Extensión** fotografía el chat completo y lo envía al servicio.
3. **Servicio** guarda la imagen y registra la captura.
4. **Servicio** pide al **Lector OCR** convertir la imagen en texto.
5. **Lector OCR** devuelve el texto con quién habla cada línea.
6. *¿El modo es nube?*
   - **Sí →** **Blindaje** tapa los datos personales → se envía a la **Nube**
     → la Nube devuelve los datos ordenados → se destapan los datos localmente.
   - **No →** el **Estructurador por reglas** ordena los datos en tu PC.
7. *¿La confianza es baja?*
   - **Sí →** se marca la fila como "requiere revisión".
   - **No →** sigue normal.
8. **Servicio** escribe/actualiza la fila en **Clientes** y agrega filas en
   **Pedidos** (ligadas por el ID del cliente).
9. **Usuario** abre las tablas en Excel y revisa.

**Puntos de decisión (compuertas del BPMN):**
- Modo de análisis: *reglas (local)* vs *Nemotron (nube)*.
- Calidad: *confianza alta* vs *baja → requiere revisión*.

**Eventos de error posibles:** sin internet (cae a reglas), clave de nube
inválida (cae a reglas), imagen ilegible.

---

## Estado actual

**Giro de rumbo (Export-first):** la vía principal ya NO es la foto+OCR sino
**"Exportar chat"** de WhatsApp (texto perfecto, historial completo, cero riesgo de
baneo, escala a miles). El OCR queda como **respaldo** para lo visual. El DOM se
archivó (su único trabajo —corregir el OCR— ya no hace falta), salvo para la futura
"lista matriz" (leer la lista de chats).

**✅ Funcionando y probado (29 tests):**
- **Importar "Exportar chat"** → tablas Clientes/Pedidos (validado con 1.805 mensajes reales).
- **Detector de multimedia** (cuenta audios/imágenes/videos y avisa para re-exportar).
- **Vigilante de carpeta** (procesa solo los .txt que sueltes) + **tablero** de avance.
- Blindaje (seudonimización), analistas reglas/Nemotron/local, columnas nuevas
  (`telefono_pendiente`, `nickname`, `audios/imagenes/videos_detectados`, `multimedia_pendiente`).
- OCR optimizado (gris/1x/WebP) como respaldo.

**🔜 Pendiente:**
- **Lista matriz** (leer la lista de chats por DOM) para el tablero "X/2.000" y modo guiado.
- **Nemotron para chats largos** (trocear/resumir; hoy un chat de 1.805 msgs es mucho para una sola llamada).
- **Filtrar** notificaciones de llamada.
- **Re-importar con multimedia** + **transcripción de audios** (Whisper) para rescatar pedidos en notas de voz.
- **App instalable** (tray, sin terminal) para clientes finales.

---

## Riesgos de bloqueo en WhatsApp / Meta

**El principio:** WhatsApp banea o mete en listas de spam por lo que una cuenta
**ENVÍA**, no por lo que **LEE**. Los bloqueos vienen de mensajes masivos, contactar
desconocidos en frío, agregar contactos muy rápido, usar apps no oficiales para
*enviar*, o acumular reportes de la gente. **Money Chwats no envía nada: solo lee
chats que tú ya abriste.** Por eso el riesgo de caer en una lista negra de números
es casi nulo en nuestro diseño.

### Las formas de hacerlo, de la más segura a la más riesgosa
| Forma de obtener los datos | Cómo funciona | Riesgo de baneo |
| --- | --- | --- |
| **Exportar chat** (función oficial de WhatsApp) | El usuario exporta el chat a un archivo y la app lo lee | **Nulo** (es una función propia de WhatsApp) |
| **Lectura local reactiva** ← *nuestra app* (DOM o pantallazo; el usuario abre cada chat a mano) | La app solo lee lo que ya está en pantalla; no navega sola | **Muy bajo** |
| **Auto-scroll** para cargar mensajes viejos | La app baja sola dentro del chat abierto | **Bajo** (automatización leve; es lo único "detectable" hoy) |
| **Automatizar la navegación** (abrir chats/contactos solos con un bot) | Un robot simula al usuario moviéndose por la app | **Medio-alto** (parece bot, es detectable) |
| **Clientes/librerías no oficiales** (se conectan al protocolo de WhatsApp) | Programas que se hacen pasar por WhatsApp | **Alto** (Meta los persigue, sobre todo si envían) |
| **Envío masivo / mensajes en frío / multicuenta** | Mandar a muchos, a desconocidos | **Muy alto** (esto sí mete en listas de spam y banea) |
| **API oficial de WhatsApp Business (Cloud API)** | La vía sancionada por Meta | **Nulo**, pero **cuesta**, exige verificar el negocio y es para tu propia mensajería, no para leer chats personales ajenos |

### Dónde estamos y qué NO hacer
- **Estamos en la zona segura** (lectura local reactiva). El único punto "detectable"
  es el auto-scroll del fotógrafo, y es leve.
- **Lo que dispararía el riesgo** (nunca agregar sin pensarlo): enviar mensajes
  automáticos, abrir chats/contactos de forma automática, usar librerías no
  oficiales, o cualquier flujo saliente masivo.
- **El mejor blindaje de nuestro diseño:** el usuario abre cada chat a mano y la
  app **nunca envía nada**.

> ⚠️ No es asesoría legal y las políticas de Meta pueden cambiar; es una evaluación
> técnica del riesgo.

---

## Fricciones, límites y aprendizajes (qué nos frenó y qué prever)

Resumen de los obstáculos reales de esta sesión. Sirve de checklist para futuros
proyectos parecidos (capturas, OCR, IA local, datos sensibles).

### A. Hardware y capacidad
| Fricción | Qué pasó | Cómo se resolvió / aprendizaje |
| --- | --- | --- |
| **RAM tope de 8 GB (Mac M1)** | La RAM está soldada, no se amplía. Es un techo fijo. | Diseñar para PC de 4 GB: nada de IA pesada local. |
| **Modelo de visión congeló el PC** | qwen2.5-VL (3–6 GB) + el pico al procesar la imagen llenó la RAM y el equipo se bloqueó varias veces. | Abandonar visión local. OCR liviano + IA en la nube. |
| **"Memoria usada" siempre llena** | macOS llena la RAM con caché; el número asusta pero no es real. | Mirar **presión de memoria** (verde/amarillo/rojo), no "usada". |
| **El swap no se vacía solo** | Llegó a 3,8 GB y trababa todo. | Solo se limpia **reiniciando** el equipo. |
| **Cuantizar no alcanzó** | El modelo ya venía cuantizado (Q4); reducir más daña la calidad. | Cuantizar resuelve "tamaño en disco", no "pico de RAM". |
| **Formatear no sirve** | No añade RAM ni quita el pico; el equipo ya estaba limpio. | No invertir horas en formateos que no atacan la causa. |

### B. Tecnologías de OCR / IA
| Fricción | Qué pasó | Aprendizaje |
| --- | --- | --- |
| **Casi todos los OCR top exigen GPU de servidor** | Chandra (5B, GPU H100), Baidu Unlimited-OCR (exige CUDA = solo NVIDIA). | En Mac/PC modesto: descartarlos de entrada. Verificar requisitos ANTES de probar. |
| **No existe OCR "bueno y liviano" de visión** | Probamos 3 modelos; todos pesados. | Para hardware limitado: OCR clásico (RapidOCR) + IA de texto, no visión. |
| **Instalar librerías de IA en Mac da guerra** | paddlepaddle es problemático en Apple Silicon. | Preferir runtimes portables (ONNX / RapidOCR). |

### C. Costos
| Fricción | Aprendizaje |
| --- | --- |
| **No hay presupuesto extra (máx. VPS de $5)** | El VPS de $5 (4 GB, sin GPU) **no** corre modelos de visión; sirve para hospedar servicios livianos, no como motor de IA. |
| **OCR/IA en la nube cuesta por uso** | El plan gratis (Nemotron `:free`) existe pero es lento y con menos garantías. |

### D. Privacidad y nube
| Fricción | Qué pasó | Aprendizaje |
| --- | --- | --- |
| **Usar la nube choca con "todo local"** | Mandar chats a OpenRouter rompe la regla de no-red-externa. | Hacerlo **opt-in** + **blindaje** (tapar datos personales antes de enviar). |
| **Plan gratis puede registrar los datos** | Los modelos `:free` pueden usar los prompts para entrenar. | El blindaje es justo lo que protege; valorar plan de pago con cero-retención. |
| **Blindaje de nombres incompleto** | "Luchi"/"Migue" viajaron sin tapar: no se sabía el nombre antes de leer. | Necesita el nombre del contacto **desde el DOM** (Fase 2) o heurística previa. |

### E. Calidad de los datos
| Fricción | Aprendizaje |
| --- | --- |
| **Errores de OCR** (¿ → :, horas coladas, líneas cruzadas) | Inevitables leyendo imágenes; mitigar con doble-check del DOM (texto exacto). |
| **Las reglas no "entienden"** | Sin IA solo hay datos básicos; el resumen inteligente requiere un LLM. |
| **Confusión "lo hizo la app vs lo hizo el asistente"** | Dejar claro qué produce la app sola y qué requiere IA. Gestionar expectativas. |

### F. Proceso y desarrollo
| Fricción | Aprendizaje |
| --- | --- |
| **Correr pruebas pesadas sin permiso congeló el PC** | En equipos limitados: **pedir autorización** antes de operaciones que consuman recursos, y medir RAM antes. |
| **Sobre-ingeniería al inicio** (emparejamiento por código, parser DOM frágil) | Empezar simple (estilo Fireshot); evitar fricción innecesaria al usuario. |
| **Límites del navegador** (canvas máx. ~16.000 px, inyección del content script) | Conocer límites técnicos del entorno antes de diseñar. |
| **Servicios que se caen al lanzarlos mal** (uvicorn con `&`) | Procesos de fondo deben lanzarse de forma persistente. |

### Checklist para proyectos similares (prever desde el día 1)
1. **¿Qué RAM/GPU real tiene el equipo destino?** Decide local vs nube antes de codear.
2. **¿El modelo elegido corre en ese hardware?** Verifica requisitos (GPU/CUDA) primero.
3. **¿Hay datos personales?** Define blindaje + opt-in de nube desde el inicio.
4. **¿Presupuesto?** Confirma si la nube de pago es opción o todo debe ser gratis/local.
5. **Empieza simple**, sin fricción para el usuario; agrega complejidad solo si suma.
6. **Pide permiso** antes de operaciones pesadas en el equipo del usuario.
7. **Separa "lo que hace la app" de "lo que hace la IA/el asistente"** para no crear falsas expectativas.

---

## Para replicar este proyecto desde cero (qué hace falta y para qué)

Este documento explica el **qué** y el **por qué**. Para que otra persona (u otra
sesión de IA) construya algo **igual**, hay que entregar también el **cómo**. Esto
es la lista de lo que falta documentar, y para qué sirve cada cosa:

### 1. Herramientas y versiones
*Para qué:* usar la misma "caja de herramientas" y no una parecida que se comporte
distinto.

*Lo que usamos:*
- **Servicio (el coordinador):** Python 3.11. Librerías: FastAPI y uvicorn (para
  recibir las "órdenes"), Pydantic v2 (para validar que los datos tengan la forma
  correcta), httpx (para hablar con la nube), filelock (para no corromper las
  tablas si Excel las tiene abiertas), Pillow + numpy (para manejar la imagen).
- **Lector de imágenes:** RapidOCR (paquete `rapidocr-onnxruntime`), que trae los
  modelos PP-OCRv4 y corre en el procesador, sin tarjeta gráfica.
- **Extensión:** TypeScript compilado con esbuild; Chrome, Manifest V3; sin
  frameworks (código simple a propósito).
- **IA de nube:** Nemotron (`nvidia/nemotron-3-super-120b-a12b:free`) a través de
  OpenRouter. *Alternativa local opcional:* Ollama con un modelo de texto chico
  (`qwen2.5:1.5b`).

### 2. Mapa de carpetas y archivos
*Para qué:* saber dónde va cada cosa y no armar un rompecabezas diferente.

*Lo que usamos:* dos carpetas grandes.
- **`extension/`** — `manifest.json` (permisos del navegador), y en `src/`:
  `background.ts` (arma la foto larga), `content-script.ts` (mide y hace scroll),
  `popup.ts/.html/.css` (el botoncito y el estado), `lib/desktop-client.ts`
  (habla con el servicio).
- **`desktop/`** — `config.toml` (la hoja de ajustes) y la carpeta `app/` con:
  `main.py` (enciende el servicio), `routes/` (las órdenes: capturar/procesar/abrir),
  `pipeline/` (lector OCR, blindaje, escritura de tablas, instrucciones de IA),
  `structurer/` (los 3 modos de análisis), `models/` (la forma de los datos).
- **Dónde se guarda todo:** `raw/AÑO/MES/DÍA/<id>.png` (las fotos),
  `data/clientes.csv`, `data/pedidos.csv`, `data/capturas.csv` (las tablas),
  `data/ocr/<id>.txt` (el texto leído, como evidencia).

### 3. Definición exacta de las tablas  *(lo más importante)*
*Para qué:* que los datos salgan idénticos y las dos tablas se conecten bien.

*Lo que usamos:* archivos CSV con separador `;`, en UTF-8, decimales con punto
(`50000.5`) y fechas tipo `2026-06-28`.
- **`clientes.csv`** — una fila por cliente. Columnas clave: un **código único
  (`cliente_id`)**, nombre, teléfono (completo y oculto), fechas del primer y
  último mensaje, conteo de mensajes (totales, del cliente, del negocio), **estado
  de la relación** (lead / activo / negociando / cerrado_ganado / cerrado_perdido
  / inactivo), dirección, sentimiento (positivo/neutral/negativo), etiquetas,
  resumen, total y monto de pedidos, confianza (0 a 1), "requiere revisión",
  imagen de evidencia, qué modelo lo analizó y cómo (`ocr+reglas` / `ocr+nemotron`).
- **`pedidos.csv`** — una fila por pedido. Trae su propio código (`pedido_id`) y
  **el `cliente_id` del cliente al que pertenece** (así se conectan las dos
  tablas), más producto, cantidad, unidad, precio, monto, moneda (COP), forma de
  pago, dirección de envío, fechas, **estado del pedido** (mencionado / confirmado
  / en_preparacion / entregado / cancelado / desconocido) y la frase original.
- **Cómo se crea el código del cliente:** se calcula a partir del teléfono (o del
  nombre si no hay teléfono). Así, **el mismo cliente siempre da el mismo código**
  y nunca se duplica aunque se procese su chat varias veces.

### 4. Las "órdenes" que recibe la app (cómo se comunican las piezas)
*Para qué:* que las partes se entiendan igual entre sí.

*Lo que usamos:* el servicio vive en `127.0.0.1:5000` (solo tu PC) y atiende:
- **Capturar:** recibe la foto (en pedazos), la une, la guarda y anota la captura.
- **Procesar una captura:** lee, blinda, analiza y llena las tablas.
- **Abrir un archivo:** muestra la imagen o la carpeta (verificando que sea del
  proyecto).
- **Consultar estado:** dice si el lector está listo y qué modo de análisis se usa.
- *Seguridad:* solo acepta llamadas de la propia extensión y de tu computador.

### 5. El texto exacto que se le da a la IA
*Para qué:* de esto depende la calidad del resumen y de los datos; cambiarlo cambia
el resultado.

*Lo que usamos:* dos instrucciones (guardadas en `prompts.py`):
- **Instrucción de rol:** "eres un analista de CRM para negocios pequeños en
  Colombia; devuelve SOLO datos en JSON; no inventes nada; los montos son en pesos
  colombianos; las fechas en formato `AÑO-MES-DÍA`; lo de la derecha es del
  negocio y lo de la izquierda del cliente; ignora horas sueltas y avisos; si no
  hay pedido claro, deja la lista vacía; pon una confianza de 0 a 1".
- **Regla de blindaje:** "el texto trae códigos como `[[NOMBRE_1]]` o `[[TEL_1]]`;
  cópialos tal cual, no los traduzcas ni borres" (así la IA respeta los datos
  tapados).
- También se le entrega el **molde exacto del JSON** que debe devolver (los mismos
  campos de las tablas).

### 6. Los pasos de las partes "inteligentes"
*Para qué:* reproducir la lógica, no solo la idea.

*Lo que usamos:*
- **Armar la foto larga:** la extensión detecta el panel de la conversación (el
  más grande y a la derecha, no la lista de contactos), esconde lo que flota,
  baja de a ~95% de pantalla (deja 5% de solape), espera a que todo quede quieto
  antes de cada toma, y une los pedazos. Si la imagen es altísima, la parte en
  trozos de máximo 16.000 px y los pega en el servicio.
- **Quién habla:** se mira la posición horizontal de cada línea; si está hacia la
  derecha es del negocio, hacia la izquierda del cliente, y en el centro "dudoso".
- **Leer la imagen:** el lector procesa la foto por franjas de ~2.000 px con un
  poco de solape, y descarta líneas repetidas por ese solape.
- **Blindaje:** detecta teléfonos/correos/direcciones (y nombres si se conocen) y
  los cambia por códigos `[[TEL_1]]`, `[[EMAIL_1]]`, `[[DIR_1]]`, `[[NOMBRE_1]]`;
  guarda en tu PC un mapa código→valor real, y al recibir la respuesta de la nube
  los vuelve a poner. El mismo dato repetido reutiliza el mismo código.
- **Analizar:** hay una "interfaz" común y 3 modos intercambiables (reglas / nube
  / local). Si se pide el modo nube pero no hay clave o internet, **cae solo al
  modo reglas** (nunca se queda sin funcionar). Si la confianza es menor a 0.6, la
  fila se marca como "requiere revisión".

### 7. La hoja de configuración
*Para qué:* ajustar la app sin tocar el código.

*Lo que usamos:* el archivo **`config.toml`**, dividido en secciones:
- dónde se guardan los archivos; formato de las tablas (`;`, UTF-8, COP, español);
- **modo de análisis** (`reglas`, `nemotron` o `local`);
- **nube** (encendida sí/no, dirección de OpenRouter, modelo, tu clave, tiempo
  máximo de espera);
- **blindaje** (qué tapar: teléfonos, correos, direcciones, nombres).

### 8. Instalación y arranque
*Para qué:* que cualquiera lo ponga a andar.

*Lo que usamos:*
1. Instalar las librerías del servicio (incluido RapidOCR).
2. Sacar la clave gratis en `openrouter.ai/keys` y pegarla en `config.toml`.
3. Encender el servicio (uvicorn en el puerto 5000).
4. Compilar la extensión y cargarla en `chrome://extensions` (modo desarrollador).
5. *(Opcional, modo local)* instalar Ollama y bajar un modelo de texto chico.

### 9. Las reglas que no se deben romper
*Para qué:* conservar la seguridad y el espíritu del proyecto.

*Lo que usamos:*
- El servicio **solo vive en tu PC** (`127.0.0.1`), nunca abierto a internet.
- A la nube **solo va texto blindado y con tu permiso** (la nube es opt-in).
- **No se automatiza WhatsApp:** el usuario abre cada chat y dispara la captura a
  mano (así no hay riesgo de bloqueo de cuenta).
- Sin telemetría ni envíos ocultos. Todo en **español** y en **pesos colombianos**.
- Los códigos de cliente/pedido son **siempre los mismos** para el mismo dato
  (reprocesar no duplica).

### 10. Cómo saber que quedó bien
*Para qué:* tener una meta clara de "terminado".

*Lo que logramos:*
- El lector procesó un chat de 107 líneas en **~7 segundos**, **sin trabar** el PC.
- El análisis con Nemotron tardó **~69 segundos** (plan gratis) y generó la fila
  del cliente con nombre, fechas, conteos, sentimiento, etiquetas y resumen real.
- Se crean las **dos tablas conectadas** por el `cliente_id`.
- Corre en un PC de **4 GB** (modo reglas o nube); el modo de IA local pide 8 GB+.
- Las **pruebas automáticas pasan** (blindaje, reglas y demás).

> En resumen: **este `SPECS.md` evita repetir errores; falta un documento técnico
> hermano (el "plano de construcción") para reproducir el sistema tal cual.** Los
> dos juntos permiten que otra persona llegue al mismo resultado.
