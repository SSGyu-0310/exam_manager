export type ApiEnvelope<T> = {
  ok?: boolean;
  code?: string;
  message?: string;
  data?: T;
  success?: boolean;
  error?: string;
  msg?: string;
} & Partial<T>;

export function isApiEnvelopeOk(payload: { ok?: boolean; success?: boolean } | null | undefined) {
  if (!payload) return false;
  if (typeof payload.ok === "boolean") return payload.ok;
  if (typeof payload.success === "boolean") return payload.success;
  return true;
}

export function getApiEnvelopeData<T>(payload: ApiEnvelope<T> | null | undefined) {
  if (!payload) return undefined;
  if (payload.data !== undefined) {
    return payload.data;
  }
  return payload as T;
}

export function getApiEnvelopeMessage(
  payload: { message?: string; error?: string; msg?: string } | null | undefined,
  fallback: string
) {
  if (!payload) return fallback;
  return payload.message || payload.error || payload.msg || fallback;
}
