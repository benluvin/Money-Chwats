/**
 * Cliente HTTP del servicio desktop. Sin auth — localhost-only.
 */

import { getServiceUrl } from "./auth.js";

export interface HealthResponse {
  status: string;
  version: string;
}

export interface CaptureResponse {
  capture_id: string;
  status: string;
  png_path: string;
  png_path_abs: string;
}

export interface CapturePayload {
  client_version: string;
  captured_at: string;
  tab_url: string | null;
  tab_title: string | null;
  /** Una o varias PNG en base64. El desktop las une verticalmente en una sola imagen. */
  screenshot_parts_b64: string[];
}

export class DesktopServiceError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${(await getServiceUrl()).replace(/\/$/, "")}${path}`;
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const r = await fetch(url, { ...init, headers });
  if (!r.ok) {
    let detail = "";
    try {
      const body = await r.json();
      detail = body?.detail ?? JSON.stringify(body);
    } catch {
      detail = await r.text().catch(() => "");
    }
    throw new DesktopServiceError(r.status, `${r.status} ${r.statusText} — ${detail}`);
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export interface LlmStatus {
  enabled: boolean;
  ready?: boolean;
  selected?: string;
  available_models?: string[];
  error?: string;
  detail?: string;
}

export interface ProcessResponse {
  capture_id: string;
  cliente_id: string;
  extraction: any;
  cliente_updated: boolean;
  pedidos_added: number;
  requiere_revision: boolean;
  csv_pending: boolean;
}

export const desktop = {
  health(): Promise<HealthResponse> {
    return call<HealthResponse>("/health");
  },
  capture(payload: CapturePayload): Promise<CaptureResponse> {
    return call<CaptureResponse>("/capture", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  openFile(path: string, reveal: boolean): Promise<void> {
    return call<void>("/open", {
      method: "POST",
      body: JSON.stringify({ path, reveal }),
    });
  },
  llmStatus(): Promise<LlmStatus> {
    return call<LlmStatus>("/llm/status");
  },
  process(captureId: string): Promise<ProcessResponse> {
    return call<ProcessResponse>(`/process/${captureId}`, { method: "POST" });
  },
};
