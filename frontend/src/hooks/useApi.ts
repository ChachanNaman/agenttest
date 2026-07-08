import { useCallback, useState } from "react";

const API_BASE = "/api";

interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function useApi<T>() {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: false });

  const run = useCallback(async (path: string, options?: RequestInit) => {
    setState({ data: null, error: null, loading: true });
    try {
      const data = await request<T>(path, options);
      setState({ data, error: null, loading: false });
      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      setState({ data: null, error: message, loading: false });
      throw err;
    }
  }, []);

  return { ...state, run };
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    await request<{ status: string }>("/health");
    return true;
  } catch {
    return false;
  }
}
