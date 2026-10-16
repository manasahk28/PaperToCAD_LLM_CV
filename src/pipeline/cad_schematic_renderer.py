#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Computerized CAD Schematic Renderer for PaperToCAD.
Translates detected circuit components and topological net connections into
professional, standardized IEEE electronic CAD schematic diagrams (SVG and PNG).
Features automatic topology detection:
- Single-loop / perimeter circuits (e.g. Battery + Resistor + LED + GND)
- Multi-branch parallel ladders / RLC networks (e.g. cir1 parallel branches)
- Common rail buses and orthogonal net routing
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import schemdraw
import schemdraw.elements as elm


class CADSchematicRenderer:
    """
    Renders standardized electronic CAD schematics with clean vector symbols,
    orthogonal wire routing, multi-branch rail alignment, and technical typography.
    """

    def __init__(self, theme: str = "dark"):
        self.theme = theme
        if theme == "dark":
            self.bg_color = "#070c16"
            self.grid_color = "rgba(56, 189, 248, 0.04)"
            self.wire_color = "#00f0ff"
            self.symbol_color = "#38bdf8"
            self.text_color = "#f8fafc"
            self.subtext_color = "#a855f7"
            self.junction_color = "#10b981"
            self.border_color = "rgba(56, 189, 248, 0.2)"
        else: # light / engineering print
            self.bg_color = "#ffffff"
            self.grid_color = "#f1f5f9"
            self.wire_color = "#0f172a"
            self.symbol_color = "#1e293b"
            self.text_color = "#0f172a"
            self.subtext_color = "#6366f1"
            self.junction_color = "#0f172a"
            self.border_color = "#cbd5e1"

    def _refine_component_type(self, comp: Dict[str, Any]) -> str:
        """
        Uses OCR text and classifier hints to accurately identify component type.
        """
        raw = (comp.get("cls_name_refined") or comp.get("cls_name") or "").lower()
        val = (comp.get("text_label") or "").strip().lower()

        if "light_emitting" in raw or "led" in raw:
            return "diode.light_emitting"
        if "battery" in raw:
            return "voltage.battery"

        if val:
            if "led" in val:
                return "diode.light_emitting"
            # Check for current source indicators (2A, 10mA, etc.)
            if ("a" in val or "ma" in val or "ua" in val) and not any(k in val for k in ("f", "h", "v", "ohm", "kω", "10k")):
                if any(k in raw for k in ("voltage", "source", "current", "resistor")):
                    return "current.dc"
            # Check for voltage source indicators (12V, 5V, etc.)
            if ("v" in val or "mv" in val) and not any(k in val for k in ("f", "h", "a")):
                if any(k in raw for k in ("current", "source", "voltage", "battery")):
                    return "voltage.battery" if "battery" in raw else "voltage.dc"
            # Inductor indicators (1H, 100mH)
            if ("h" in val or "mh" in val) and not any(k in val for k in ("ohm", "ω")):
                return "inductor"
            # Capacitor indicators (1F, 10uF, 100pF)
            if any(k in val for k in ("f", "uf", "pf", "nf")):
                return "capacitor.unpolarized"
            # Resistor indicators
            if any(k in val for k in ("ω", "ohm", "kω")) or (val.endswith("k") and not val.endswith("khz")):
                return "resistor"

        return raw

    def _extract_branches(
        self,
        components: List[Dict[str, Any]],
        padding: float = 60.0
    ) -> Tuple[List[List[Dict[str, Any]]], Optional[Dict[str, Any]], str]:
        """
        Extracts topological structure:
        - Accurately classifies whether the circuit is a 'single_loop' or 'parallel_ladder'.
        - Separates GND reference terminal.
        """
        raw_comps = [c for c in components if c.get("cls_name", "") not in ("text", "junction", "crossover")]
        
        gnd_comp = next((c for c in raw_comps if "gnd" in c.get("cls_name", "").lower() or "vss" in c.get("cls_name", "").lower()), None)
        active_comps = [c for c in raw_comps if c != gnd_comp]

        if not active_comps:
            return [], gnd_comp, "empty"

        # Calculate coordinates
        for c in active_comps:
            bbox = c["bbox"]
            c["_cx"] = (bbox[0] + bbox[2]) / 2.0 + padding
            c["_cy"] = (bbox[1] + bbox[3]) / 2.0 + padding
            c["_bw"] = abs(bbox[2] - bbox[0])
            c["_bh"] = abs(bbox[3] - bbox[1])

        xs = [c["_cx"] for c in active_comps]
        ys = [c["_cy"] for c in active_comps]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)

        # Check for left-side power source feeding a top rail (single loop pattern)
        sources = [c for c in active_comps if any(k in self._refine_component_type(c) for k in ("voltage", "battery", "source"))]
        has_left_source = False
        left_source = None

        for s in sources:
            # Source is near the left border
            if (s["_cx"] - min_x) <= 0.28 * span_x:
                passives = [c for c in active_comps if c not in sources]
                if passives:
                    min_pass_x = min(p["_cx"] for p in passives)
                    if min_pass_x >= s["_cx"] + 0.12 * span_x:
                        has_left_source = True
                        left_source = s
                        break

        if has_left_source:
            # Single perimeter loop
            top_passives = [c for c in active_comps if c != left_source]
            top_passives.sort(key=lambda c: c["_cx"])
            return [[left_source], top_passives], gnd_comp, "single_loop"

        # Cluster by Y coordinate into horizontal rows
        sorted_by_y = sorted(active_comps, key=lambda c: c["_cy"])
        rows: List[List[Dict[str, Any]]] = []
        threshold_y = 80.0

        for c in sorted_by_y:
            placed = False
            for r in rows:
                mean_y = sum(x["_cy"] for x in r) / len(r)
                if abs(c["_cy"] - mean_y) < threshold_y:
                    r.append(c)
                    placed = True
                    break
            if not placed:
                rows.append([c])

        for r in rows:
            r.sort(key=lambda c: c["_cx"])

        # Check if parallel ladder: 2+ horizontal rows spanning across similar width
        if len(rows) >= 2:
            return rows, gnd_comp, "parallel_ladder"

        return [sorted_by_y], gnd_comp, "single_loop"

    def render_svg_schematic(
        self,
        width: int,
        height: int,
        components: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, Any]]] = None,
        image_name: str = "schematic"
    ) -> str:
        """
        Renders a full layout-preserving vector CAD schematic as an SVG string.
        Topology-aware: supports both single-loop and parallel-ladder architectures.
        """
        padding = 60
        view_w = max(width + padding * 2, 850)
        view_h = max(height + padding * 2, 600)

        rows, gnd_comp, topo_type = self._extract_branches(components, padding)

        svg = []
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w} {view_h}" width="{view_w}" height="{view_h}">')
        svg.append('<defs>')
        
        # Grid pattern
        svg.append(f'''
        <pattern id="cadGrid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="{self.grid_color}" stroke-width="1"/>
        </pattern>
        <style>
          .cad-text {{ font-family: 'JetBrains Mono', 'Plus Jakarta Sans', monospace, sans-serif; font-weight: 600; }}
          .cad-val {{ font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700; fill: {self.subtext_color}; }}
          .cad-lbl {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 800; fill: {self.text_color}; }}
          .cad-component-group {{ cursor: pointer; transition: filter 0.2s ease, transform 0.2s ease; }}
          .cad-component-group:hover {{ filter: drop-shadow(0 0 8px #00f0ff); }}
          .cad-component-group.selected {{ filter: drop-shadow(0 0 12px #f59e0b); }}
          .cad-uncertain-badge {{ fill: #f59e0b; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: bold; }}
          .cad-junction-dot {{ cursor: pointer; transition: r 0.2s ease; }}
          .cad-junction-dot:hover {{ r: 6.5; }}
        </style>
        ''')
        svg.append('</defs>')

        # Background sheet
        svg.append(f'<rect width="{view_w}" height="{view_h}" fill="{self.bg_color}"/>')
        svg.append(f'<rect width="{view_w}" height="{view_h}" fill="url(#cadGrid)"/>')
        
        # Engineering Title Block / Border
        svg.append(f'<rect x="20" y="20" width="{view_w - 40}" height="{view_h - 40}" fill="none" stroke="{self.border_color}" stroke-width="2"/>')
        svg.append(f'''
        <g transform="translate({view_w - 280}, {view_h - 65})">
          <rect width="250" height="38" fill="rgba(16,23,38,0.7)" stroke="{self.border_color}" stroke-width="1" rx="4"/>
          <text x="12" y="16" font-size="11" fill="{self.text_color}" class="cad-text">PAPER-TO-CAD ENGINE</text>
          <text x="12" y="30" font-size="10" fill="{self.wire_color}" class="cad-text">CIRCUIT: {image_name.upper()} • IEEE-STD</text>
        </g>
        ''')

        junction_dots: List[Tuple[float, float]] = []

        # Layer 1: Orthogonal Wires
        svg.append(f'<g id="wires" stroke="{self.wire_color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none">')

        if topo_type == "parallel_ladder":
            all_comps = [c for r in rows for c in r]
            all_cx = [c["_cx"] for c in all_comps]
            min_cx = min(all_cx)
            max_cx = max(all_cx)

            x_left_bus = max(60.0, min_cx - 95.0)
            x_right_bus = min(view_w - 60.0, max_cx + 95.0)

            row_y_coords = []
            for r in rows:
                mean_y = sum(c["_cy"] for c in r) / len(r)
                row_y_coords.append(mean_y)
                for c in r:
                    c["_snap_cy"] = mean_y

                first_c = r[0]
                svg.append(f'<line x1="{x_left_bus:.1f}" y1="{mean_y:.1f}" x2="{first_c["_cx"] - 38:.1f}" y2="{mean_y:.1f}"/>')

                for k in range(len(r) - 1):
                    c1 = r[k]
                    c2 = r[k + 1]
                    svg.append(f'<line x1="{c1["_cx"] + 38:.1f}" y1="{mean_y:.1f}" x2="{c2["_cx"] - 38:.1f}" y2="{mean_y:.1f}"/>')

                last_c = r[-1]
                svg.append(f'<line x1="{last_c["_cx"] + 38:.1f}" y1="{mean_y:.1f}" x2="{x_right_bus:.1f}" y2="{mean_y:.1f}"/>')
                junction_dots.append((x_left_bus, mean_y))
                junction_dots.append((x_right_bus, mean_y))

            y_top = row_y_coords[0]
            y_bot = row_y_coords[-1]
            svg.append(f'<line x1="{x_left_bus:.1f}" y1="{y_top:.1f}" x2="{x_left_bus:.1f}" y2="{y_bot:.1f}"/>')
            svg.append(f'<line x1="{x_right_bus:.1f}" y1="{y_top:.1f}" x2="{x_right_bus:.1f}" y2="{y_bot:.1f}"/>')

            gnd_row_idx = len(rows) // 2
            gnd_y = row_y_coords[gnd_row_idx]
            svg.append(f'<line x1="{x_left_bus:.1f}" y1="{gnd_y:.1f}" x2="{x_left_bus - 40:.1f}" y2="{gnd_y:.1f}"/>')

        elif topo_type == "single_loop":
            # Single perimeter loop
            left_source = rows[0][0]
            top_passives = rows[1] if len(rows) > 1 else []

            x_left = left_source["_cx"]
            y_src = left_source["_cy"]

            y_top = min(p["_cy"] for p in top_passives) if top_passives else y_src - 100
            for p in top_passives:
                p["_snap_cy"] = y_top

            x_right = (max(p["_cx"] for p in top_passives) + 95.0) if top_passives else (x_left + 350.0)
            y_bottom = max(y_src + 110.0, y_top + 220.0)

            # Left vertical wire through source
            svg.append(f'<line x1="{x_left:.1f}" y1="{y_top:.1f}" x2="{x_left:.1f}" y2="{y_src - 38:.1f}"/>')
            svg.append(f'<line x1="{x_left:.1f}" y1="{y_src + 38:.1f}" x2="{x_left:.1f}" y2="{y_bottom:.1f}"/>')

            # Top horizontal wire through passives
            if top_passives:
                svg.append(f'<line x1="{x_left:.1f}" y1="{y_top:.1f}" x2="{top_passives[0]["_cx"] - 38:.1f}" y2="{y_top:.1f}"/>')
                for k in range(len(top_passives) - 1):
                    p1 = top_passives[k]
                    p2 = top_passives[k + 1]
                    svg.append(f'<line x1="{p1["_cx"] + 38:.1f}" y1="{y_top:.1f}" x2="{p2["_cx"] - 38:.1f}" y2="{y_top:.1f}"/>')
                svg.append(f'<line x1="{top_passives[-1]["_cx"] + 38:.1f}" y1="{y_top:.1f}" x2="{x_right:.1f}" y2="{y_top:.1f}"/>')
            else:
                svg.append(f'<line x1="{x_left:.1f}" y1="{y_top:.1f}" x2="{x_right:.1f}" y2="{y_top:.1f}"/>')

            # Right vertical wire down
            svg.append(f'<line x1="{x_right:.1f}" y1="{y_top:.1f}" x2="{x_right:.1f}" y2="{y_bottom:.1f}"/>')

            # Bottom return wire to left
            svg.append(f'<line x1="{x_right:.1f}" y1="{y_bottom:.1f}" x2="{x_left:.1f}" y2="{y_bottom:.1f}"/>')

            # Ground wire on bottom rail
            gnd_x = (x_left + x_right) * 0.65
            svg.append(f'<line x1="{gnd_x:.1f}" y1="{y_bottom:.1f}" x2="{gnd_x:.1f}" y2="{y_bottom + 25:.1f}"/>')
            junction_dots.append((gnd_x, y_bottom))

        else:
            comps = [c for r in rows for c in r]
            for i in range(len(comps) - 1):
                p1 = (comps[i]["_cx"] + 38, comps[i]["_cy"])
                p2 = (comps[i + 1]["_cx"] - 38, comps[i + 1]["_cy"])
                mid_x = (p1[0] + p2[0]) / 2.0
                svg.append(f'<path d="M {p1[0]:.1f} {p1[1]:.1f} L {mid_x:.1f} {p1[1]:.1f} L {mid_x:.1f} {p2[1]:.1f} L {p2[0]:.1f} {p2[1]:.1f}"/>')

        svg.append('</g>')

        # Layer 2: Standardized Computerized Symbols
        svg.append(f'<g id="symbols" stroke="{self.symbol_color}" stroke-width="2.5" fill="none">')
        prefix_counters: Dict[str, int] = {}

        if topo_type == "single_loop":
            left_source = rows[0][0]
            top_passives = rows[1] if len(rows) > 1 else []

            # Draw left source vertically
            eff_s = self._refine_component_type(left_source)
            desig_s = left_source.get("designator") or "V1"
            val_s = left_source.get("value") or left_source.get("text_label") or ""
            svg.append(self._render_symbol_svg(eff_s, left_source["_cx"], left_source["_cy"], is_horiz=False, desig=desig_s, val_text=val_s, comp_id=left_source.get("id")))

            # Draw top passives horizontally
            for p in top_passives:
                eff_p = self._refine_component_type(p)
                desig_p = p.get("designator") or p.get("text_label") or "R"
                val_p = p.get("value") or ""
                # If desig_p has value embedded, split cleanly
                if "\n" in desig_p:
                    parts = desig_p.split("\n", 1)
                    desig_p, val_p = parts[0], parts[1]
                svg.append(self._render_symbol_svg(eff_p, p["_cx"], p.get("_snap_cy", p["_cy"]), is_horiz=True, desig=desig_p, val_text=val_p, comp_id=p.get("id")))

            # Draw Ground symbol on bottom rail
            gnd_x = (left_source["_cx"] + (max(p["_cx"] for p in top_passives) + 95.0)) * 0.65 if top_passives else left_source["_cx"] + 150.0
            y_bottom = max(left_source["_cy"] + 110.0, (min(p["_cy"] for p in top_passives) if top_passives else 200.0) + 220.0)
            gnd_id = gnd_comp.get("id") if gnd_comp else None
            svg.append(self._render_symbol_svg("gnd", gnd_x, y_bottom + 25.0, is_horiz=True, desig="GND", val_text="", comp_id=gnd_id))

        else:
            for r in rows:
                for c in r:
                    cx = c["_cx"]
                    cy = c.get("_snap_cy", c["_cy"])
                    is_horiz = True

                    eff_type = self._refine_component_type(c)
                    val_text = c.get("text_label") or ""

                    # Determine designator prefix
                    if "resistor" in eff_type:
                        pref = "R"
                    elif "capacitor" in eff_type:
                        pref = "C"
                    elif "inductor" in eff_type:
                        pref = "L"
                    elif "light_emitting" in eff_type or "led" in eff_type:
                        pref = "LED"
                    elif "diode" in eff_type:
                        pref = "D"
                    elif "battery" in eff_type or "voltage" in eff_type:
                        pref = "V"
                    elif "current" in eff_type:
                        pref = "I"
                    else:
                        pref = "U"

                    desig = c.get("designator") or f"{pref}{prefix_counters.get(pref, 0) + 1}"
                    prefix_counters[pref] = prefix_counters.get(pref, 0) + 1
                    val_clean = c.get("value") or val_text

                    sym_svg = self._render_symbol_svg(eff_type, cx, cy, is_horiz, desig, val_clean, comp_id=c.get("id"))
                    svg.append(sym_svg)

            if topo_type == "parallel_ladder":
                x_left_bus = max(60.0, min_cx - 95.0)
                gnd_row_idx = len(rows) // 2
                gnd_y = row_y_coords[gnd_row_idx]
                svg.append(self._render_symbol_svg("gnd", x_left_bus - 40, gnd_y, True, "GND", ""))

        svg.append('</g>')

        # Layer 3: Junction Dots (●)
        svg.append(f'<g id="junctions" fill="{self.junction_color}">')
        for jx, jy in junction_dots:
            svg.append(f'<circle cx="{jx:.1f}" cy="{jy:.1f}" r="4.5"/>')
        svg.append('</g>')

        svg.append('</svg>')
        return "\n".join(svg)

    def _render_symbol_svg(
        self,
        c_type: str,
        cx: float,
        cy: float,
        is_horiz: bool,
        desig: str,
        val_text: str,
        comp_id: Optional[int] = None
    ) -> str:
        """
        Emits clean SVG elements for a single standardized electronic component symbol.
        """
        rot = 0 if is_horiz else 90
        comp_attr = f' data-comp-id="{comp_id}"' if comp_id is not None else ""
        elements = [f'<g class="cad-component-group"{comp_attr} transform="translate({cx:.1f}, {cy:.1f}) rotate({rot})">']

        if "resistor" in c_type:
            # IEEE standard zig-zag resistor
            elements.append(
                f'<path d="M -38 0 L -22 0 L -17 -9 L -10 9 L -3 -9 L 4 9 L 11 -9 L 17 9 L 22 0 L 38 0" '
                f'stroke="{self.symbol_color}" stroke-width="2.5" fill="none"/>'
            )
        elif "capacitor" in c_type:
            elements.append(
                f'<path d="M -38 0 L -6 0 M 6 0 L 38 0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<line x1="-6" y1="-18" x2="-6" y2="18" stroke="{self.symbol_color}" stroke-width="3"/>'
                f'<line x1="6" y1="-18" x2="6" y2="18" stroke="{self.symbol_color}" stroke-width="3"/>'
            )
        elif "inductor" in c_type:
            elements.append(
                f'<path d="M -38 0 L -24 0 A 6 6 0 0 1 -12 0 A 6 6 0 0 1 0 0 A 6 6 0 0 1 12 0 A 6 6 0 0 1 24 0 L 38 0" stroke="{self.symbol_color}" stroke-width="2.5" fill="none"/>'
            )
        elif "light_emitting" in c_type or "led" in c_type:
            # LED diode triangle with outward light rays
            elements.append(
                f'<path d="M -38 0 L -12 0 M 12 0 L 38 0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<polygon points="-12,-14 -12,14 12,0" fill="{self.symbol_color}" stroke="{self.symbol_color}" stroke-width="1.5"/>'
                f'<line x1="12" y1="-14" x2="12" y2="14" stroke="{self.symbol_color}" stroke-width="3"/>'
                f'<line x1="0" y1="-16" x2="10" y2="-27" stroke="{self.symbol_color}" stroke-width="2"/>'
                f'<polygon points="10,-27 4,-26 8,-22" fill="{self.symbol_color}"/>'
                f'<line x1="8" y1="-12" x2="18" y2="-23" stroke="{self.symbol_color}" stroke-width="2"/>'
                f'<polygon points="18,-23 12,-22 16,-18" fill="{self.symbol_color}"/>'
            )
        elif "diode" in c_type:
            elements.append(
                f'<path d="M -38 0 L -12 0 M 12 0 L 38 0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<polygon points="-12,-14 -12,14 12,0" fill="{self.symbol_color}" stroke="{self.symbol_color}" stroke-width="1.5"/>'
                f'<line x1="12" y1="-14" x2="12" y2="14" stroke="{self.symbol_color}" stroke-width="3"/>'
            )
        elif "battery" in c_type:
            # Standard multi-cell Battery symbol
            elements.append(
                f'<line x1="-38" y1="0" x2="-14" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<line x1="-14" y1="-20" x2="-14" y2="20" stroke="{self.symbol_color}" stroke-width="3"/>'
                f'<line x1="-4" y1="-10" x2="-4" y2="10" stroke="{self.symbol_color}" stroke-width="4.5"/>'
                f'<line x1="6" y1="-20" x2="6" y2="20" stroke="{self.symbol_color}" stroke-width="3"/>'
                f'<line x1="16" y1="-10" x2="16" y2="10" stroke="{self.symbol_color}" stroke-width="4.5"/>'
                f'<line x1="16" y1="0" x2="38" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<text x="-24" y="-12" font-size="12" font-weight="bold" fill="{self.text_color}" class="cad-text">+</text>'
                f'<text x="24" y="-12" font-size="14" font-weight="bold" fill="{self.text_color}" class="cad-text">-</text>'
            )
        elif "current" in c_type:
            elements.append(
                f'<line x1="-38" y1="0" x2="-20" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<line x1="20" y1="0" x2="38" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<circle cx="0" cy="0" r="20" stroke="{self.symbol_color}" stroke-width="2.5" fill="{self.bg_color}"/>'
                f'<line x1="-10" y1="0" x2="10" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<polygon points="10,-5 16,0 10,5" fill="{self.symbol_color}"/>'
            )
        elif "voltage" in c_type or "source" in c_type:
            elements.append(
                f'<line x1="-38" y1="0" x2="-20" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<line x1="20" y1="0" x2="38" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<circle cx="0" cy="0" r="20" stroke="{self.symbol_color}" stroke-width="2.5" fill="{self.bg_color}"/>'
                f'<text x="-12" y="4" font-size="14" font-weight="bold" fill="{self.text_color}" class="cad-text">+</text>'
                f'<text x="6" y="4" font-size="14" font-weight="bold" fill="{self.text_color}" class="cad-text">-</text>'
            )
        elif "gnd" in c_type or "vss" in c_type:
            elements.append(
                f'<line x1="0" y1="-25" x2="0" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<line x1="-18" y1="0" x2="18" y2="0" stroke="{self.symbol_color}" stroke-width="3"/>'
                f'<line x1="-12" y1="7" x2="12" y2="7" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<line x1="-6" y1="14" x2="6" y2="14" stroke="{self.symbol_color}" stroke-width="2"/>'
            )
        else:
            elements.append(
                f'<rect x="-24" y="-16" width="48" height="32" stroke="{self.symbol_color}" stroke-width="2.5" fill="{self.bg_color}"/>'
                f'<line x1="-38" y1="0" x2="-24" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
                f'<line x1="24" y1="0" x2="38" y2="0" stroke="{self.symbol_color}" stroke-width="2.5"/>'
            )

        elements.append('</g>')

        # Technical CAD Labels (Placed without rotation)
        lbl_x = cx
        lbl_y = cy - 26 if is_horiz else cy - 42
        val_y = lbl_y + 16

        elements.append(f'<g transform="translate(0, 0)">')
        elements.append(f'<text x="{lbl_x:.1f}" y="{lbl_y:.1f}" text-anchor="middle" class="cad-lbl">{desig}</text>')
        if val_text and val_text != desig:
            elements.append(f'<text x="{lbl_x:.1f}" y="{val_y:.1f}" text-anchor="middle" class="cad-val">{val_text}</text>')
        elements.append('</g>')

        return "\n".join(elements)

    def _create_schemdraw_elem(self, eff_type: str, label: str, length: float = 2.5):
        """Helper to create the appropriate schemdraw element."""
        eff = eff_type.lower()
        if "inductor" in eff:
            return elm.Inductor().right().label(label).length(length)
        elif "capacitor" in eff:
            return elm.Capacitor().right().label(label).length(length)
        elif "resistor" in eff:
            return elm.Resistor().right().label(label).length(length)
        elif "current" in eff:
            return elm.SourceI().right().label(label).length(length)
        elif "battery" in eff:
            return elm.Battery().right().label(label).length(length)
        elif "voltage" in eff:
            return elm.SourceV().right().label(label).length(length)
        elif "light_emitting" in eff or "led" in eff or "led" in label.lower():
            return elm.LED().right().label(label).length(length)
        elif "diode" in eff:
            return elm.Diode().right().label(label).length(length)
        else:
            return elm.Resistor().right().label(label).length(length)

    def render_schemdraw_circuit(
        self,
        components: List[Dict[str, Any]],
        output_svg_path: Path,
        output_png_path: Optional[Path] = None
    ) -> bool:
        """
        Renders an accurate textbook circuit diagram using schemdraw from detected components.
        Reconstructs both single-loop and multi-branch parallel ladders with common bus rails.
        """
        try:
            rows, gnd_comp, topo_type = self._extract_branches(components, padding=0.0)

            if not rows or not rows[0]:
                return False

            with schemdraw.Drawing(file=str(output_svg_path), show=False) as d:
                d.config(fontsize=12, unit=2.6)

                if topo_type == "parallel_ladder":
                    y_spacing = 3.2
                    max_comps = max(len(r) for r in rows)
                    total_width = max(max_comps * 2.8 + 0.5, 7.5)

                    for idx, row in enumerate(rows):
                        y = -idx * y_spacing
                        d += elm.Dot().at((0, y))

                        comp_w = total_width / len(row)
                        for c in row:
                            eff_type = self._refine_component_type(c)
                            lbl = c.get("text_label") or eff_type
                            elem = self._create_schemdraw_elem(eff_type, lbl, length=comp_w)
                            d += elem

                        d += elm.Line().right().tox(total_width)
                        d += elm.Dot().at((total_width, y))

                    # Left vertical rail
                    y_top = 0
                    y_bot = -(len(rows) - 1) * y_spacing
                    d += elm.Line().at((0, y_top)).to((0, y_bot))

                    # Ground on left rail
                    gnd_row_idx = len(rows) // 2
                    d += elm.Ground().at((0, -gnd_row_idx * y_spacing)).left()

                    # Right vertical rail
                    d += elm.Line().at((total_width, y_top)).to((total_width, y_bot))

                elif topo_type == "single_loop":
                    # Single perimeter loop
                    left_source = rows[0][0]
                    top_passives = rows[1] if len(rows) > 1 else []

                    eff_src = self._refine_component_type(left_source)
                    desig_s = left_source.get("designator") or "V1"
                    val_s = left_source.get("value") or left_source.get("text_label") or ""
                    lbl_s = f"{desig_s}\n{val_s}" if (val_s and val_s != desig_s) else desig_s

                    # 1. Left power source going UP
                    if "battery" in eff_src:
                        d += elm.Battery().up().label(lbl_s, loc="left")
                    elif "current" in eff_src:
                        d += elm.SourceI().up().label(lbl_s, loc="left")
                    else:
                        d += elm.SourceV().up().label(lbl_s, loc="left")

                    # 2. Top passives going RIGHT
                    for p in top_passives:
                        eff_p = self._refine_component_type(p)
                        lbl_p = p.get("text_label") or eff_p
                        d += self._create_schemdraw_elem(eff_p, lbl_p)

                    # 3. Right vertical line DOWN
                    d += elm.Line().down()

                    # 4. Bottom return rail to LEFT with ground
                    if gnd_comp:
                        d += elm.Line().left().tox(3.5)
                        d += elm.Dot()
                        d.push()
                        d += elm.Ground().down()
                        d.pop()
                    d += elm.Line().left().tox(0)

                else:
                    comps = rows[0]
                    for c in comps:
                        eff = self._refine_component_type(c)
                        lbl = c.get("text_label") or eff
                        d += self._create_schemdraw_elem(eff, lbl)
                    d += elm.Line().down()
                    d += elm.Line().left().tox(0)

            return True
        except Exception as e:
            print(f"[CAD Renderer] Schemdraw error: {e}")
            return False


def generate_cad_schematic_files(
    image_name: str,
    width: int,
    height: int,
    components: List[Dict[str, Any]],
    output_dir: Path
) -> Dict[str, str]:
    """
    Generates all computerized schematic formats:
    - Dark CAD Schematic (SVG)
    - Light CAD Schematic (SVG)
    - Schemdraw Textbook Schematic (SVG)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Dark CAD Schematic
    renderer_dark = CADSchematicRenderer(theme="dark")
    svg_dark = renderer_dark.render_svg_schematic(width, height, components, image_name=image_name)
    dark_svg_path = output_dir / f"{image_name}_cad_dark.svg"
    with open(dark_svg_path, "w", encoding="utf-8") as f:
        f.write(svg_dark)

    # 2. Light Blueprint Schematic
    renderer_light = CADSchematicRenderer(theme="light")
    svg_light = renderer_light.render_svg_schematic(width, height, components, image_name=image_name)
    light_svg_path = output_dir / f"{image_name}_cad_light.svg"
    with open(light_svg_path, "w", encoding="utf-8") as f:
        f.write(svg_light)

    # 3. Schemdraw Normalized Circuit
    schemdraw_svg_path = output_dir / f"{image_name}_schemdraw.svg"
    renderer_dark.render_schemdraw_circuit(components, schemdraw_svg_path)

    return {
        "cad_dark_svg": f"{image_name}_cad_dark.svg",
        "cad_light_svg": f"{image_name}_cad_light.svg",
        "schemdraw_svg": f"{image_name}_schemdraw.svg"
    }


def render_circuit_graph(graph: Any, output_dir: Path) -> Dict[str, str]:
    """
    Renders digital schematic files directly from a Paper2CAD CircuitGraph instance.
    """
    comps_dict = []
    for c in graph.components:
        comps_dict.append({
            "id": c.id,
            "cls_id": c.cls_id,
            "cls_name": c.type,
            "cls_name_refined": c.type_refined,
            "designator": c.label,
            "text_label": c.value or c.label,
            "value": c.value,
            "confidence": c.confidence,
            "bbox": c.bbox,
            "is_uncertain": any(u.target_id == c.id for u in getattr(graph, "uncertainties", []))
        })
    return generate_cad_schematic_files(graph.image_name, graph.width, graph.height, comps_dict, output_dir)

