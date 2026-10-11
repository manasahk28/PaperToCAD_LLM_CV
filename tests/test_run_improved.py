import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from src.pipeline.cad_schematic_renderer import CADSchematicRenderer, generate_cad_schematic_files

def run():
    cir1_json = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / "cir1.final.json"
    if not cir1_json.exists():
        print("cir1.final.json not found")
        return
    with open(cir1_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    comps = data["components"]
    texts = data.get("texts", [])
    text_map = {t["matched_component_id"]: t["text"] for t in texts if "matched_component_id" in t}
    for c in comps:
        if c["id"] in text_map:
            c["text_label"] = text_map[c["id"]]

    out_dir = REPO_ROOT / "outputs" / "test_previews"
    paths = generate_cad_schematic_files("cir1", data["width"], data["height"], comps, out_dir)
    print("Generated files:", paths)

if __name__ == "__main__":
    run()
