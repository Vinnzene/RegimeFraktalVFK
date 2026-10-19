"use client";

/** Tampilan seragam untuk state loading dan error pada setiap panel. */
export default function ApiState({
  loading,
  error,
}: {
  loading: boolean;
  error: string | null;
}) {
  if (error) {
    return (
      <div className="rounded border border-bearish/40 bg-bearish/10 px-3 py-2 text-[11px] text-bearish">
        {error}
      </div>
    );
  }
  if (loading) {
    return <div className="h-40 animate-pulse rounded border border-edge bg-surface/40" />;
  }
  return null;
}
