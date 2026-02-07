"use client";

import { useEffect, useState } from "react";
import { User, Shield, Cpu, LogOut, Info } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { apiFetch } from "@/lib/http";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface AppConfig {
    pdf_parser: string;
    local_admin: boolean;
    version: string;
    build_date: string;
}

export default function SettingsPage() {
    const { t } = useLanguage();
    const { user, logout } = useAuth();
    const [config, setConfig] = useState<AppConfig | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchConfig = async () => {
            try {
                const res = await apiFetch<any>("/api/dashboard/config");
                if (res.ok) {
                    setConfig(res.data);
                }
            } catch (error) {
                console.error("Failed to fetch settings config", error);
            } finally {
                setLoading(false);
            }
        };
        fetchConfig();
    }, []);

    const handleLogout = async () => {
        await logout();
        window.location.href = "/login";
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground">{t("common.settings")}</h1>
                <p className="text-muted-foreground">{t("manage.settings.profileDesc")}</p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                {/* Account Section */}
                <Card className="border-border bg-card">
                    <CardHeader>
                        <div className="flex items-center gap-2">
                            <User className="h-5 w-5 text-primary" />
                            <CardTitle>{t("manage.settings.profile")}</CardTitle>
                        </div>
                        <CardDescription>{t("manage.settings.profileDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex flex-col gap-1">
                            <span className="text-sm font-medium text-muted-foreground">{t("manage.settings.email")}</span>
                            <span className="text-foreground">{user?.email}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                            <span className="text-sm font-medium text-muted-foreground">{t("manage.settings.role")}</span>
                            <div className="flex items-center gap-2">
                                <Badge variant={user?.is_admin ? "success" : "neutral"}>
                                    {user?.is_admin ? t("manage.settings.admin") : t("manage.settings.user")}
                                </Badge>
                                {user?.is_admin && <Shield className="h-3 w-3 text-success" />}
                            </div>
                        </div>
                        <Button
                            variant="destructive"
                            className="mt-4 w-full justify-start gap-2"
                            onClick={handleLogout}
                        >
                            <LogOut className="h-4 w-4" /> {t("manage.settings.logout")}
                        </Button>
                    </CardContent>
                </Card>

                {/* System Section */}
                <Card className="border-border bg-card">
                    <CardHeader>
                        <div className="flex items-center gap-2">
                            <Cpu className="h-5 w-5 text-primary" />
                            <CardTitle>{t("manage.settings.system")}</CardTitle>
                        </div>
                        <CardDescription>{t("manage.settings.systemDesc")}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {loading ? (
                            <div className="space-y-3">
                                <div className="h-4 bg-muted animate-pulse rounded" />
                                <div className="h-4 bg-muted animate-pulse rounded" />
                                <div className="h-4 bg-muted animate-pulse rounded" />
                            </div>
                        ) : (
                            <>
                                <div className="flex justify-between items-center py-2 border-b border-border/50">
                                    <span className="text-sm text-muted-foreground">{t("manage.settings.version")}</span>
                                    <span className="text-sm font-medium text-foreground">{config?.version}</span>
                                </div>
                                <div className="flex justify-between items-center py-2 border-b border-border/50">
                                    <span className="text-sm text-muted-foreground">{t("manage.settings.parserMode")}</span>
                                    <Badge variant="neutral" className="capitalize">{config?.pdf_parser}</Badge>
                                </div>
                                <div className="flex justify-between items-center py-2 border-b border-border/50">
                                    <span className="text-sm text-muted-foreground">{t("manage.settings.localAdmin")}</span>
                                    <span className="text-sm font-medium text-foreground">{config?.local_admin ? t("manage.settings.enabled") : t("manage.settings.disabled")}</span>
                                </div>
                                <div className="flex items-center gap-2 mt-4 p-3 rounded-lg bg-primary/5 text-primary border border-primary/10">
                                    <Info className="h-4 w-4 shrink-0" />
                                    <p className="text-xs">{t("manage.settings.info")}</p>
                                </div>
                            </>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
