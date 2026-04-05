import { AppNav } from "@/components/AppNav";
import { RequireAuth } from "@/components/RequireAuth";
import { RequireVerifiedEmail } from "@/components/RequireVerifiedEmail";

export default function MainLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <RequireAuth>
      <RequireVerifiedEmail>
        <AppNav />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </RequireVerifiedEmail>
    </RequireAuth>
  );
}
