import { NextResponse } from "next/server";
import { backend, getRecord, saveRecord } from "@/lib/analyses-server";
import { requireUser } from "@/lib/server-user";

export const dynamic = "force-dynamic";

/** Status atau hasil satu analisis; hanya pemiliknya yang boleh membaca. */
export async function GET(_: Request, { params }: { params: { id: string } }) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const record = await getRecord(user, params.id);
  if (!record) return NextResponse.json({ error: "Analisis tidak ditemukan." }, { status: 404 });

  const res = await backend(`/${encodeURIComponent(params.id)}`).catch(() => null);
  const data = res ? await res.json().catch(() => null) : null;
  if (!res || !res.ok || !data) {
    return NextResponse.json({ error: data?.detail ?? "Server analisis tidak dapat dihubungi." }, { status: res?.status === 404 ? 404 : 502 });
  }

  // Ringkasan hasil disalin ke riwayat sekali, saat analisis selesai atau gagal.
  if ((data.status === "done" || data.status === "failed") && record.status !== data.status) {
    const conf = data.current_probabilities && data.current_regime ? data.current_probabilities[data.current_regime] : null;
    await saveRecord(user, {
      ...record,
      status: data.status,
      current_regime: data.current_regime ?? null,
      confidence: conf,
      low_confidence: data.current_low_confidence ?? null,
      error: data.error ?? null,
    });
  }
  return NextResponse.json(data);
}
