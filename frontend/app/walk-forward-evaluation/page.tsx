"use client";

import { useState, useEffect } from "react";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import Papa from "papaparse";

export default function WalkForwardEvaluationPage() {
  const [mode, setMode] = useState("mode_B");
  const [summaryData, setSummaryData] = useState<any>(null);
  const [regimeData, setRegimeData] = useState<any[]>([]);

  useEffect(() => {
    // Load summary CSV
    fetch(`/reports/${mode}/setup_summary.csv`)
      .then((res) => res.text())
      .then((csvText) => {
        const parsed = Papa.parse(csvText, { header: true });
        if (parsed.data && parsed.data.length > 0) {
          setSummaryData(parsed.data[0]);
        }
      });

    // Load regime CSV
    fetch(`/reports/${mode}/regime_conditioned_results.csv`)
      .then((res) => res.text())
      .then((csvText) => {
        const parsed = Papa.parse(csvText, { header: true });
        if (parsed.data) {
          setRegimeData(parsed.data.filter((r: any) => r.regime));
        }
      });
  }, [mode]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Walk-Forward Setup Evaluation"
        description="Laporan akhir simulasi trading engine menggunakan arsitektur Attention-BiLSTM secara out-of-sample tanpa lookahead bias."
      />

      <Panel title="Pengaturan Mode Evaluasi">
        <div className="flex gap-4">
          <label className="text-sm font-medium text-txtDim">Mode Filter:</label>
          <select
            className="rounded border border-edge bg-panelAlt px-3 py-1 text-sm text-txtDim"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="mode_A">Mode A (Tanpa Filter Mikrostruktur)</option>
            <option value="mode_B">Mode B (Strict OFI & CVD Filter)</option>
          </select>
        </div>
      </Panel>

      {summaryData && (
        <Panel title="Metrik Kinerja Keseluruhan (Global Metrics)">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className="rounded border border-edge bg-panelAlt p-4">
              <div className="text-xs text-txtMuted">Total Setup</div>
              <div className="mt-1 text-2xl font-mono text-txt">{summaryData.total_setup}</div>
            </div>
            <div className="rounded border border-edge bg-panelAlt p-4">
              <div className="text-xs text-txtMuted">Win Rate</div>
              <div className="mt-1 text-2xl font-mono text-txt">
                {(Number(summaryData.win_rate) * 100).toFixed(1)}%
              </div>
            </div>
            <div className="rounded border border-edge bg-panelAlt p-4">
              <div className="text-xs text-txtMuted">Total R (Risk Multiple)</div>
              <div className="mt-1 text-2xl font-mono text-txt">
                {Number(summaryData.total_r).toFixed(2)} R
              </div>
            </div>
            <div className="rounded border border-edge bg-panelAlt p-4">
              <div className="text-xs text-txtMuted">Max Drawdown</div>
              <div className="mt-1 text-2xl font-mono text-txt">
                {Number(summaryData.max_drawdown).toFixed(2)} R
              </div>
            </div>
          </div>
          <div className="mt-4 flex gap-6 text-sm text-txtMuted">
            <div>
              <span className="font-semibold">Profit Factor:</span>{" "}
              {Number(summaryData.profit_factor).toFixed(2)}
            </div>
            <div>
              <span className="font-semibold">Average R:</span>{" "}
              {Number(summaryData.average_r).toFixed(2)}
            </div>
          </div>
        </Panel>
      )}

      {regimeData.length > 0 && (
        <Panel title="Analisis Berbasis Rezim (Regime-Conditioned Results)">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-txtDim">
              <thead className="bg-panelAlt text-xs uppercase text-txtMuted border-b border-edge">
                <tr>
                  <th className="px-4 py-3">Regime</th>
                  <th className="px-4 py-3">Setup</th>
                  <th className="px-4 py-3">TP</th>
                  <th className="px-4 py-3">SL</th>
                  <th className="px-4 py-3">Avg R</th>
                  <th className="px-4 py-3">Total R</th>
                </tr>
              </thead>
              <tbody>
                {regimeData.map((row, idx) => (
                  <tr key={idx} className="border-b border-edge/50">
                    <td className="px-4 py-3 font-medium text-txt">{row.regime}</td>
                    <td className="px-4 py-3">{row.setup_count}</td>
                    <td className="px-4 py-3">{row.tp}</td>
                    <td className="px-4 py-3">{row.sl}</td>
                    <td className="px-4 py-3">{Number(row.avg_r).toFixed(2)}</td>
                    <td className="px-4 py-3 font-mono">{Number(row.total_r).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <Panel title="Visualisasi Eksekusi - Cumulative R">
        <div className="w-full h-[600px] border border-edge rounded overflow-hidden">
          <iframe
            src={`/reports/${mode}/walk_forward_cumulative_r.html`}
            className="w-full h-full border-none"
            title="Cumulative R"
          />
        </div>
      </Panel>

      <Panel title="Visualisasi Eksekusi - Distribusi Rezim">
        <div className="w-full h-[600px] border border-edge rounded overflow-hidden">
          <iframe
            src={`/reports/${mode}/regime_setup_distribution.html`}
            className="w-full h-full border-none"
            title="Regime Setup Distribution"
          />
        </div>
      </Panel>

    </div>
  );
}
