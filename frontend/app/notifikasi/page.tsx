"use client";

import { useEffect, useRef, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { useUser } from "@/components/UserContext";

/**
 * Langganan notifikasi Telegram.
 *
 * Pengguna tidak perlu tahu chat ID-nya: tombol "Hubungkan" membuat kode sekali
 * pakai dan membuka bot di Telegram. Begitu pengguna menekan Start, backend
 * menautkan chat itu ke akun ini, dan halaman ini mendeteksinya otomatis.
 */

const TF_LABEL: Record<string, string> = { "1h": "1H (lebih sering, ±4 jam per window)", "4h": "4H (lebih jarang, ±16 jam per window)" };

async function call(method: string, url: string, body?: unknown) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data;
}

function Toggle({ id, checked, onChange, disabled, label }: {
  id: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string;
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50 ${
        checked ? "border-accent bg-accent/80" : "border-edgeBright bg-surface"
      }`}
    >
      <span className={`absolute top-0.5 h-[18px] w-[18px] rounded-full bg-txt transition-all ${checked ? "left-[22px]" : "left-0.5"}`} />
    </button>
  );
}

export default function NotifikasiPage() {
  const { me, loading, reload } = useUser();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [waitingUntil, setWaitingUntil] = useState<number | null>(null);
  const [linkUrl, setLinkUrl] = useState<string | null>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  const tg = me?.telegram ?? null;
  const ready = Boolean(me?.firestore && me?.bot_username);

  // Setelah tautan dibuka, periksa /api/me berkala sampai Telegram terhubung.
  useEffect(() => {
    if (!waitingUntil) return;
    poll.current = setInterval(async () => {
      const fresh = await reload();
      if (fresh?.telegram || Date.now() > waitingUntil) {
        setWaitingUntil(null);
        setLinkUrl(null);
        if (fresh?.telegram) setNotice("Telegram terhubung. Notifikasi 1H aktif.");
      }
    }, 3000);
    return () => {
      if (poll.current) clearInterval(poll.current);
    };
  }, [waitingUntil, reload]);

  const act = async (key: string, fn: () => Promise<unknown>, done?: string) => {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      await fn();
      await reload();
      if (done) setNotice(done);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const connect = () =>
    act("link", async () => {
      const { url, expires_at } = await call("POST", "/api/telegram/link");
      setLinkUrl(url);
      setWaitingUntil(new Date(expires_at).getTime());
      window.open(url, "_blank", "noopener");
    });

  const setTimeframe = (tf: string, on: boolean) => {
    if (!tg) return;
    const next = on ? Array.from(new Set([...tg.timeframes, tf])) : tg.timeframes.filter((t) => t !== tf);
    if (!next.length) {
      setError("Pilih minimal satu timeframe, atau matikan notifikasi.");
      return;
    }
    void act(`tf-${tf}`, () => call("PATCH", "/api/telegram", { timeframes: next }));
  };

  return (
    <div className="mx-auto max-w-[1100px] space-y-3">
      <PageHeader
        title="Notifikasi Telegram"
        description="Terima pesan Telegram setiap kali regime BTC/USDT berganti. Pergantian diumumkan setelah terkonfirmasi beberapa window berturut-turut supaya tidak bolak-balik. Setiap notifikasi juga dicatat sebagai bukti uji maju (forward test) penelitian."
      />

      {loading && <div className="h-40 animate-pulse rounded border border-edge bg-surface/40" />}

      {error && (
        <div role="alert" className="rounded border border-bearish/40 bg-bearish/10 px-3 py-2 text-[12px] text-bearish">{error}</div>
      )}
      {notice && (
        <div role="status" className="rounded border border-bullish/40 bg-bullish/10 px-3 py-2 text-[12px] text-bullish">{notice}</div>
      )}

      {!loading && me && (
        <div className="grid gap-3 lg:grid-cols-[1.25fr_1fr]">
          <section className="panel space-y-4">
            {!ready && (
              <div className="space-y-2">
                <div className="panel-title">Belum dikonfigurasi</div>
                <p className="text-[12.5px] leading-relaxed text-txtDim">
                  Server belum terhubung ke {me.firestore ? "bot Telegram" : "Firestore"}. Isi{" "}
                  {me.firestore ? (
                    <code className="font-mono text-txt">NEXT_PUBLIC_TELEGRAM_BOT_USERNAME</code>
                  ) : (
                    <code className="font-mono text-txt">FIREBASE_SERVICE_ACCOUNT</code>
                  )}{" "}
                  di <code className="font-mono text-txt">frontend/.env.local</code>, lalu jalankan ulang frontend. Panduan lengkap ada di
                  README bagian Notifikasi Telegram.
                </p>
              </div>
            )}

            {ready && !tg && (
              <>
                <div>
                  <div className="panel-title">Hubungkan Telegram</div>
                  <div className="panel-sub">Tidak perlu mencari chat ID. Cukup tiga langkah:</div>
                </div>
                <ol className="grid gap-2.5 text-[12.5px] text-txtDim">
                  {[
                    ["Klik Hubungkan Telegram", "Telegram terbuka ke bot @" + me.bot_username + " dengan kode sekali pakai."],
                    ["Tekan Start di Telegram", "Bot menautkan chat Anda ke akun ini."],
                    ["Selesai", "Halaman ini mendeteksi tautan otomatis. Notifikasi 1H langsung aktif."],
                  ].map(([title, text], i) => (
                    <li key={title} className="flex gap-3">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-edgeBright font-mono text-[11px] text-txt">
                        {i + 1}
                      </span>
                      <div>
                        <div className="font-medium text-txt">{title}</div>
                        <div className="text-[12px] text-txtMuted">{text}</div>
                      </div>
                    </li>
                  ))}
                </ol>

                <button
                  type="button"
                  onClick={() => void connect()}
                  disabled={busy !== null || waitingUntil !== null}
                  className="h-10 rounded-md bg-accent px-4 text-[13px] font-semibold text-panelAlt transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
                >
                  {waitingUntil ? "Menunggu Anda menekan Start di Telegram…" : busy === "link" ? "Membuat kode…" : "Hubungkan Telegram"}
                </button>

                {linkUrl && (
                  <p className="text-[11.5px] leading-relaxed text-txtMuted">
                    Telegram tidak terbuka?{" "}
                    <a href={linkUrl} target="_blank" rel="noopener noreferrer" className="text-accent underline underline-offset-2">
                      Buka tautan ini
                    </a>
                    . Kode berlaku 15 menit dan hanya bisa dipakai sekali.
                  </p>
                )}
                {me.user.demo && (
                  <p className="text-[11.5px] text-warn">
                    Anda memakai mode demo. Telegram akan ditautkan ke akun demo bersama, bukan akun pribadi.
                  </p>
                )}
              </>
            )}

            {ready && tg && (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="metric-label">Terhubung ke</div>
                    <div className="mt-1 text-[16px] font-semibold text-txt">
                      {tg.username ? `@${tg.username}` : tg.first_name ?? `chat ${tg.chat_id}`}
                    </div>
                    {tg.linked_at && (
                      <div className="text-2xs text-txtMuted">
                        sejak {new Date(tg.linked_at).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" })}
                      </div>
                    )}
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-2xs font-semibold ${tg.enabled ? "bg-bullish/15 text-bullish" : "bg-surface text-txtMuted"}`}>
                    {tg.enabled ? "Aktif" : "Dijeda"}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-4 rounded-md border border-edge bg-surface/50 px-3 py-2.5">
                  <label htmlFor="tg-enabled" className="text-[12.5px] text-txt">
                    Kirim notifikasi
                    <span className="block text-2xs text-txtMuted">Matikan untuk jeda tanpa memutus tautan.</span>
                  </label>
                  <Toggle
                    id="tg-enabled"
                    label="Kirim notifikasi"
                    checked={tg.enabled}
                    disabled={busy !== null}
                    onChange={(v) => void act("enabled", () => call("PATCH", "/api/telegram", { enabled: v }))}
                  />
                </div>

                <fieldset className="space-y-1.5">
                  <legend className="metric-label mb-1">Timeframe</legend>
                  {(["1h", "4h"] as const).map((tf) => (
                    <label key={tf} htmlFor={`tf-${tf}`} className="flex cursor-pointer items-center gap-2.5 text-[12.5px] text-txtDim">
                      <input
                        id={`tf-${tf}`}
                        type="checkbox"
                        checked={tg.timeframes.includes(tf)}
                        disabled={busy !== null || !tg.enabled}
                        onChange={(e) => setTimeframe(tf, e.target.checked)}
                        className="h-4 w-4 accent-[#ff7a1a]"
                      />
                      {TF_LABEL[tf]}
                    </label>
                  ))}
                </fieldset>

                <div className="flex flex-wrap gap-2 border-t border-edge pt-3">
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void act("test", () => call("POST", "/api/telegram/test"), "Pesan uji terkirim. Cek Telegram Anda.")}
                    className="h-9 rounded-md border border-edge bg-surface px-3 text-[12.5px] font-medium text-txt transition hover:border-edgeBright disabled:opacity-60"
                  >
                    {busy === "test" ? "Mengirim…" : "Kirim pesan uji"}
                  </button>
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void act("unlink", () => call("DELETE", "/api/telegram"), "Tautan Telegram diputus.")}
                    className="h-9 rounded-md px-3 text-[12.5px] text-txtMuted transition hover:text-bearish disabled:opacity-60"
                  >
                    Putuskan Telegram
                  </button>
                </div>
              </>
            )}
          </section>

          <aside className="panel space-y-3">
            <div className="panel-title">Contoh pesan</div>
            <div className="rounded-lg rounded-tl-sm border border-edge bg-surface px-3.5 py-3 font-sans text-[12.5px] leading-relaxed text-txtDim">
              <div className="font-semibold text-txt">BTC/USDT 1H — regime berganti</div>
              <div>
                Acak / Tanpa Pola → <b className="text-txt">Tren Berlanjut</b>
              </div>
              <div className="mt-2">Harga: 83.158,99 USDT</div>
              <div>Terkonfirmasi 3 window berturut-turut</div>
              <div>Hurst 0,60 · DFA 0,57</div>
              <div className="mt-2">
                Strategi yang cocok: <b className="text-txt">Trend-following</b> <i>(rancangan, belum teruji di BTC)</i>
              </div>
              <div className="mt-2 text-txtMuted">Bukan saran investasi.</div>
            </div>
            <ul className="list-disc space-y-1 pl-4 text-[11.5px] leading-relaxed text-txtMuted">
              <li>Dikirim hanya saat regime berganti dan sudah stabil 3 window berturut-turut.</li>
              <li>Kondisi &ldquo;Belum Jelas&rdquo; tidak memicu notifikasi.</li>
              <li>Ketik /status di Telegram untuk kondisi terbaru, /stop untuk berhenti.</li>
            </ul>
          </aside>
        </div>
      )}
    </div>
  );
}
