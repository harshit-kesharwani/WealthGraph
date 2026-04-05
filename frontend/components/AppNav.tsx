"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";

const links = [
  { href: "/dashboard", label: "Overview" },
  { href: "/policy", label: "Goals & limits" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/live-advisor", label: "Live AI Advisor" },
  { href: "/inbox", label: "Updates" },
  { href: "/demo", label: "Try scenarios" },
];

export function AppNav() {
  const path = usePathname();
  return (
    <header className="border-b border-gray-800 bg-ink-900/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-3">
        <Link href="/dashboard" className="font-display text-lg font-semibold text-mint-400">
          WealthGraph
        </Link>
        <nav className="flex flex-wrap gap-1 text-sm">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-md px-3 py-1.5 ${
                path === l.href
                  ? "bg-mint-500/20 text-mint-400"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <button
          type="button"
          onClick={() => signOut(getFirebaseAuth())}
          className="text-sm text-gray-500 hover:text-white"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
