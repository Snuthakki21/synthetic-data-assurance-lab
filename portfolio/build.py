"""Create a static site, executed example reports and a browser Python bundle."""
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import zipfile
from .registry import ROOT, execute, projects

REPOS = {
    "ledger_reconciliation": "ledger-reconciliation-workbench",
    "liquidity_stress_lab": "liquidity-stress-lab",
    "fraud_investigation_workbench": "fraud-investigation-workbench",
    "synthetic_data_foundry": "synthetic-data-assurance-lab",
    "lineage_change_impact": "lineage-change-advisor",
    "legacy_modernization_workbench": "legacy-modernization-workbench",
    "incident_command": "incident-command-workbench",
    "document_evidence_room": "document-evidence-room",
    "data_contract_observatory": "data-contract-observatory",
    "ai_release_gate": "ai-evaluation-release-gate",
    "governed_analytics": "governed-analytics-workbench",
    "inference_cost_lab": "ai-inference-cost-lab",
    "ai_investment_planner": "ai-investment-planner",
}


def build(destination=None):
    destination = Path(destination or ROOT / "dist")
    destination.mkdir(parents=True, exist_ok=True)
    for file in (ROOT / "web").iterdir():
        if file.is_file():
            shutil.copy2(file, destination / file.name)
        elif file.is_dir():
            shutil.copytree(file, destination / file.name, dirs_exist_ok=True)
    catalog = []
    for pid, module in projects().items():
        metadata = copy.deepcopy(module.META)
        metadata["repo_url"] = "https://github.com/Snuthakki21/" + REPOS[pid]
        metadata["demo_url"] = "https://Snuthakki21.github.io/" + REPOS[pid] + "/"
        examples = metadata.pop("demo_inputs", []) or [{"label": "Sample scenario", "payload": module.default_input()}]
        metadata["examples"] = []
        for example in examples:
            payload = example.get("payload", module.default_input())
            metadata["examples"].append({"label": example["label"], "payload": payload, "report": execute(pid, payload)})
        catalog.append(metadata)
    data = {"version": "2.0.0", "built_at": datetime.now(timezone.utc).isoformat(), "projects": catalog}
    (destination / "catalog.json").write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    (destination / ".nojekyll").touch()
    # The same reviewed source and fixtures execute in the browser, inside a worker.
    with zipfile.ZipFile(destination / "application.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in ("portfolio", "projects", "app"):
            for path in sorted((ROOT / directory).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
                    archive.write(path, path.relative_to(ROOT))
    return data
