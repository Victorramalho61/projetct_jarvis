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

type FetchOptions = Omit<RequestInit, "body"> & {
  token?: string | null;
  json?: unknown;
};

export async function apiFetch<T = unknown>(
  path: string,
  { token, json, ...init }: FetchOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "Sem conexão com o servidor.");
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

  const contentType = response.headers.get("content-type") ?? "";
  if (response.status === 204 || !contentType.includes("application/json")) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
