"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function LandingPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, isLoading, router]);

  const { t } = useLanguage();

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">{t("common.loading")}</div>;
  }

  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center space-y-8 text-center">
      <div className="space-y-4">
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          {t("landing.title")}
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          {t("landing.subtitle")}
        </p>
      </div>
      <div className="flex gap-4">
        <Link href="/login">
          <Button size="lg" className="min-w-[120px]">
            {t("landing.loginButton")}
          </Button>
        </Link>
        <Link href="/register">
          <Button size="lg" variant="outline" className="min-w-[120px]">
            {t("landing.signupButton")}
          </Button>
        </Link>
      </div>
    </div>
  );
}
