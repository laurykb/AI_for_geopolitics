/** /monde a fusionné avec le théâtre : la carte EST la scène (G1). */

import { redirect } from "next/navigation";

export default async function MondePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/games/${id}`);
}
