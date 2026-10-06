import { AppShell } from "@/components/app-shell";
import { requireAdmin } from "@/lib/server-api";

const NAV_ITEMS = [
  { href: "/types", label: "Test Case Types" },
  { href: "/users", label: "Users" },
  { href: "/audit-log", label: "Audit Log" },
];

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await requireAdmin();
  return (
    <AppShell user={user} navItems={NAV_ITEMS}>
      {children}
    </AppShell>
  );
}
