import RetiredPage from "@/components/RetiredPage";

export default function AttentionPage() {
  return (
    <RetiredPage
      title="Fokus Model (dinonaktifkan)"
      reason="Bobot attention di halaman ini berasal dari model SWT + Attention-BiLSTM lama (target h = 500 bar), bukan dari model identifikasi yang dipakai sistem."
    />
  );
}
