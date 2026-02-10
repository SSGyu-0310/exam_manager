const ABSOLUTE_URL_PATTERN = /^[a-zA-Z][a-zA-Z\d+\-.]*:/;

export const resolveImageUrl = (value?: string | null): string | null => {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;

  if (ABSOLUTE_URL_PATTERN.test(trimmed)) {
    return trimmed;
  }
  if (trimmed.startsWith("/api/proxy/")) {
    return trimmed;
  }

  if (trimmed.startsWith("/static/")) {
    return `/api/proxy${trimmed}`;
  }
  if (trimmed.startsWith("/uploads/")) {
    return `/api/proxy/static${trimmed}`;
  }
  if (trimmed.startsWith("static/")) {
    return `/api/proxy/${trimmed}`;
  }
  if (trimmed.startsWith("uploads/")) {
    return `/api/proxy/static/${trimmed}`;
  }

  const normalized = trimmed.replace(/^\/+/, "");
  return `/api/proxy/static/uploads/${normalized}`;
};
