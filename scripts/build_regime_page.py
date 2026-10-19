"""Bangun docs/presentasi/peta_regime_strategi.html dari template + hasil simulasi.

    python ml/src/regime_strategy_demo.py
    python scripts/build_regime_page.py docs/presentasi/peta_regime_strategi.template.html ml/artifacts/regime_strategy_demo.json docs/presentasi/peta_regime_strategi.html
"""

import json
import sys

HEAD = (
    '<!doctype html>\n<html lang="id">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    "</head>\n<body>\n"
)
TAIL = "\n</body>\n</html>\n"

tpl_path, data_path, out_path = sys.argv[1:4]
s = open(tpl_path, encoding="utf-8").read()
old = """  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);"""
new = """  for (const [k, v] of Object.entries(attrs)) {
    // var() hanya andal lewat CSS, tidak lewat atribut presentasi SVG.
    if (typeof v === "string" && v.includes("var(")) e.style.setProperty(k, v);
    else e.setAttribute(k, v);
  }"""
assert s.count(old) == 1
s = s.replace(old, new)
data = json.load(open(data_path, encoding="utf-8"))
assert s.count("__DATA__") == 1
s = s.replace("__DATA__", json.dumps(data, separators=(",", ":")))
# Dokumen mandiri agar bisa dibuka langsung di browser tanpa server.
s = HEAD + s + TAIL
open(out_path, "w", encoding="utf-8", newline="").write(s)
print(out_path, len(s))
