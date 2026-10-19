"""Walk-Forward Setup Engine.

Simulasi setup entry historis di atas output regime model existing
(SWT + Attention-BiLSTM, label Hurst-DFA). Tidak ada model baru, tidak ada
eksekusi order nyata — seluruh keluaran adalah SIMULATED ENTRY.

Tahap 1: config, data contract, loader, alignment multi-timeframe.
"""

from app.services.setup_engine.config import SetupEngineConfig, load_setup_config
from app.services.setup_engine.setup_engine import generate_setups, SetupRejectionReason

__all__ = ["SetupEngineConfig", "load_setup_config", "generate_setups", "SetupRejectionReason"]
