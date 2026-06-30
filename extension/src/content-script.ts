/**
 * Content script para capturas de página completa.
 * Detecta el contenedor scrolleable real (ventana o, si la ventana no scrollea,
 * el contenedor interno con MÁS ÁREA VISIBLE — esto evita elegir sidebars).
 * Genérico, sin lógica específica de ningún sitio.
 */

type Scroller = Window | HTMLElement;

interface MeasureResult {
  scrollWidth: number;
  scrollHeight: number;
  viewportWidth: number;
  viewportHeight: number;
  dpr: number;
  /** Posición inicial del scroll. Para contenedores internos, usamos esto como punto de arranque. */
  initialScrollTop: number;
  containerRect: { x: number; y: number; width: number; height: number } | null;
}

const state: {
  scroller: Scroller;
  originalScrollTop: number;
  styleEl: HTMLStyleElement | null;
  hiddenEls: { el: HTMLElement; prevVisibility: string }[];
} = {
  scroller: window,
  originalScrollTop: 0,
  styleEl: null,
  hiddenEls: [],
};

function getScrollTop(s: Scroller): number {
  return s === window ? (s as Window).scrollY : (s as HTMLElement).scrollTop;
}
function setScrollTop(s: Scroller, y: number): void {
  if (s === window) (s as Window).scrollTo(0, y);
  else (s as HTMLElement).scrollTop = y;
}
function getScrollHeight(s: Scroller): number {
  return s === window
    ? document.documentElement.scrollHeight
    : (s as HTMLElement).scrollHeight;
}
function getClientHeight(s: Scroller): number {
  return s === window ? (s as Window).innerHeight : (s as HTMLElement).clientHeight;
}

function findScroller(): Scroller {
  const docH = document.documentElement.scrollHeight;
  if (docH > window.innerHeight + 8) return window;

  type Candidate = { el: HTMLElement; area: number; right: number };
  const candidates: Candidate[] = [];
  document.querySelectorAll<HTMLElement>("*").forEach((el) => {
    const sh = el.scrollHeight;
    const ch = el.clientHeight;
    const cw = el.clientWidth;
    if (sh - ch <= 8 || ch < 100 || cw < 100) return;
    const style = getComputedStyle(el);
    if (!["auto", "scroll", "overlay"].includes(style.overflowY)) return;
    const rect = el.getBoundingClientRect();
    if (rect.width < 100 || rect.height < 100) return;
    if (rect.bottom < 0 || rect.top > window.innerHeight) return;
    candidates.push({
      el,
      area: rect.width * rect.height,
      right: rect.x + rect.width,
    });
  });
  if (candidates.length === 0) return window;
  candidates.sort((a, b) => {
    const areaDiff = b.area - a.area;
    if (Math.abs(areaDiff) > 5000) return areaDiff;
    return b.right - a.right;
  });
  return candidates[0].el;
}

function measure(): MeasureResult {
  state.scroller = findScroller();
  state.originalScrollTop = getScrollTop(state.scroller);
  const isWindow = state.scroller === window;
  const dpr = window.devicePixelRatio || 1;
  const sh = getScrollHeight(state.scroller);
  const ch = getClientHeight(state.scroller);
  const sw = isWindow
    ? document.documentElement.scrollWidth
    : (state.scroller as HTMLElement).scrollWidth;
  const vw = isWindow ? window.innerWidth : (state.scroller as HTMLElement).clientWidth;

  let containerRect: MeasureResult["containerRect"] = null;
  if (!isWindow) {
    const rect = (state.scroller as HTMLElement).getBoundingClientRect();
    containerRect = { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
  }
  return {
    scrollWidth: sw,
    scrollHeight: sh,
    viewportWidth: vw,
    viewportHeight: ch,
    dpr,
    initialScrollTop: state.originalScrollTop,
    containerRect,
  };
}

function hideStickyAndFixed(): void {
  // Esto esconde el globito flotante de fecha, headers sticky, banners, etc.
  // que cambian de contenido o posición entre capturas y causan tears.
  document.querySelectorAll<HTMLElement>("*").forEach((el) => {
    const pos = getComputedStyle(el).position;
    if (pos === "fixed" || pos === "sticky") {
      state.hiddenEls.push({ el, prevVisibility: el.style.visibility });
      el.style.visibility = "hidden";
    }
  });
}

function restoreHidden(): void {
  for (const { el, prevVisibility } of state.hiddenEls) {
    el.style.visibility = prevVisibility;
  }
  state.hiddenEls = [];
}

function prepare(): void {
  state.styleEl = document.createElement("style");
  state.styleEl.id = "mc-capture-style";
  state.styleEl.textContent = `
    html, body { scroll-behavior: auto !important; }
    *, *::before, *::after {
      animation: none !important;
      animation-duration: 0s !important;
      animation-delay: 0s !important;
      transition: none !important;
      transition-duration: 0s !important;
      transition-delay: 0s !important;
      caret-color: transparent !important;
    }
  `;
  document.documentElement.appendChild(state.styleEl);
  hideStickyAndFixed();
}

async function rafTwice(): Promise<void> {
  return new Promise<void>((r) =>
    requestAnimationFrame(() => requestAnimationFrame(() => r())),
  );
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/**
 * Hace scroll y espera hasta que tanto `scrollTop` como `scrollHeight` queden
 * estables por ≥240 ms — evita capturar a mitad de animación o cuando el
 * contenedor está cargando contenido nuevo (lazy load).
 */
async function scrollAndSettle(
  y: number,
): Promise<{ actualY: number; scrollHeight: number }> {
  setScrollTop(state.scroller, y);
  await rafTwice();
  await sleep(200);

  // Espera hasta que scrollTop + scrollHeight + clientHeight queden estables
  // por ≥400 ms (los virtualizadores tipo WhatsApp tardan en montar/desmontar items).
  let prevSnap = `${getScrollTop(state.scroller)}|${getScrollHeight(state.scroller)}`;
  let stable = 0;
  for (let i = 0; i < 40; i++) {
    await sleep(80);
    const curSnap = `${getScrollTop(state.scroller)}|${getScrollHeight(state.scroller)}`;
    if (curSnap === prevSnap) {
      stable++;
      if (stable >= 5) break; // ~400 ms estable
    } else {
      stable = 0;
      prevSnap = curSnap;
    }
  }
  // Margen extra para que el repaint termine antes del captureVisibleTab.
  await sleep(120);

  return {
    actualY: getScrollTop(state.scroller),
    scrollHeight: getScrollHeight(state.scroller),
  };
}

function restore(): void {
  restoreHidden();
  setScrollTop(state.scroller, state.originalScrollTop);
  if (state.styleEl) state.styleEl.remove();
  state.styleEl = null;
}

/**
 * Lee el nombre del contacto del ENCABEZADO de la conversación de WhatsApp Web.
 * Es la barra superior: [Nombre] · Videollamada · Llamada · Buscar · Menú.
 * Leemos el DOM (reactivo, sin clics) → nombre EXACTO, sin OCR ni adivinanzas.
 */
function getContactName(): string {
  const header = document.querySelector("#main header");
  if (!header) return "";
  // El nombre vive en un span con atributo title dentro del header.
  const conTitle = header.querySelector<HTMLElement>("span[title]");
  if (conTitle) {
    const t = conTitle.getAttribute("title") || conTitle.textContent || "";
    if (t.trim()) return t.trim();
  }
  // Respaldo: primer span con texto del header.
  const span = header.querySelector<HTMLElement>('span[dir="auto"]');
  return (span?.textContent || "").trim();
}

type Msg =
  | { kind: "ping" }
  | { kind: "measure" }
  | { kind: "prepare" }
  | { kind: "scroll-to"; y: number }
  | { kind: "restore" }
  | { kind: "contact-name" };

chrome.runtime.onMessage.addListener((msg: Msg, _sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.kind) {
        case "ping":
          sendResponse({ ok: true });
          return;
        case "measure":
          sendResponse({ ok: true, data: measure() });
          return;
        case "prepare":
          prepare();
          sendResponse({ ok: true });
          return;
        case "scroll-to": {
          const r = await scrollAndSettle(msg.y);
          sendResponse({ ok: true, ...r });
          return;
        }
        case "restore":
          restore();
          sendResponse({ ok: true });
          return;
        case "contact-name":
          sendResponse({ ok: true, name: getContactName() });
          return;
      }
    } catch (e) {
      sendResponse({ ok: false, error: (e as Error)?.message ?? "unknown" });
    }
  })();
  return true;
});
