"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { SiteNav } from "@/components/site-nav";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";

/**
 * Client-side auth guard. The `proxy.ts` (formerly middleware) does an
 * optimistic cookie sentinel check to redirect unauth users quickly, but
 * we still guard here so that a user whose tokens have been revoked gets
 * kicked out of the SPA.
 */
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  return (
    <>
      <SiteNav variant="app" />
      <main className="flex-1">
        <div className="mx-auto w-full max-w-6xl px-6 py-10">
          {isLoading || !user ? <DashboardSkeleton /> : children}
        </div>
      </main>
    </>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-4 w-80" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
