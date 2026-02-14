export type HttpErrorPayload = {
  ok: false;
  status: number;
  message: string;
};

export class HttpError extends Error {
  payload: HttpErrorPayload;

  constructor(payload: HttpErrorPayload) {
    super(payload.message);
    this.payload = payload;
  }
}

function buildProxyUrl(path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const proxyPath = `/api/proxy${normalized}`;
  if (typeof window === "undefined") {
    const baseUrl = (
      process.env.NEXT_PUBLIC_SITE_URL ||
      process.env.NEXT_PUBLIC_APP_URL ||
      "http://localhost:4000"
    ).replace(/\/$/, "");
    return `${baseUrl}${proxyPath}`;
  }
  return proxyPath;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers ?? {});
  if (typeof window === "undefined") {
    try {
      const { cookies } = await import("next/headers");
      const cookieStore = await cookies();
      const cookieHeader = cookieStore
        .getAll()
        .map((cookie: { name: string; value: string }) => `${cookie.name}=${cookie.value}`)
        .join("; ");
      if (cookieHeader && !headers.has("cookie")) {
        headers.set("cookie", cookieHeader);
      }
    } catch {
      // noop
    }
  } else {
    // Client-side: attach CSRF token for mutation requests
    const method = (init.method || "GET").toUpperCase();
    if (["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
      const csrfToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrf_access_token="))
        ?.split("=")[1];
      if (csrfToken && !headers.has("X-CSRF-TOKEN")) {
        headers.set("X-CSRF-TOKEN", csrfToken);
      }
    }
  }
  const response = await fetch(buildProxyUrl(path), {
    ...init,
    headers,
    credentials: init.credentials ?? "include",
  });

  if (!response.ok) {
    let message = response.statusText || "Request failed";

    // Handle 401 Unauthorized on client side
    if (response.status === 401 && typeof window !== "undefined") {
      const currentPath = window.location.pathname;
      if (!currentPath.startsWith("/login") && !currentPath.startsWith("/register")) {
        const currentUrl = `${currentPath}${window.location.search}`;
        window.location.href = `/login?from=${encodeURIComponent(currentUrl)}`;
      }
      throw new HttpError({
        ok: false,
        status: 401,
        message: "Authentication required - redirecting to login",
      });
    }

    try {
      const data = await response.json();
      if (data && typeof data.message === "string") {
        message = data.message;
      } else if (data && typeof data.error === "string") {
        message = data.error;
      }
    } catch {
      try {
        message = await response.text();
      } catch {
        // noop
      }
    }

    throw new HttpError({ ok: false, status: response.status, message });
  }

  return (await response.json()) as T;
}
