/**
 * Configuración mínima en chrome.storage.local: solo la URL del servicio.
 * No hay shared secret — el servicio escucha en localhost.
 */

const KEY_SERVICE_URL = "money_chwats:serviceUrl";

export const DEFAULT_SERVICE_URL = "http://127.0.0.1:5000";

export async function getServiceUrl(): Promise<string> {
  const out = await chrome.storage.local.get([KEY_SERVICE_URL]);
  return out[KEY_SERVICE_URL] ?? DEFAULT_SERVICE_URL;
}

export async function setServiceUrl(url: string): Promise<void> {
  await chrome.storage.local.set({ [KEY_SERVICE_URL]: url });
}
