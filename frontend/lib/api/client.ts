// Central fetch wrapper: base URL, Bearer auth, transparent 401→refresh→retry,
// and error normalization. All resource modules build on top of this.

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

const ACCESS_KEY = "js.access_token";
const REFRESH_KEY = "js.refresh_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---- token storage (localStorage; backend auth is stateless Bearer) ----
export const tokenStore = {
  get access() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_KEY, access);
    if (refresh) window.localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
  get isAuthenticated() {
    return Boolean(this.access);
  },
};

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      // FastAPI validation error shape
      return data.detail.map((e: { msg?: string }) => e.msg).filter(Boolean).join("; ") || res.statusText;
    }
    return res.statusText;
  } catch {
    return res.statusText || `Request failed (${res.status})`;
  }
}

let refreshInFlight: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  const refresh = tokenStore.refresh;
  if (!refresh) return null;
  // De-dupe concurrent refreshes.
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_URL}/api/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return null;
        const data = await res.json();
        tokenStore.set(data.access_token);
        return data.access_token as string;
      } catch {
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** When true, `body` is sent as-is (e.g. FormData) and Content-Type is left to the browser. */
  raw?: boolean;
  auth?: boolean;
  /** Resolve to a Blob instead of parsed JSON — for binary responses like question audio. */
  blob?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, raw = false, auth = true, blob = false } = opts;

  const doFetch = async (token: string | null): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (auth && token) headers["Authorization"] = `Bearer ${token}`;
    let payload: BodyInit | undefined;
    if (body !== undefined) {
      if (raw) {
        payload = body as BodyInit;
      } else {
        headers["Content-Type"] = "application/json";
        payload = JSON.stringify(body);
      }
    }
    return fetch(`${API_URL}${path}`, { method, headers, body: payload });
  };

  let res = await doFetch(tokenStore.access);

  // Transparent refresh on a single 401.
  if (res.status === 401 && auth && tokenStore.refresh) {
    const newToken = await tryRefresh();
    if (newToken) {
      res = await doFetch(newToken);
    } else {
      tokenStore.clear();
    }
  }

  if (res.status === 401 && auth) {
    tokenStore.clear();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res));
  }

  if (res.status === 204) return undefined as T;
  if (blob) return (await res.blob()) as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  getBlob: (path: string) => request<Blob>(path, { method: "GET", blob: true }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form, raw: true }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  // Unauthenticated variants for the auth endpoints themselves.
  postPublic: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body, auth: false }),
};

export { API_URL };
