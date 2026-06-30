/**
 * Service worker MV3. Captura de página completa con scroll-and-stitch.
 *
 *  - Detecta el contenedor scrolleable (ventana o panel interno con más área).
 *  - Para paneles internos, captura desde el scroll actual del usuario hacia
 *    ABAJO. Así el usuario controla dónde empieza (scrollea él hasta donde
 *    quiera) y evitamos disparar lazy-load al subir hasta el tope.
 *  - Espera estabilidad de scrollTop + scrollHeight antes de cada captura
 *    (evita tears por animaciones o re-render).
 *  - Esconde elementos fixed/sticky desde antes de capturar (no se ven dobles).
 *  - Particiona la imagen en pedazos ≤16k px y los une en el desktop.
 */

import { desktop, DesktopServiceError, type CapturePayload } from "./lib/desktop-client.js";

const VERSION = chrome.runtime.getManifest().version;
const CAPTURE_DELAY_MS = 650; // ~2 capturas/seg, dentro del rate limit de Chrome
const MAX_CHUNK_HEIGHT_PX = 16000;
const OVERLAP_RATIO = 0.05; // 5% overlap entre capturas para tolerar pequeños desfases

interface MeasureResult {
  scrollWidth: number;
  scrollHeight: number;
  viewportWidth: number;
  viewportHeight: number;
  dpr: number;
  initialScrollTop: number;
  containerRect: { x: number; y: number; width: number; height: number } | null;
}

interface Chunk {
  canvas: OffscreenCanvas;
  ctx: OffscreenCanvasRenderingContext2D;
  heightPx: number;
  startY: number;
}

async function ensureContentScript(tabId: number): Promise<void> {
  try {
    await chrome.tabs.sendMessage(tabId, { kind: "ping" });
    return;
  } catch {
    // continúa con inyección
  }
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["content-script.js"],
  });
}

async function tabAsk<T = any>(tabId: number, msg: unknown): Promise<T> {
  const resp = (await chrome.tabs.sendMessage(tabId, msg)) as any;
  if (!resp?.ok) throw new Error(resp?.error ?? "content script error");
  return resp as T;
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

async function dataUrlToBitmap(dataUrl: string): Promise<ImageBitmap> {
  const blob = await (await fetch(dataUrl)).blob();
  return createImageBitmap(blob);
}

async function blobToBase64(blob: Blob): Promise<string> {
  const buf = await blob.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let bin = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

function buildChunks(widthPx: number, totalHeightPx: number): Chunk[] {
  const chunks: Chunk[] = [];
  let cursor = 0;
  while (cursor < totalHeightPx) {
    const h = Math.min(MAX_CHUNK_HEIGHT_PX, totalHeightPx - cursor);
    const canvas = new OffscreenCanvas(widthPx, h);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("OffscreenCanvas sin contexto 2d");
    // Blanco y negro: ~⅓ menos peso y el OCR suele leer mejor. El reescalado a
    // resolución normal usa interpolación de alta calidad para no perder nitidez.
    ctx.filter = "grayscale(1)";
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    chunks.push({ canvas, ctx, heightPx: h, startY: cursor });
    cursor += h;
  }
  return chunks;
}

function drawSlice(
  chunks: Chunk[],
  bitmap: ImageBitmap,
  srcX: number,
  srcY: number,
  srcW: number,
  srcH: number,
  dstY: number,
  destW: number,
  destH: number,
): void {
  // La fuente (bitmap) está en píxeles físicos (retina); el destino está en
  // píxeles "normales" (1x). drawImage reescala de físico → normal.
  const dstEnd = dstY + destH;
  for (const chunk of chunks) {
    const chunkEnd = chunk.startY + chunk.heightPx;
    if (dstEnd <= chunk.startY || dstY >= chunkEnd) continue;
    const overlapStart = Math.max(dstY, chunk.startY);
    const overlapEnd = Math.min(dstEnd, chunkEnd);
    const destSliceH = overlapEnd - overlapStart;
    if (destSliceH <= 0) continue;
    const sliceSrcY = srcY + ((overlapStart - dstY) / destH) * srcH;
    const sliceSrcH = (destSliceH / destH) * srcH;
    const sliceDstY = overlapStart - chunk.startY;
    chunk.ctx.drawImage(bitmap, srcX, sliceSrcY, srcW, sliceSrcH, 0, sliceDstY, destW, destSliceH);
  }
}

async function captureFullPage(tabId: number, windowId: number): Promise<string[]> {
  await ensureContentScript(tabId);

  const measureResp = await tabAsk<{ ok: true; data: MeasureResult }>(tabId, { kind: "measure" });
  const m = measureResp.data;
  console.log("[money-chwats] measure", m);

  await tabAsk(tabId, { kind: "prepare" });

  const isInner = !!m.containerRect;
  // Para contenedores internos arrancamos desde donde está el usuario y vamos hacia abajo.
  // Para la ventana, empezamos desde 0 (comportamiento Fireshot clásico).
  const startScroll = isInner ? m.initialScrollTop : 0;
  const captureHeightCss = Math.max(0, m.scrollHeight - startScroll);

  // Resolución NORMAL (1x): el lienzo final usa píxeles CSS, no físicos (retina).
  // Esto reduce el tamaño hasta 4x en pantallas retina sin perder legibilidad.
  const finalWidthCss = isInner ? m.containerRect!.width : m.viewportWidth;
  const finalWidthPx = Math.max(1, Math.round(finalWidthCss));
  const finalHeightPx = Math.max(1, Math.round(captureHeightCss));

  const chunks = buildChunks(finalWidthPx, finalHeightPx);
  console.log(
    `[money-chwats] imagen final (1x, gris): ${finalWidthPx}x${finalHeightPx} px en ${chunks.length} pedazo(s)`,
  );

  // Paso de scroll: 95% del viewport (deja 5% de overlap para tolerar desfases pequeños).
  const stepCss = Math.max(50, Math.floor(m.viewportHeight * (1 - OVERLAP_RATIO)));

  const MAX_ITER = 400; // Cap defensivo
  const NO_PROGRESS_THRESHOLD_PX = 4;
  try {
    let y = startScroll;
    let lastActualY = -Infinity;
    let noProgress = 0;
    let captures = 0;

    for (let iter = 0; iter < MAX_ITER; iter++) {
      const scrollResp = await tabAsk<{
        ok: true;
        actualY: number;
        scrollHeight: number;
      }>(tabId, { kind: "scroll-to", y });
      const actualY = scrollResp.actualY;
      const curScrollH = scrollResp.scrollHeight;

      // El virtualizador puede ajustar scrollTop ligeramente hacia atrás cuando
      // recicla items. Solo cortamos si NO HAY PROGRESO durante varias iteraciones.
      if (actualY - lastActualY < NO_PROGRESS_THRESHOLD_PX) {
        noProgress++;
        if (noProgress >= 3) {
          console.log("[money-chwats] sin progreso x3, fin de scroll");
          break;
        }
      } else {
        noProgress = 0;
      }
      lastActualY = actualY;

      await sleep(CAPTURE_DELAY_MS);
      const dataUrl = await chrome.tabs.captureVisibleTab(windowId, { format: "png" });
      const bitmap = await dataUrlToBitmap(dataUrl);

      const dstY = Math.round(actualY - startScroll); // píxeles CSS (1x)
      // Si el contenido creció más allá de lo medido, salimos (no hay canvas para más).
      if (dstY >= finalHeightPx) {
        bitmap.close();
        console.log("[money-chwats] dstY excede canvas final, fin");
        break;
      }

      if (isInner) {
        const r = m.containerRect!;
        // Fuente en píxeles físicos; destino en CSS (1x).
        const sx = Math.round(r.x * m.dpr);
        const sy = Math.round(r.y * m.dpr);
        const sw = Math.round(r.width * m.dpr);
        const sh = Math.round(r.height * m.dpr);
        drawSlice(chunks, bitmap, sx, sy, sw, sh, dstY, Math.round(r.width), Math.round(r.height));
      } else {
        drawSlice(
          chunks, bitmap, 0, 0, bitmap.width, bitmap.height,
          dstY, finalWidthPx, Math.round(m.viewportHeight),
        );
      }
      bitmap.close();
      captures++;

      // ¿Cubrimos hasta el fondo del contenido?
      if (actualY + m.viewportHeight >= curScrollH - 10) {
        console.log("[money-chwats] llegamos al fondo del contenido");
        break;
      }

      // Siempre avanzamos el "target" — aunque actualY haya retrocedido —
      // para que el bucle progrese.
      y = Math.max(y + stepCss, actualY + stepCss);
    }
    console.log(`[money-chwats] capturas totales: ${captures}`);
  } finally {
    await tabAsk(tabId, { kind: "restore" }).catch(() => undefined);
  }

  const partsB64: string[] = [];
  for (const chunk of chunks) {
    const blob = await chunk.canvas.convertToBlob({ type: "image/png" });
    partsB64.push(await blobToBase64(blob));
  }
  return partsB64;
}

async function captureActiveTab(): Promise<{
  capture_id: string;
  png_path_abs: string;
}> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.windowId) throw new Error("No hay pestaña activa.");

  const parts = await captureFullPage(tab.id, tab.windowId);

  // Nombre del encabezado de la conversación (DOM, exacto).
  let contactName: string | null = null;
  try {
    const r = await tabAsk<{ ok: true; name: string }>(tab.id, { kind: "contact-name" });
    contactName = r.name?.trim() || null;
  } catch {
    contactName = null;
  }

  const payload: CapturePayload = {
    client_version: VERSION,
    captured_at: new Date().toISOString(),
    tab_url: tab.url ?? null,
    tab_title: tab.title ?? null,
    contact_name: contactName,
    screenshot_parts_b64: parts,
  };
  const r = await desktop.capture(payload);
  return { capture_id: r.capture_id, png_path_abs: r.png_path_abs };
}

// Captura + procesa con IA en un solo paso. La captura queda guardada aunque el
// procesado falle; en ese caso devolvemos processError para informarlo.
async function captureAndProcess(): Promise<{
  capture_id: string;
  png_path_abs: string;
  result?: unknown;
  processError?: string;
}> {
  const cap = await captureActiveTab();
  try {
    const result = await desktop.process(cap.capture_id);
    return { ...cap, result };
  } catch (e) {
    return { ...cap, processError: (e as Error)?.message ?? "error al procesar" };
  }
}

async function flashBadge(success: boolean): Promise<void> {
  await chrome.action.setBadgeText({ text: success ? "OK" : "ERR" });
  await chrome.action.setBadgeBackgroundColor({ color: success ? "#25D366" : "#E53935" });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 2000);
}

type PopupRequest =
  | { kind: "ping-desktop" }
  | { kind: "capture-now" }
  | { kind: "open-file"; path: string; reveal: boolean }
  | { kind: "llm-status" }
  | { kind: "process"; capture_id: string };

chrome.runtime.onMessage.addListener((msg: PopupRequest, _sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.kind) {
        case "ping-desktop": {
          const h = await desktop.health();
          sendResponse({ ok: true, health: h });
          return;
        }
        case "capture-now": {
          const r = await captureAndProcess();
          await flashBadge(!r.processError);
          sendResponse({ ok: true, ...r });
          return;
        }
        case "open-file": {
          await desktop.openFile(msg.path, msg.reveal);
          sendResponse({ ok: true });
          return;
        }
        case "llm-status": {
          const s = await desktop.llmStatus();
          sendResponse({ ok: true, status: s });
          return;
        }
        case "process": {
          const r = await desktop.process(msg.capture_id);
          sendResponse({ ok: true, result: r });
          return;
        }
      }
    } catch (e) {
      const message =
        e instanceof DesktopServiceError
          ? e.message
          : (e as Error)?.message ?? "error desconocido";
      if (msg.kind === "capture-now") await flashBadge(false);
      sendResponse({ ok: false, error: message });
    }
  })();
  return true;
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "capture-current-chat") return;
  try {
    const r = await captureAndProcess();
    await flashBadge(!r.processError);
  } catch (e) {
    console.error("[money-chwats] capture failed:", e);
    await flashBadge(false);
  }
});

chrome.runtime.onInstalled.addListener(() => {
  console.log("[money-chwats] v" + VERSION + " instalada");
});
