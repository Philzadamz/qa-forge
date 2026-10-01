import { AppShell } from "@/components/app-shell";
import { requireUser } from "@/lib/server-api";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects", label: "Projects" },
];
const ADMIN_NAV_ITEMS = [{ href: "/types", label: "Admin Console" }];

export default async function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();
  const navItems = user.role === "admin" ? [...NAV_ITEMS, ...ADMIN_NAV_ITEMS] : NAV_ITEMS;
  return (
    <AppShell user={user} navItems={navItems}>
      {children}
    </AppShell>
  );
}
