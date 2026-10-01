import { ReportDetailClient } from "./report-detail-client";

export default async function ReportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReportDetailClient reportId={id} />;
}
