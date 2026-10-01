import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { requireUser } from "@/lib/server-api";

export default async function DashboardPage() {
  const user = await requireUser();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome, {user.full_name}</h1>
        <p className="text-muted-foreground">
          Projects, suites and runs land here in later phases (PRD §7.1).
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Nothing to show yet</CardTitle>
          <CardDescription>
            Once Phase 3 ships, recent suites, in-progress runs and pass-rate charts will appear
            here.
          </CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </div>
  );
}
