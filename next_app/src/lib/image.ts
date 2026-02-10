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

  const normalized = trimmed.replace(/\\/g, "/");
  const match = normalized.match(/^([^?#]*)([?#].*)?$/);
  const pathOnly = (match?.[1] || "").trim();
  const suffix = match?.[2] || "";
  if (!pathOnly) return null;

  if (pathOnly.startsWith("/static/")) {
    return `/api/proxy${pathOnly}${suffix}`;
  }
  if (pathOnly.startsWith("/uploads/")) {
    return `/api/proxy/static${pathOnly}${suffix}`;
  }
  if (pathOnly.startsWith("static/")) {
    return `/api/proxy/${pathOnly}${suffix}`;
  }
  if (pathOnly.startsWith("uploads/")) {
    return `/api/proxy/static/${pathOnly}${suffix}`;
  }

  const withoutLeading = pathOnly.replace(/^\/+/, "");
  const staticIndex = withoutLeading.lastIndexOf("static/");
  if (staticIndex >= 0) {
    return `/api/proxy/${withoutLeading.slice(staticIndex)}${suffix}`;
  }

  const uploadsIndex = withoutLeading.lastIndexOf("uploads/");
  if (uploadsIndex >= 0) {
    return `/api/proxy/static/${withoutLeading.slice(uploadsIndex)}${suffix}`;
  }

  return `/api/proxy/static/uploads/${withoutLeading}${suffix}`;
};
