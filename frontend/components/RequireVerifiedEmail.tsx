"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "./AuthProvider";

/** Blocks app until Firebase emailVerified (signup flow). */
export function RequireVerifiedEmail({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading || !user) return;
    if (!user.emailVerified) {
      router.replace("/verify-email");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-gray-400">
        Loading…
      </div>
    );
  }
  if (!user) return null;
  if (!user.emailVerified) return null;
  return <>{children}</>;
}
