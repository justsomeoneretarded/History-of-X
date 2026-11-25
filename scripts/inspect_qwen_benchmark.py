"""Read the saved CPU experiment; no model download, inference or credentials."""
import json
from pathlib import Path

root = Path("work/director")
out = Path("output/inspection")
out.mkdir(parents=True, exist_ok=True)
report = {}
for name in ("failure.json", "metrics.json", "model-details.json", "render-metrics.json"):
    path = root / name
    if path.exists():
        report[name] = json.loads(path.read_text())
for path in sorted(root.glob("draft-*.txt")):
    text = path.read_text()
    report[path.name] = {"characters": len(text), "text": text[:18000]}
for path in sorted(root.glob("draft-*-validation.json")):
    report[path.name] = json.loads(path.read_text())
if not report:
    raise ValueError("The selected artifact contains no CPU benchmark evidence")
(out / "qwen-benchmark-evidence.json").write_text(json.dumps(report, indent=2))
print("QWEN_SAVED_EVIDENCE " + json.dumps(report), flush=True)
