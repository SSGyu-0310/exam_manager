'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getApiEnvelopeData, isApiEnvelopeOk, type ApiEnvelope } from '@/lib/api/contract';

interface User {
    id: number;
    email: string;
    is_admin: boolean;
}

type MePayload = {
    id: number;
    email: string;
    is_admin: boolean;
};

interface AuthContextType {
    user: User | null;
    login: () => Promise<void>;
    logout: () => Promise<void>;
    isAuthenticated: boolean;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    login: async () => { },
    logout: async () => { },
    isAuthenticated: false,
    isLoading: true,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        fetchUser();
    }, []);

    const fetchUser = async () => {
        setIsLoading(true);
        try {
            const res = await fetch('/api/proxy/api/auth/me', {
                credentials: "include",
            });
            if (res.ok) {
                const payload = (await res.json()) as ApiEnvelope<MePayload>;
                if (!isApiEnvelopeOk(payload)) {
                    setUser(null);
                    return;
                }
                const data = getApiEnvelopeData(payload);
                if (!data || typeof data.id !== "number") {
                    setUser(null);
                    return;
                }
                setUser({
                    id: data.id,
                    email: data.email,
                    is_admin: Boolean(data.is_admin),
                });
            } else {
                setUser(null);
            }
        } catch (error) {
            console.error('Failed to fetch user', error);
            setUser(null);
        } finally {
            setIsLoading(false);
        }
    };

    const login = async () => {
        await fetchUser();
    };

    const logout = async () => {
        try {
            await fetch('/api/proxy/api/auth/logout', { method: "POST", credentials: "include" });
        } catch (error) {
            console.error('Failed to logout', error);
        }
        setUser(null);
        router.push('/login');
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
