"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdvisorRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);
  return (
    <p className="text-gray-500">Redirecting to Overview...</p>
  );
}
