#!/usr/bin/env bash
# Jalankan ulang seluruh eksperimen Bab 4 dengan analysis.threshold_source =
# train_only (konfigurasi utama sejak 2026-10-19) plus baseline tabular.
#
#   bash scripts/rerun_train_only.sh            # 1H dan 4H
#   bash scripts/rerun_train_only.sh 4h         # satu timeframe
#
# Log per langkah: ml/artifacts/logs/<langkah>.log. Langkah yang gagal dicatat
# dan langkah berikutnya tetap dijalankan.

set -u
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8 TF_CPP_MIN_LOG_LEVEL=2
LOGDIR=ml/artifacts/logs
mkdir -p "$LOGDIR"
TFS=("${@:-4h 1h}")
read -r -a TFS <<< "${TFS[*]}"
FAILED=()

step() {
  local name=$1; shift
  local t0=$SECONDS
  echo "[$(date +%H:%M:%S)] mulai  $name"
  if python "$@" > "$LOGDIR/$name.log" 2>&1; then
    echo "[$(date +%H:%M:%S)] selesai $name ($((SECONDS - t0))s)"
  else
    echo "[$(date +%H:%M:%S)] GAGAL  $name — lihat $LOGDIR/$name.log"
    FAILED+=("$name")
  fi
}

PS_VARIANTS="clean shuffle_split no_purge global_scaler no_multifractal no_vr no_vr_ac no_persistence_proxies no_persistence_proxies_all"
WF_PS_MODELS="structural_mlp logreg lightgbm hybrid_swt hybrid_ps ps_attention_bilstm"

for tf in "${TFS[@]}"; do
  step "main_eval_$tf"        ml/src/main_evaluation.py --timeframe "$tf"
  step "ps_study_$tf"         ml/src/persistence_sequence_study.py --timeframe "$tf"
  step "leakage_$tf"          ml/src/leakage_study.py --timeframe "$tf"
  # shellcheck disable=SC2086
  step "leakage_${tf}_ps"     ml/src/leakage_study.py --timeframe "$tf" --models hybrid_ps --tag _ps --variants $PS_VARIANTS
  step "walk_forward_$tf"     ml/src/walk_forward_neural.py --timeframe "$tf"
  # shellcheck disable=SC2086
  step "walk_forward_${tf}_ps" ml/src/walk_forward_neural.py --timeframe "$tf" --models $WF_PS_MODELS --tag _ps
  step "bootstrap_$tf"        ml/src/block_bootstrap_eval.py --timeframe "$tf"
  step "forward_persistence_$tf" ml/src/forward_persistence_analysis.py --timeframe "$tf"
  step "threshold_sensitivity_$tf" ml/src/run_threshold_sensitivity.py --timeframe "$tf"
done
step "make_figures" ml/src/make_figures.py

if [ ${#FAILED[@]} -eq 0 ]; then
  echo "SEMUA LANGKAH SELESAI"
else
  echo "GAGAL: ${FAILED[*]}"
  exit 1
fi
