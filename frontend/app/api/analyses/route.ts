import { NextResponse } from "next/server";
import { backend, consumeQuota, DAILY_LIMIT, listRecords, quotaUsed, refundQuota, saveRecord } from "@/lib/analyses-server";
import { requireUser } from "@/lib/server-user";

export const dynamic = "force-dynamic";

/** Riwayat analisis pengguna dan sisa kuota hari ini. */
export async function GET() {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const [items, used] = await Promise.all([listRecords(user), quotaUsed(user)]);
  return NextResponse.json({ items, quota: { used, limit: DAILY_LIMIT, remaining: Math.max(0, DAILY_LIMIT - used) } });
}

/** Mulai analisis baru; memakai satu kuota hanya bila backend menerima permintaan. */
export async function POST(req: Request) {
  const user = await requireUser();
  if (user instanceof NextResponse) return user;
  const body = await req.json().catch(() => null);
  if (!body || typeof body.symbol !== "string" || typeof body.source !== "string" || typeof body.timeframe !== "string") {
    return NextResponse.json({ error: "Isian analisis tidak lengkap." }, { status: 400 });
  }

  if (!(await consumeQuota(user))) {
    return NextResponse.json(
      { error: `Kuota analisis hari ini habis (${DAILY_LIMIT} per hari). Coba lagi besok setelah pukul 00.00 WIB.` },
      { status: 429 },
    );
  }

  const res = await backend("", {
    method: "POST",
    body: JSON.stringify({ source: body.source, symbol: body.symbol, timeframe: body.timeframe, bars: Number(body.bars) || 2000 }),
  }).catch(() => null);
  const data = res ? await res.json().catch(() => null) : null;
  if (!res || !res.ok || !data?.id) {
    await refundQuota(user);
    const status = res && res.status >= 400 && res.status < 500 ? 400 : 502;
    return NextResponse.json({ error: data?.detail ?? "Server analisis tidak dapat dihubungi." }, { status });
  }

  await saveRecord(user, {
    id: data.id,
    source: data.source,
    symbol: data.symbol,
    timeframe: data.timeframe,
    bars: data.n_bars,
    created_at: Math.floor(Date.now() / 1000),
    status: "queued",
  });
  return NextResponse.json(data);
}
