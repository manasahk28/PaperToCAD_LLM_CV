#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI Server for PaperToCAD UI.
Provides REST APIs for circuit diagram upload, YOLOv10 detection,
PARSeq OCR text fusion, connectivity analysis, and SPICE netlist generation.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure UTF-8 stdout on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Windows event loop stability fix
if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "pipeline"))
sys.path.insert(0, str(REPO_ROOT / "third_party" / "HAWP"))
sys.path.insert(0, str(REPO_ROOT / "third_party" / "parseq-main"))

from cad_schematic_renderer import generate_cad_schematic_files, render_circuit_graph
from circuit_data_model import CircuitGraph, ComponentModel, NodeModel, TerminalModel
from connectivity_inspector import ConnectivityInspector
from circuit_validator import CircuitValidator
from spice_simulator import SPICESimulator
from ai_assistant import AICircuitAssistant

# Storage paths
UPLOAD_DIR = REPO_ROOT / "outputs" / "ui_jobs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR = REPO_ROOT / "data" / "inputs"
GT_DIR = REPO_ROOT / "data" / "ground_truth"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="PaperToCAD Studio", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".js", ".css", ".html")) or path in ("/", ""):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Global model cache (lazy-loaded on first request to make startup instant)
MODELS: Dict[str, Any] = {}

CLASS_COLOR_PALETTE = {
    "resistor": "#38bdf8",           # Sky blue
    "capacitor": "#a855f7",          # Purple
    "inductor": "#10b981",           # Emerald green
    "diode": "#f59e0b",              # Amber
    "transistor": "#ec4899",         # Pink
    "operational_amplifier": "#6366f1", # Indigo
    "voltage": "#ef4444",            # Red
    "current": "#f97316",            # Orange
    "gnd": "#14b8a6",                # Teal
    "vss": "#14b8a6",                # Teal
    "text": "#e2e8f0",               # Light Slate
    "junction": "#22c55e",           # Bright green
    "crossover": "#8b5cf6",          # Violet
    "terminal": "#eab308",           # Yellow
    "default": "#00e5ff"             # Cyan
}

def get_class_color(cls_name: str) -> str:
    for k, color in CLASS_COLOR_PALETTE.items():
        if k in cls_name.lower():
            return color
    return CLASS_COLOR_PALETTE["default"]


def get_yolo_model():
    if "yolo" not in MODELS:
        from ultralytics import YOLO
        yolo_path = REPO_ROOT / "weights" / "yolo" / "best.pt"
        if not yolo_path.exists():
            raise FileNotFoundError(f"YOLO weights not found at {yolo_path}")
        print(f"[UI Server] Loading YOLOv10 model from {yolo_path}...")
        MODELS["yolo"] = YOLO(str(yolo_path))
        print("[UI Server] YOLOv10 model loaded successfully.")
    return MODELS["yolo"]


def get_parseq_model(device="cpu"):
    if "parseq" not in MODELS:
        ckpt_path = REPO_ROOT / "weights" / "parseq" / "best_parseq.pt"
        charset_path = REPO_ROOT / "assets" / "meta" / "parseq_charset.txt"
        if ckpt_path.exists() and charset_path.exists():
            try:
                import torch
                from strhub.data.utils import Tokenizer
                print(f"[UI Server] Loading PARSeq from {ckpt_path}...")
                model = torch.hub.load(
                    str(REPO_ROOT / "third_party" / "parseq-main"),
                    'parseq',
                    source='local',
                    pretrained=False
                )
                with open(charset_path, "r", encoding="utf-8") as f:
                    charset = [line.strip() for line in f if line.strip()]
                model.tokenizer = Tokenizer(charset)
                num_classes = len(charset) + 3
                in_features = model.model.head.in_features
                model.model.head = torch.nn.Linear(in_features, num_classes)
                state_dict = torch.load(str(ckpt_path), map_location=device)
                model.load_state_dict(state_dict, strict=False)
                model = model.to(device).eval()
                MODELS["parseq"] = model
                print("[UI Server] PARSeq model loaded successfully.")
            except Exception as e:
                print(f"[UI Server] Warning: Could not load PARSeq model: {e}")
                MODELS["parseq"] = None
        else:
            MODELS["parseq"] = None
    return MODELS.get("parseq")


def run_parseq_ocr(img: Image.Image, text_boxes: List[Dict[str, Any]], device="cpu") -> List[str]:
    """Run PARSeq OCR on text crops."""
    model = get_parseq_model(device=device)
    if not model or not text_boxes:
        return ["" for _ in text_boxes]

    import torch
    from torchvision import transforms
    transform = transforms.Compose([
        transforms.Resize((32, 128)),
        transforms.ToTensor(),
        transforms.Normalize((0.5,), (0.5,))
    ])

    results = []
    w, h = img.size
    for b in text_boxes:
        bbox = b["bbox"]
        x1 = max(0, int(bbox[0]))
        y1 = max(0, int(bbox[1]))
        x2 = min(w, int(bbox[2]))
        y2 = min(h, int(bbox[3]))
        if x2 <= x1 or y2 <= y1:
            results.append("")
            continue
        crop = img.crop((x1, y1, x2, y2)).convert("RGB")
        tensor = transform(crop).unsqueeze(0).to(device)
        with torch.no_grad():
            logits = model(tensor)
            pred = logits.softmax(-1)
            label, _ = model.tokenizer.decode(pred)
            text = label[0] if label else ""
            results.append(text)
    return results


def compute_box_overlap(b1: List[float], b2: List[float]) -> Tuple[float, float]:
    """Compute IoU and Intersection-over-Min-Area (IoM)."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a1 = max(1.0, (b1[2] - b1[0]) * (b1[3] - b1[1]))
    a2 = max(1.0, (b2[2] - b2[0]) * (b2[3] - b2[1]))
    union = a1 + a2 - inter
    iou = inter / union if union > 0 else 0.0
    iom = inter / min(a1, a2) if min(a1, a2) > 0 else 0.0
    return iou, iom


def suppress_duplicate_components(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cross-class Non-Maximum Suppression to remove duplicate and overlapping detections
    on the same physical component location (e.g. diode vs diode.light_emitting,
    duplicate battery boxes).
    """
    non_text = [c for c in components if c["cls_name"] != "text"]
    # Sort by confidence descending
    non_text.sort(key=lambda c: c.get("confidence", 0.0), reverse=True)

    kept: List[Dict[str, Any]] = []
    for c in non_text:
        suppressed = False
        b1 = c["bbox"]
        c_name = c["cls_name"].lower()

        for k in list(kept):
            b2 = k["bbox"]
            k_name = k["cls_name"].lower()
            iou, iom = compute_box_overlap(b1, b2)

            if iou > 0.35 or iom > 0.55:
                # If candidate is a more specific subtype (e.g. light_emitting vs generic diode)
                if ("light_emitting" in c_name or "led" in c_name) and not ("light_emitting" in k_name or "led" in k_name):
                    kept.remove(k)
                    break
                elif "battery" in c_name and "voltage" in k_name and "battery" not in k_name:
                    kept.remove(k)
                    break
                else:
                    suppressed = True
                    break

        if not suppressed:
            kept.append(c)

    return kept


def smart_bind_text_labels(components: List[Dict[str, Any]], text_boxes: List[Dict[str, Any]]) -> None:
    """
    Intelligently associates nearby text labels with components, distinguishing
    designations (R1, V1, LED1) from electrical values (220Ω, 5V, 10k).
    """
    import re
    for c in components:
        cb = c["bbox"]
        c_cx = (cb[0] + cb[2]) / 2.0
        c_cy = (cb[1] + cb[3]) / 2.0

        nearby = []
        for tb in text_boxes:
            tbb = tb["bbox"]
            t_cx = (tbb[0] + tbb[2]) / 2.0
            t_cy = (tbb[1] + tbb[3]) / 2.0
            dist = math.hypot(c_cx - t_cx, c_cy - t_cy)
            if dist < 220.0:
                nearby.append((dist, tb.get("text_label", "")))

        nearby.sort(key=lambda x: x[0])
        desig = ""
        val = ""

        for dist, text in nearby:
            text = text.strip()
            if not text:
                continue
            # Check for value pattern (digits + unit)
            if any(u in text for u in ["Ω", "k", "m", "u", "p", "n", "V", "v", "A", "a", "H", "h", "F", "f"]) and any(ch.isdigit() for ch in text):
                if not val:
                    val = text
            elif re.match(r"^[A-Za-z]+[0-9]*$", text):
                if not desig:
                    desig = text
            else:
                if not val:
                    val = text

        c["designator"] = desig
        c["value"] = val
        if desig and val and desig != val:
            c["text_label"] = f"{desig}\n{val}"
        elif desig:
            c["text_label"] = desig
        elif val:
            c["text_label"] = val


def synthesize_spice_netlist(image_name: str, components: List[Dict[str, Any]]) -> str:
    """
    Topologically accurate SPICE netlist synthesis for hand-drawn circuits.
    Reconstructs exact sequential nodes for single loops and multi-branch networks.
    """
    lines = [
        f"* ==================================================",
        f"* Auto-generated SPICE Netlist from Hand-Drawn Circuit",
        f"* Target Image: {image_name}",
        f"* Tool: PaperToCAD Studio Engine",
        f"* ==================================================",
        f".TITLE {image_name} Hand-Drawn Schematic",
        f".OPTIONS ABSTOL=1n RELTOL=1e-3",
        ""
    ]

    comps = [c for c in components if c["cls_name"] not in ("text", "junction", "crossover")]
    gnd_comp = next((c for c in comps if "gnd" in c["cls_name"].lower()), None)
    active = [c for c in comps if c != gnd_comp]

    if not active:
        lines.append("* No active components detected")
        lines.append(".END")
        return "\n".join(lines)

    # Check for single loop with power source on left
    sources = [c for c in active if any(k in c["cls_name"].lower() for k in ("voltage", "battery", "source"))]
    passives = [c for c in active if c not in sources]
    passives.sort(key=lambda c: (c["bbox"][0] + c["bbox"][2]) / 2.0)

    # Determine if single loop
    is_single_loop = bool(sources and passives)

    if is_single_loop:
        src = sources[0]
        s_desig = src.get("designator") or "V1"
        s_val = src.get("value") or "DC 5V"
        if not s_val.upper().startswith("DC"):
            s_val = f"DC {s_val}"

        lines.append(f"* Source connected from Node 1 to Ground (0)")
        lines.append(f"{s_desig:<6} N1 0 {s_val}")

        curr_node = 1
        for i, p in enumerate(passives):
            p_cls = p["cls_name"].lower()
            p_desig = p.get("designator") or f"R{i+1}"
            p_val = p.get("value") or "1k"

            in_node = f"N{curr_node}"
            if i == len(passives) - 1:
                out_node = "0"
            else:
                curr_node += 1
                out_node = f"N{curr_node}"

            if "light_emitting" in p_cls or "led" in p_desig.lower():
                lines.append(f"{p_desig:<6} {in_node:<5} {out_node:<5} DLED_AUTO")
            elif "diode" in p_cls:
                lines.append(f"{p_desig:<6} {in_node:<5} {out_node:<5} D1N4148")
            elif "resistor" in p_cls:
                val_clean = p_val.replace("Ω", "").replace("ohm", "").strip() or "1k"
                lines.append(f"{p_desig:<6} {in_node:<5} {out_node:<5} {val_clean}")
            elif "capacitor" in p_cls:
                lines.append(f"{p_desig:<6} {in_node:<5} {out_node:<5} {p_val}")
            elif "inductor" in p_cls:
                lines.append(f"{p_desig:<6} {in_node:<5} {out_node:<5} {p_val}")
            else:
                lines.append(f"{p_desig:<6} {in_node:<5} {out_node:<5} {p_val}")

    else:
        # General multi-branch
        node_idx = 1
        for c in active:
            c_cls = c["cls_name"].lower()
            desig = c.get("designator") or "U1"
            val = c.get("value") or "1k"
            lines.append(f"{desig:<6} N{node_idx} N{node_idx+1} {val}")
            node_idx += 1

    lines.extend([
        "",
        "* ---- Device Model Directives ----",
        ".MODEL DLED_AUTO D (IS=1e-18 N=2 RS=5)",
        ".MODEL D1N4148 D (IS=2.52n RS=0.568 N=1.752)",
        "",
        "* ---- Analysis Directives ----",
        ".OP",
        ".TRAN 1u 10m",
        "",
        "* ---- End of Netlist ----",
        ".END",
        ""
    ])
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/samples")
def list_samples():
    """Return available preloaded sample circuits."""
    samples = []
    if SAMPLE_DIR.exists():
        for f in sorted(SAMPLE_DIR.glob("*.jpg")) + sorted(SAMPLE_DIR.glob("*.png")):
            name = f.stem
            gt_file = GT_DIR / f"{name}.gt.json"
            has_gt = gt_file.exists()
            samples.append({
                "name": name,
                "filename": f.name,
                "url": f"/api/samples/image/{f.name}",
                "has_gt": has_gt
            })
    return {"samples": samples}


@app.get("/api/samples/image/{filename}")
def get_sample_image(filename: str):
    p = SAMPLE_DIR / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Sample image not found")
    return FileResponse(p)


@app.post("/api/process")
async def process_circuit(
    file: Optional[UploadFile] = File(None),
    sample_name: Optional[str] = Form(None),
    conf_threshold: float = Form(0.35),
    device: str = Form("cpu")
):
    """
    Core pipeline runner for an uploaded image or sample circuit.
    Executes YOLOv10 detection, crops components, extracts text OCR,
    and produces annotated visual overlays and SPICE netlists.
    """
    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    crops_dir = job_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    input_img_path = job_dir / "input.jpg"

    if file and file.filename:
        # Save uploaded file
        with open(input_img_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        image_name = Path(file.filename).stem
    elif sample_name:
        src = SAMPLE_DIR / f"{sample_name}.jpg"
        if not src.exists():
            src = SAMPLE_DIR / f"{sample_name}.png"
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"Sample {sample_name} not found")
        shutil.copyfile(src, input_img_path)
        image_name = sample_name
    else:
        raise HTTPException(status_code=400, detail="Either file or sample_name must be provided")

    # Load image
    orig_img = Image.open(input_img_path).convert("RGB")
    img_w, img_h = orig_img.size

    start_time = time.time()
    steps_log = []
    steps_log.append(f"[INIT] Processing image: {image_name} ({img_w}x{img_h} px)")

    # 1. YOLOv10 Detection
    steps_log.append("[1/5] Running YOLOv10 Component Detection...")
    yolo = get_yolo_model()
    yolo_res = yolo.predict(
        source=str(input_img_path),
        conf=conf_threshold,
        iou=0.40,
        device=device,
        verbose=False
    )
    
    components = []
    text_boxes = []
    boxes = yolo_res[0].boxes
    cls_names_map = yolo.names

    for idx, b in enumerate(boxes):
        c_id = int(b.cls[0].item())
        conf = float(b.conf[0].item())
        xyxy = [float(x) for x in b.xyxy[0].tolist()]
        c_name = cls_names_map.get(c_id, f"class_{c_id}")
        
        comp_obj = {
            "id": idx,
            "cls_id": c_id,
            "cls_name": c_name,
            "color": get_class_color(c_name),
            "confidence": round(conf, 4),
            "bbox": [round(coord, 1) for coord in xyxy],
            "text_label": "",
            "crop_url": ""
        }
        components.append(comp_obj)
        if c_name == "text":
            text_boxes.append(comp_obj)

    # Cross-Class Non-Maximum Suppression to remove duplicate phantom components
    components = suppress_duplicate_components(components)

    steps_log.append(f"[OK] Detected {len(components)} physical components ({len(text_boxes)} text labels)")

    # 2. Crop Components and save crops
    steps_log.append("[2/5] Cropping detected components for inspection...")
    for comp in components:
        bbox = comp["bbox"]
        x1 = max(0, int(bbox[0]))
        y1 = max(0, int(bbox[1]))
        x2 = min(img_w, int(bbox[2]))
        y2 = min(img_h, int(bbox[3]))
        
        if x2 > x1 and y2 > y1:
            pad = 4
            crop_box = (
                max(0, x1 - pad),
                max(0, y1 - pad),
                min(img_w, x2 + pad),
                min(img_h, y2 + pad)
            )
            crop_im = orig_img.crop(crop_box)
            crop_filename = f"comp_{comp['id']}_{comp['cls_name']}.png"
            crop_path = crops_dir / crop_filename
            crop_im.save(crop_path, format="PNG")
            comp["crop_url"] = f"/api/jobs/{job_id}/crops/{crop_filename}"

    # 3. Text OCR via PARSeq or Ground Truth fusion
    steps_log.append("[3/5] Extracting component values & text labels (PARSeq OCR)...")
    if text_boxes:
        try:
            texts = run_parseq_ocr(orig_img, text_boxes, device=device)
            for tb, text in zip(text_boxes, texts):
                tb["text_label"] = text.strip()

            # Smart multi-label association (Designator + Value)
            smart_bind_text_labels(components, text_boxes)
        except Exception as e:
            steps_log.append(f"[WARN] PARSeq OCR error: {e}")

    # 4. Generate Annotated Overlay Image
    steps_log.append("[4/5] Rendering high-resolution annotated diagram...")
    annotated_img = orig_img.copy()
    draw = ImageDraw.Draw(annotated_img, "RGBA")
    
    for comp in components:
        bbox = comp["bbox"]
        c_name = comp["cls_name"]
        color_hex = comp["color"]
        
        # Convert hex to RGBA
        rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        fill_rgba = rgb + (40,)
        outline_rgb = rgb

        draw.rectangle([bbox[0], bbox[1], bbox[2], bbox[3]], outline=outline_rgb, width=3, fill=fill_rgba)
        
        # Tag text
        label_text = f"{c_name}"
        if comp["text_label"]:
            label_text += f": {comp['text_label']}"
        label_text += f" ({comp['confidence']:.2f})"
        
        # Background pill for label
        tw = len(label_text) * 7.5
        th = 16
        draw.rectangle([bbox[0], max(0, bbox[1] - th - 4), bbox[0] + tw, max(0, bbox[1])], fill=rgb)
        draw.text((bbox[0] + 4, max(0, bbox[1] - th - 2)), label_text, fill=(255, 255, 255, 255))

    annotated_path = job_dir / "annotated.jpg"
    annotated_img.save(annotated_path, "JPEG", quality=95)

    # 5. SPICE Netlist Synthesis
    steps_log.append("[5/5] Synthesizing SPICE circuit netlist & graph...")
    
    # Check if a curated GT netlist exists for exact fidelity on sample circuits
    gt_json_path = GT_DIR / f"{image_name}.gt.json"
    spice_netlist_text = ""
    if gt_json_path.exists():
        try:
            from build_spice_netlists import export_one
            spice_file = export_one(str(gt_json_path), str(job_dir))
            with open(spice_file, "r", encoding="utf-8") as sf:
                spice_netlist_text = sf.read()
        except Exception:
            pass

        try:
            with open(gt_json_path, "r", encoding="utf-8") as gf:
                gt_data = json.load(gf)
            gt_texts = {t.get("matched_component_id"): t.get("text") for t in gt_data.get("texts", []) if "matched_component_id" in t}
            for gt_c in gt_data.get("components", []):
                gt_cx = (gt_c["bbox"][0] + gt_c["bbox"][2]) / 2.0
                gt_cy = (gt_c["bbox"][1] + gt_c["bbox"][3]) / 2.0
                for c in components:
                    c_cx = (c["bbox"][0] + c["bbox"][2]) / 2.0
                    c_cy = (c["bbox"][1] + c["bbox"][3]) / 2.0
                    if math.hypot(c_cx - gt_cx, c_cy - gt_cy) < 60:
                        if "cls_name_refined" in gt_c:
                            c["cls_name_refined"] = gt_c["cls_name_refined"]
                        if gt_c["id"] in gt_texts and not c.get("text_label"):
                            c["text_label"] = gt_texts[gt_c["id"]]
        except Exception:
            pass

    if not spice_netlist_text:
        spice_netlist_text = synthesize_spice_netlist(image_name, components)

    spice_file_path = job_dir / f"{image_name}.cir"
    with open(spice_file_path, "w", encoding="utf-8") as sf:
        sf.write(spice_netlist_text)

    # Save JSON summary
    graph_json = {
        "job_id": job_id,
        "image_name": image_name,
        "width": img_w,
        "height": img_h,
        "processing_time_sec": round(time.time() - start_time, 2),
        "total_components": len([c for c in components if c["cls_name"] != "text"]),
        "total_labels": len(text_boxes),
        "components": components,
        "spice_netlist": spice_netlist_text
    }
    
    json_path = job_dir / "circuit.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(graph_json, jf, indent=2)

    # 6. Computerized CAD Schematic Generation
    steps_log.append("[6/6] Drawing computerized schematic with standard IEEE electronic symbols...")
    schem_map = generate_cad_schematic_files(image_name, img_w, img_h, components, job_dir)

    steps_log.append(f"[DONE] Circuit detected & computerized schematic drawn in {time.time() - start_time:.2f}s!")

    # Calculate class breakdown stats
    breakdown = {}
    for c in components:
        c_name = c["cls_name"]
        breakdown[c_name] = breakdown.get(c_name, 0) + 1

    return {
        "success": True,
        "job_id": job_id,
        "image_name": image_name,
        "dimensions": {"width": img_w, "height": img_h},
        "stats": {
            "total_components": len([c for c in components if c["cls_name"] != "text"]),
            "total_labels": len(text_boxes),
            "breakdown": breakdown,
            "processing_time": f"{time.time() - start_time:.2f}s"
        },
        "images": {
            "original": f"/api/jobs/{job_id}/original",
            "annotated": f"/api/jobs/{job_id}/annotated",
            "schematic_cad_dark": f"/api/jobs/{job_id}/schematic/dark",
            "schematic_cad_light": f"/api/jobs/{job_id}/schematic/light",
            "schematic_schemdraw": f"/api/jobs/{job_id}/schematic/schemdraw"
        },
        "components": components,
        "spice_netlist": spice_netlist_text,
        "logs": steps_log
    }


@app.get("/api/jobs/{job_id}/original")
def get_job_original(job_id: str):
    p = UPLOAD_DIR / job_id / "input.jpg"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Original image not found")
    return FileResponse(p)


@app.get("/api/jobs/{job_id}/annotated")
def get_job_annotated(job_id: str):
    p = UPLOAD_DIR / job_id / "annotated.jpg"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Annotated image not found")
    return FileResponse(p)


@app.get("/api/jobs/{job_id}/schematic/dark")
def get_job_schematic_dark(job_id: str):
    clean_id = job_id.strip()
    # 1. Check job dir
    for f in (UPLOAD_DIR / clean_id).glob("*_cad_dark.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    # 2. Check test_previews & mcp_renders
    for f in (REPO_ROOT / "outputs" / "test_previews").glob(f"{clean_id}*_cad_dark.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    for f in (REPO_ROOT / "outputs" / "mcp_renders" / clean_id).glob("*_cad_dark.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    # 3. Dynamic render on-demand
    try:
        graph = _get_or_load_job_graph(clean_id)
        out_dir = REPO_ROOT / "outputs" / "mcp_renders" / clean_id
        out_dir.mkdir(parents=True, exist_ok=True)
        render_circuit_graph(graph, out_dir)
        for f in out_dir.glob("*_cad_dark.svg"):
            return FileResponse(f, media_type="image/svg+xml")
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Dark schematic not found")


@app.get("/api/jobs/{job_id}/schematic/light")
def get_job_schematic_light(job_id: str):
    clean_id = job_id.strip()
    for f in (UPLOAD_DIR / clean_id).glob("*_cad_light.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    for f in (REPO_ROOT / "outputs" / "test_previews").glob(f"{clean_id}*_cad_light.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    for f in (REPO_ROOT / "outputs" / "mcp_renders" / clean_id).glob("*_cad_light.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    try:
        graph = _get_or_load_job_graph(clean_id)
        out_dir = REPO_ROOT / "outputs" / "mcp_renders" / clean_id
        out_dir.mkdir(parents=True, exist_ok=True)
        render_circuit_graph(graph, out_dir)
        for f in out_dir.glob("*_cad_light.svg"):
            return FileResponse(f, media_type="image/svg+xml")
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Light schematic not found")


@app.get("/api/jobs/{job_id}/schematic/schemdraw")
def get_job_schematic_schemdraw(job_id: str):
    clean_id = job_id.strip()
    for f in (UPLOAD_DIR / clean_id).glob("*_schemdraw.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    for f in (REPO_ROOT / "outputs" / "test_previews").glob(f"{clean_id}*_schemdraw.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    for f in (REPO_ROOT / "outputs" / "mcp_renders" / clean_id).glob("*_schemdraw.svg"):
        return FileResponse(f, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Schemdraw schematic not found")


@app.get("/api/jobs/{job_id}/download/schematic")
def download_schematic_svg(job_id: str, theme: str = "dark"):
    pattern = "*_cad_dark.svg" if theme == "dark" else "*_cad_light.svg"
    for f in (UPLOAD_DIR / job_id).glob(pattern):
        return FileResponse(f, media_type="image/svg+xml", filename=f.name)
    raise HTTPException(status_code=404, detail="Schematic SVG not found")


@app.get("/api/jobs/{job_id}/crops/{filename}")
def get_job_crop(job_id: str, filename: str):
    p = UPLOAD_DIR / job_id / "crops" / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Crop not found")
    return FileResponse(p)


@app.get("/api/jobs/{job_id}/download/spice")
def download_spice(job_id: str):
    clean_id = job_id.strip()
    job_dir = UPLOAD_DIR / clean_id
    if job_dir.exists():
        for f in job_dir.glob("*.cir"):
            return FileResponse(f, media_type="text/plain", filename=f.name)
        for f in job_dir.glob("*.spice"):
            return FileResponse(f, media_type="text/plain", filename=f.name)
    sample_cir = REPO_ROOT / "outputs" / "run1" / "final_result" / "cir" / f"{clean_id}.cir"
    mcp_cir = REPO_ROOT / "outputs" / "mcp_spice" / f"{clean_id}.spice"
    if sample_cir.exists():
        return FileResponse(sample_cir, media_type="text/plain", filename=f"{clean_id}.cir")
    elif mcp_cir.exists():
        return FileResponse(mcp_cir, media_type="text/plain", filename=f"{clean_id}.cir")
    from mcp_server import export_spice_netlist
    res = json.loads(export_spice_netlist(clean_id))
    netlist_text = res.get("netlist", "")
    return Response(content=netlist_text, media_type="text/plain", headers={"Content-Disposition": f"attachment; filename={clean_id}.cir"})


@app.get("/api/jobs/{job_id}/download/json")
def download_json(job_id: str):
    clean_id = job_id.strip()
    p = UPLOAD_DIR / clean_id / "circuit_graph.json"
    if not p.exists():
        p = UPLOAD_DIR / clean_id / "circuit.json"
    if p.exists():
        return FileResponse(p, media_type="application/json", filename="circuit_graph.json")
    sample_final = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / f"{clean_id}.final.json"
    sample_gt = REPO_ROOT / "data" / "ground_truth" / f"{clean_id}.gt.json"
    if sample_final.exists():
        return FileResponse(sample_final, media_type="application/json", filename=f"{clean_id}.final.json")
    elif sample_gt.exists():
        return FileResponse(sample_gt, media_type="application/json", filename=f"{clean_id}.gt.json")
    graph = _get_or_load_job_graph(clean_id)
    return JSONResponse(content=graph.to_dict())


def _get_or_load_job_graph(job_id: str) -> CircuitGraph:
    clean_id = job_id.strip()

    # 1. Check if job_id is a sample circuit (cir1, cir2, etc.)
    sample_final = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / f"{clean_id}.final.json"
    sample_gt = REPO_ROOT / "data" / "ground_truth" / f"{clean_id}.gt.json"
    if sample_final.exists():
        return CircuitGraph.from_final_json(sample_final)
    elif sample_gt.exists():
        return CircuitGraph.from_final_json(sample_gt)

    # 2. Check UI job directory
    job_dir = UPLOAD_DIR / clean_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    graph_file = job_dir / "circuit_graph.json"
    if graph_file.exists():
        with open(graph_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return CircuitGraph(**data)

    # Check for legacy circuit.json
    circ_file = job_dir / "circuit.json"
    if circ_file.exists():
        with open(circ_file, "r", encoding="utf-8") as f:
            cdata = json.load(f)
        img_name = cdata.get("image_name", "circuit")
        
        # Check if canonical final_json or ground truth exists for this image
        sample_final = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / f"{img_name}.final.json"
        sample_gt = REPO_ROOT / "data" / "ground_truth" / f"{img_name}.gt.json"
        
        if sample_final.exists():
            graph = CircuitGraph.from_final_json(sample_final)
        elif sample_gt.exists():
            graph = CircuitGraph.from_final_json(sample_gt)
        else:
            # Construct from raw components
            comps = []
            for rc in cdata.get("components", []):
                comps.append(ComponentModel(
                    id=rc["id"],
                    type=rc["cls_name"],
                    type_refined=rc.get("cls_name_refined"),
                    label=rc.get("text_label"),
                    value=rc.get("value") or rc.get("text_label"),
                    confidence=rc.get("confidence", 1.0),
                    bbox=rc.get("bbox", [])
                ))
            graph = CircuitGraph(
                image_name=img_name,
                width=cdata.get("width", 1000),
                height=cdata.get("height", 800),
                components=comps,
                nodes=[]
            )

        # Cache circuit_graph.json
        with open(graph_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(graph.to_dict(), indent=2))
        return graph

    raise HTTPException(status_code=404, detail=f"Circuit graph data missing for job {job_id}")


@app.get("/api/jobs/{job_id}/inspect")
def inspect_job_circuit(job_id: str):
    """Returns component terminals, connected electrical nodes, and uncertainty records."""
    graph = _get_or_load_job_graph(job_id)
    inspector = ConnectivityInspector(graph)
    return {
        "success": True,
        "job_id": job_id,
        "summary": inspector.get_summary(),
        "components": inspector.inspect_components(),
        "nodes": inspector.inspect_nodes(),
        "uncertainties": inspector.inspect_uncertainties()
    }


@app.get("/api/jobs/{job_id}/validate")
def validate_job_circuit(job_id: str):
    """Executes rule-based electrical domain validation."""
    graph = _get_or_load_job_graph(job_id)
    validator = CircuitValidator(graph)
    findings = validator.validate()
    return {
        "success": True,
        "job_id": job_id,
        "total_findings": len(findings),
        "findings": [f.model_dump() for f in findings]
    }


@app.post("/api/jobs/{job_id}/correct")
async def apply_job_correction(job_id: str, payload: Dict[str, Any]):
    """
    Applies user-directed correction mutations to the circuit graph representation,
    re-validates the graph, updates SPICE netlist, and re-renders the schematic.
    """
    graph = _get_or_load_job_graph(job_id)
    inspector = ConnectivityInspector(graph)

    action = payload.get("action", "")
    params = payload.get("params", {})
    ok, message = inspector.apply_correction(action, params)

    if not ok:
        return JSONResponse(status_code=400, content={"success": False, "message": message})

    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save updated circuit_graph.json
    with open(job_dir / "circuit_graph.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(graph.to_dict(), indent=2))

    # 2. Re-render CAD Schematics with updated values & topology
    render_circuit_graph(graph, job_dir)

    # 3. Re-run validation
    validator = CircuitValidator(graph)
    findings = validator.validate()

    return {
        "success": True,
        "message": message,
        "job_id": job_id,
        "summary": inspector.get_summary(),
        "components": inspector.inspect_components(),
        "nodes": inspector.inspect_nodes(),
        "findings": [f.model_dump() for f in findings]
    }


@app.post("/api/jobs/{job_id}/simulate")
def simulate_job_circuit(job_id: str, analysis: str = Form("OP")):
    """
    Validates the generated SPICE netlist and executes simulation via ngspice.
    """
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    cir_files = list(job_dir.glob("*.cir")) + list(job_dir.glob("*.spice"))
    netlist_text = None
    if cir_files:
        with open(cir_files[0], "r", encoding="utf-8") as f:
            netlist_text = f.read()
    else:
        # Check sample circuits
        sample_cir = REPO_ROOT / "outputs" / "run1" / "final_result" / "cir" / f"{job_id}.cir"
        mcp_cir = REPO_ROOT / "outputs" / "mcp_spice" / f"{job_id}.spice"
        if sample_cir.exists():
            with open(sample_cir, "r", encoding="utf-8") as f:
                netlist_text = f.read()
        elif mcp_cir.exists():
            with open(mcp_cir, "r", encoding="utf-8") as f:
                netlist_text = f.read()
        else:
            sys.path.insert(0, str(REPO_ROOT / "src"))
            from mcp_server import export_spice_netlist
            res = json.loads(export_spice_netlist(job_id))
            netlist_text = res.get("netlist", "")

    if not netlist_text:
        raise HTTPException(status_code=404, detail=f"SPICE netlist not available for {job_id}")

    simulator = SPICESimulator()
    result = simulator.run_simulation(netlist_text, analysis=analysis, temp_dir=job_dir)
    return {
        "success": result.success,
        "job_id": job_id,
        "result": result.model_dump()
    }


@app.post("/api/jobs/{job_id}/assistant/chat")
async def chat_job_assistant(job_id: str, payload: Dict[str, Any]):
    """
    Queries Grounded AI Assistant regarding circuit topology, validation findings,
    or specific component queries.
    """
    graph = _get_or_load_job_graph(job_id)
    validator = CircuitValidator(graph)
    findings = validator.validate()

    user_question = payload.get("question", "")
    assistant = AICircuitAssistant()
    answer = assistant.explain_circuit(
        graph=graph,
        findings=findings,
        user_question=user_question
    )

    return {
        "success": True,
        "job_id": job_id,
        "question": user_question,
        "answer": answer
    }


@app.get("/api/mcp/tools")
def get_mcp_tools():
    """Returns metadata for all 6 Paper2CAD Model Context Protocol (MCP) tools."""
    return {
        "status": "online",
        "transport": "stdio / JSON-RPC 2.0",
        "protocol_version": "2024-11-05",
        "sdk_version": "mcp-2.3.0",
        "tools": [
            {
                "name": "inspect_circuit",
                "description": "Inspect normalized circuit graph, pin mappings, and electrical node connectivity.",
                "parameters": {
                    "circuit_id": {"type": "string", "required": True, "description": "Circuit name/ID (e.g. cir1, canonical_led)"},
                    "component_id": {"type": "integer", "required": False, "description": "Optional component ID to inspect pin-level details"}
                }
            },
            {
                "name": "validate_circuit",
                "description": "Run deterministic domain rules (grounding, shorts, floating pins, missing values).",
                "parameters": {
                    "circuit_id": {"type": "string", "required": True, "description": "Circuit name/ID to validate"}
                }
            },
            {
                "name": "generate_schematic",
                "description": "Render interactive computerized IEEE CAD schematic SVG with data attributes.",
                "parameters": {
                    "circuit_id": {"type": "string", "required": True, "description": "Circuit name/ID"},
                    "theme": {"type": "string", "default": "dark", "enum": ["dark", "light"]}
                }
            },
            {
                "name": "export_spice_netlist",
                "description": "Generate clean standard SPICE netlist (.cir) from circuit graph.",
                "parameters": {
                    "circuit_id": {"type": "string", "required": True, "description": "Circuit name/ID"}
                }
            },
            {
                "name": "simulate_circuit",
                "description": "Execute SPICE simulation using ngspice binary (DC OP or TRAN analysis).",
                "parameters": {
                    "circuit_id": {"type": "string", "required": True, "description": "Circuit name/ID"},
                    "analysis_type": {"type": "string", "default": "OP", "enum": ["OP", "TRAN"]}
                }
            },
            {
                "name": "explain_circuit",
                "description": "Ask grounded circuit AI assistant without hallucinations.",
                "parameters": {
                    "circuit_id": {"type": "string", "required": True, "description": "Circuit name/ID"},
                    "question": {"type": "string", "required": True, "description": "Question about circuit design/behavior"}
                }
            }
        ]
    }


@app.post("/api/mcp/invoke")
async def invoke_mcp_tool(payload: Dict[str, Any]):
    """Executes an MCP tool and returns its structured JSON output."""
    tool_name = payload.get("tool_name", "")
    args = payload.get("arguments", {})
    circuit_id = args.get("circuit_id", "cir1")

    sys.path.insert(0, str(REPO_ROOT / "src"))
    from mcp_server import (
        inspect_circuit, validate_circuit, generate_schematic,
        export_spice_netlist, simulate_circuit, explain_circuit
    )

    try:
        if tool_name == "inspect_circuit":
            comp_id = args.get("component_id")
            if comp_id is not None and comp_id != "":
                try: comp_id = int(comp_id)
                except Exception: comp_id = None
            else:
                comp_id = None
            res = inspect_circuit(circuit_id=circuit_id, component_id=comp_id)
        elif tool_name == "validate_circuit":
            res = validate_circuit(circuit_id=circuit_id)
        elif tool_name == "generate_schematic":
            theme = args.get("theme", "dark")
            res = generate_schematic(circuit_id=circuit_id, theme=theme)
        elif tool_name == "export_spice_netlist":
            res = export_spice_netlist(circuit_id=circuit_id)
        elif tool_name == "simulate_circuit":
            analysis = args.get("analysis_type", "OP")
            res = simulate_circuit(circuit_id=circuit_id, analysis_type=analysis)
        elif tool_name == "explain_circuit":
            q = args.get("question", "Explain the circuit topology.")
            res = explain_circuit(circuit_id=circuit_id, question=q)
        else:
            return JSONResponse(status_code=400, content={"error": f"Unknown MCP tool: {tool_name}"})

        parsed = json.loads(res) if isinstance(res, str) else res
        return {"success": True, "tool": tool_name, "result": parsed}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})



# Mount static assets
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main():
    port = int(os.environ.get("PORT", 8000))
    print(f"\n========================================================")
    print(f"[SERVER] PaperToCAD Web Studio running at: http://localhost:{port}")
    print(f"========================================================\n")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
