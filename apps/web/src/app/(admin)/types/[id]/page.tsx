import { TypeDetailClient } from "./type-detail-client";

export default async function TypeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TypeDetailClient typeId={id} />;
}
