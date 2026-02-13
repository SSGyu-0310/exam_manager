'use client';

import { useState, Suspense } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { getApiEnvelopeMessage, type ApiEnvelope } from '@/lib/api/contract';
import { normalizeRedirectTarget } from '@/lib/security/redirect';

function LoginForm() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        try {
            const res = await fetch('/api/proxy/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
                credentials: "include",
            });

            if (res.ok) {
                await res.json();
                await login();
                const from = searchParams.get('from');
                const target = normalizeRedirectTarget(from, '/dashboard');
                router.replace(target);
                router.refresh();
            } else {
                const payload = (await res.json()) as ApiEnvelope<unknown>;
                setError(getApiEnvelopeMessage(payload, 'Login failed'));
            }
        } catch {
            setError('An unexpected error occurred');
        }
    };

    return (
        <div className="w-full max-w-md space-y-8 p-8 bg-white rounded-xl shadow-lg">
            <div className="text-center">
                <h2 className="mt-6 text-3xl font-bold text-gray-900">Sign in to your account</h2>
            </div>
            <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                <div className="space-y-4">
                    <div>
                        <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email address</label>
                        <input
                            id="email"
                            name="email"
                            type="email"
                            required
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-indigo-500"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                    </div>
                    <div>
                        <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
                        <input
                            id="password"
                            name="password"
                            type="password"
                            required
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-indigo-500"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                        />
                    </div>
                </div>

                {error && <div className="text-red-500 text-sm text-center">{error}</div>}

                <div>
                    <button
                        type="submit"
                        className="group relative flex w-full justify-center rounded-md border border-transparent bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                    >
                        Sign in
                    </button>
                </div>
                <div className="text-center text-sm">
                    <Link href="/register" className="font-medium text-indigo-600 hover:text-indigo-500">
                        Don&apos;t have an account? Sign up
                    </Link>
                </div>
            </form>
        </div>
    );
}

function LoginFormFallback() {
    return (
        <div className="w-full max-w-md space-y-8 p-8 bg-white rounded-xl shadow-lg animate-pulse">
            <div className="text-center">
                <div className="mt-6 h-9 w-64 bg-gray-200 rounded mx-auto" />
            </div>
            <div className="mt-8 space-y-6">
                <div className="space-y-4">
                    <div className="h-16 bg-gray-200 rounded" />
                    <div className="h-16 bg-gray-200 rounded" />
                </div>
                <div className="h-10 bg-gray-200 rounded" />
            </div>
        </div>
    );
}

export default function LoginPage() {
    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
            <Suspense fallback={<LoginFormFallback />}>
                <LoginForm />
            </Suspense>
        </div>
    );
}
