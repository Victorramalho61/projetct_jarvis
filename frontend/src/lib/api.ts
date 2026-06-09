declare const __API_URL__: string;
const BASE = typeof __API_URL__ !== "undefined" ? __API_URL__ : "";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

let _onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(fn: () => void): void {
  _onUnauthorized = fn;
}

const API_TIMEOUT_MS = 30_000;

type FetchOptions = Omit<RequestInit, "body"> & {
  token?: string | null;
  json?: unknown;
  timeoutMs?: number;
  onHeaders?: (headers: Headers) => void;
};

export async function apiFetch<T = unknown>(
  path: string,
  { token, json, timeoutMs = API_TIMEOUT_MS, signal: userSignal, onHeaders, ...init }: FetchOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";

  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  if (userSignal) {
    userSignal.addEventListener("abort", () => controller.abort(userSignal.reason), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      if (timedOut) throw new ApiError(0, `Tempo limite excedido (${timeoutMs / 1000}s). Tente novamente.`);
      throw err;
    }
    throw new ApiError(0, "Sem conexão com o servidor.");
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    if (response.status === 401 && _onUnauthorized) {
      _onUnauthorized();
    }
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      (body as { detail?: string }).detail ?? `Erro ${response.status}`
    );
  }

  if (onHeaders) onHeaders(response.headers);

  const contentType = response.headers.get("content-type") ?? "";
  if (response.status === 204 || !contentType.includes("application/json")) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
