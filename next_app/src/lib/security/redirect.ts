const SCHEME_PREFIX = /^[a-zA-Z][a-zA-Z0-9+.-]*:/;

function sanitizeRedirectTarget(value: string | null | undefined): string | null {
    if (typeof value !== 'string') {
        return null;
    }

    const target = value.trim();
    if (!target) {
        return null;
    }

    if (target.includes('\\')) {
        return null;
    }

    if (SCHEME_PREFIX.test(target)) {
        return null;
    }

    if (!target.startsWith('/')) {
        return null;
    }

    if (target.startsWith('//')) {
        return null;
    }

    return target;
}

export function normalizeRedirectTarget(raw: string | null | undefined, fallback: string): string {
    const safeFallback = sanitizeRedirectTarget(fallback) ?? '/';
    return sanitizeRedirectTarget(raw) ?? safeFallback;
}
