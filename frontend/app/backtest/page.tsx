import RetiredPage from "@/components/RetiredPage";

export default function BacktestPage() {
  return (
    <RetiredPage
      title="Uji Strategi lama (dinonaktifkan)"
      reason="Backtest eksploratif ini memakai keluaran model SWT lama (target h = 500 bar). Uji strategi yang berlaku ada di halaman Regime → Strategi."
    />
  );
}
