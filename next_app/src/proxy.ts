import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Routes that require authentication
const protectedRoutes = ['/dashboard', '/learn', '/manage', '/review'];

// Routes that should redirect to dashboard if already logged in
const authRoutes = ['/login', '/register'];

export function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl;
    const searchParams = request.nextUrl.searchParams;

    // Check if user has auth token
    const hasAuthToken = request.cookies.has('auth_token');

    // Redirect to login if accessing protected route without auth
    if (protectedRoutes.some(route => pathname.startsWith(route)) && !hasAuthToken) {
        const loginUrl = new URL('/login', request.url);
        loginUrl.searchParams.set('from', pathname);
        return NextResponse.redirect(loginUrl);
    }

    const isAuthRoute = authRoutes.some(route => pathname.startsWith(route));
    const hasRedirectIntent = searchParams.has('from') || searchParams.has('force');

    // Redirect to dashboard if accessing auth routes while logged in
    if (isAuthRoute && hasAuthToken && !hasRedirectIntent) {
        return NextResponse.redirect(new URL('/dashboard', request.url));
    }

    return NextResponse.next();
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - api (API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         */
        '/((?!api|_next/static|_next/image|favicon.ico).*)',
    ],
};
