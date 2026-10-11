import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import json
from pathlib import Path
import schemdraw
import schemdraw.elements as elm

def test_full_pipeline_cir1():
    with open("outputs/run1/final_result/json/cir1.final.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    comps = data["components"]
    texts = data.get("texts", [])
    text_map = {t["matched_component_id"]: t["text"] for t in texts if "matched_component_id" in t}
    for c in comps:
        if c["id"] in text_map:
            c["text_label"] = text_map[c["id"]]

    # Test clustering
    active_comps = [c for c in comps if "text" not in c["cls_name"] and "gnd" not in c["cls_name"]]
    for c in active_comps:
        b = c["bbox"]
        c["cx"] = (b[0] + b[2]) / 2.0
        c["cy"] = (b[1] + b[3]) / 2.0

    active_comps.sort(key=lambda c: c["cy"])
    
    rows = []
    for c in active_comps:
        placed = False
        for r in rows:
            mean_y = sum(x["cy"] for x in r) / len(r)
            if abs(c["cy"] - mean_y) < 70:
                r.append(c)
                placed = True
                break
        if not placed:
            rows.append([c])

    for r in rows:
        r.sort(key=lambda c: c["cx"])

    print(f"Detected {len(rows)} parallel branches:")
    for i, r in enumerate(rows):
        print(f" Branch {i+1}:", [(c.get("cls_name_refined", c["cls_name"]), c.get("text_label")) for c in r])

if __name__ == "__main__":
    test_full_pipeline_cir1()
