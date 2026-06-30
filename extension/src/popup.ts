/**
 * Popup UI. Permite capturar, abrir la imagen, y procesarla con LLM.
 */

import { getServiceUrl } from "./lib/auth.js";
import type { LlmStatus, ProcessResponse } from "./lib/desktop-client.js";

function $<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) throw new Error("missing element: " + id);
  return el as T;
}

function log(node: HTMLElement | string, kind: "ok" | "err" | "" = ""): void {
  const box = $("log");
  const wrap = document.createElement("div");
  wrap.className = "entry" + (kind ? " " + kind : "");
  const ts = document.createElement("span");
  ts.className = "ts";
  ts.textContent = new Date().toLocaleTimeString();
  wrap.append(ts, document.createTextNode(" "));
  wrap.append(typeof node === "string" ? document.createTextNode(node) : node);
  box.prepend(wrap);
}

function setStatus(dotClass: "dot-ok" | "dot-err" | "dot-unknown", text: string): void {
  $("status-dot").className = "dot " + dotClass;
  $("status-text").textContent = text;
}

async function ask<T>(req: unknown): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    chrome.runtime.sendMessage(req, (resp: any) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!resp?.ok) {
        reject(new Error(resp?.error ?? "error desconocido"));
        return;
      }
      resolve(resp as T);
    });
  });
}

function setLlmStatus(s: LlmStatus): void {
  const el = $("llm-text");
  if (!s.enabled) {
    el.textContent = "deshabilitada";
    el.title = "";
  } else if (s.ready) {
    el.textContent = `lista (${s.selected})`;
    el.title = (s.available_models ?? []).join(", ");
  } else {
    el.textContent = "no lista";
    el.title = s.detail ?? "";
  }
  el.dataset.ready = s.ready ? "1" : "0";
}

async function refreshStatus(): Promise<void> {
  $("service-url").textContent = await getServiceUrl();
  const btn = $<HTMLButtonElement>("btn-capture");
  try {
    const r = await ask<{ ok: true; health: { version: string } }>({ kind: "ping-desktop" });
    setStatus("dot-ok", `vivo (v${r.health.version})`);
    btn.disabled = false;
    try {
      const llm = await ask<{ ok: true; status: LlmStatus }>({ kind: "llm-status" });
      setLlmStatus(llm.status);
    } catch {
      setLlmStatus({ enabled: false });
    }
  } catch (e) {
    setStatus("dot-err", "no responde");
    btn.disabled = true;
    log("desktop: " + (e as Error).message, "err");
  }
}

function captureLogNode(captureId: string, absPath: string): HTMLElement {
  const wrap = document.createElement("span");
  wrap.append(`captura OK · ${captureId.slice(0, 8)}…  `);

  const a1 = document.createElement("a");
  a1.href = "#";
  a1.className = "link";
  a1.textContent = "abrir imagen";
  a1.addEventListener("click", async (e) => {
    e.preventDefault();
    try {
      await ask({ kind: "open-file", path: absPath, reveal: false });
    } catch (err) {
      log("no se pudo abrir: " + (err as Error).message, "err");
    }
  });

  const a2 = document.createElement("a");
  a2.href = "#";
  a2.className = "link";
  a2.textContent = "ver en Finder";
  a2.addEventListener("click", async (e) => {
    e.preventDefault();
    try {
      await ask({ kind: "open-file", path: absPath, reveal: true });
    } catch (err) {
      log("no se pudo abrir: " + (err as Error).message, "err");
    }
  });

  wrap.append(a1, document.createTextNode("  ·  "), a2);
  return wrap;
}

function extractionLogNode(r: ProcessResponse): HTMLElement {
  const c = r.extraction.cliente ?? {};
  const wrap = document.createElement("span");
  wrap.innerHTML =
    `IA OK · cliente: <b>${escapeHtml(c.nombre || "sin nombre")}</b> ` +
    `(${escapeHtml(c.sentimiento_general || "?")}, ` +
    `${r.pedidos_added} pedido${r.pedidos_added === 1 ? "" : "s"}, ` +
    `conf ${((c.confianza_extraccion ?? 0) * 100).toFixed(0)}%)` +
    (r.requiere_revision ? " <em>· requiere revisión</em>" : "");
  return wrap;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[m]!));
}

async function onCapture(): Promise<void> {
  const btn = $<HTMLButtonElement>("btn-capture");
  btn.disabled = true;
  btn.textContent = "Capturando y analizando…";
  try {
    const r = await ask<{
      ok: true;
      capture_id: string;
      png_path_abs: string;
      result?: ProcessResponse;
      processError?: string;
    }>({ kind: "capture-now" });
    log(captureLogNode(r.capture_id, r.png_path_abs), "ok");
    // La IA corre sola en el backend; mostramos su resultado de una vez.
    if (r.result) {
      log(extractionLogNode(r.result), "ok");
    } else if (r.processError) {
      log("IA: " + r.processError, "err");
    }
  } catch (e) {
    log("error: " + (e as Error).message, "err");
  } finally {
    btn.disabled = false;
    btn.textContent = "Capturar pestaña";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("btn-capture").addEventListener("click", onCapture);
  refreshStatus();
});
