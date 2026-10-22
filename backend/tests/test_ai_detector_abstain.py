import pandas as pd

from app.services import ai_detector


def test_with_abstain_marks_only_low_confidence_windows():
    df = pd.DataFrame({"regime": ["persistent", "random_like", "anti_persistent"], "confidence": [0.9, 0.6, 0.75]})
    out = ai_detector.with_abstain(df, tau=0.75)
    assert out["regime"].tolist() == ["persistent", "uncertain_lowconf", "anti_persistent"]
    assert df["regime"].tolist()[1] == "random_like"  # deret asli tidak diubah
