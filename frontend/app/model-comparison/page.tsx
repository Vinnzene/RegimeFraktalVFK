import RetiredPage from "@/components/RetiredPage";

export default function ModelComparisonPage() {
  return (
    <RetiredPage
      title="Perbandingan Model (dinonaktifkan)"
      reason="Panel ini membandingkan model SWT lama yang dilatih untuk menebak regime 500 bar ke depan (h = 500), bukan model identifikasi yang dipakai sistem."
    />
  );
}
