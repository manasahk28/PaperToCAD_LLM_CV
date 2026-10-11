import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
from pathlib import Path
from src.pipeline.cad_schematic_renderer import CADSchematicRenderer, generate_cad_schematic_files

def run():
    with open("outputs/run1/final_result/json/cir1.final.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    comps = data["components"]
    texts = data.get("texts", [])
    text_map = {t["matched_component_id"]: t["text"] for t in texts if "matched_component_id" in t}
    for c in comps:
        if c["id"] in text_map:
            c["text_label"] = text_map[c["id"]]

    out_dir = Path("outputs/test_improved")
    paths = generate_cad_schematic_files("cir1", data["width"], data["height"], comps, out_dir)
    print("Generated files:", paths)

if __name__ == "__main__":
    run()
