import json

with open('ml/artifacts/walk_forward_neural_4h_ps.json') as f:
    d = json.load(f)
mdata = d['models']['hybrid_ps']
print("mdata keys:", list(mdata.keys()))
print("mdata['folds'][0] keys:", list(mdata['folds'][0].keys()))
print("mdata['folds'][0]:", mdata['folds'][0])
print("comparison:", json.dumps(d['comparison'], indent=2))
