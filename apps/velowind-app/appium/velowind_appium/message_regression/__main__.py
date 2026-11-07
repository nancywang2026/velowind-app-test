import argparse
import json
from pathlib import Path
from .journeys import CASES
from .config import audit_bindings

parser = argparse.ArgumentParser(description="Audit October message coverage without connecting a device")
parser.add_argument("--bindings", help="Execution JSON; omitted audits missing bindings")
parser.add_argument("--output", help="Sanitized audit output JSON")
args = parser.parse_args()
data = json.loads(Path(args.bindings).read_text()) if args.bindings else {}
rows = audit_bindings(data, CASES)
result = {"case_groups": len(CASES), "variants": sum(len(x.variants) for x in CASES),
          "rows": rows, "device_execution": "not run"}
if args.output:
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({"case_groups":result["case_groups"], "variants":result["variants"],
                  "blocked": sum(x["status"] == "blocked" for x in rows), "device_execution":"not run"}, ensure_ascii=False))
