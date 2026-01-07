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
  return `/api/proxy${normalized}`;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}) {
  const response = await fetch(buildProxyUrl(path), init);

  if (!response.ok) {
    let message = response.statusText || "Request failed";
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
