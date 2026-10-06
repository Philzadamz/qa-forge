import { requireUser } from "@/lib/server-api";

import { DashboardView } from "./dashboard-view";

export default async function DashboardPage() {
  const user = await requireUser();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome, {user.full_name}</h1>
        <p className="text-muted-foreground">Usage across the projects you can access.</p>
      </div>
      <DashboardView />
    </div>
  );
}
