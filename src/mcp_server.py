# -*- coding: utf-8 -*-
"""
Paper2CAD Official Model Context Protocol (MCP) Server (Phase 7).

Exposes real circuit analysis, inspection, validation, simulation, and schematic
tools using the official Python MCP SDK (MCPServer 2.x).

Tools exposed:
- inspect_circuit(circuit_id): Components, nodes, connections, uncertainties
- validate_circuit(circuit_id): Rule-based domain checks (shorts, floating pins, ground)
- generate_schematic(circuit_id, theme): Renders IEEE CAD SVG diagram
- export_spice_netlist(circuit_id): Synthesizes and exports SPICE .cir file
- simulate_circuit(circuit_id, analysis): Validates and runs simulation via ngspice
- explain_circuit(circuit_id, question): Grounded AI circuit explanation
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[0] if (Path(__file__).resolve().name == "mcp_server.py" and Path(__file__).resolve().parent.name != "src") else Path(__file__).resolve().parents[1]
PIPELINE_DIR = REPO_ROOT / "src" / "pipeline"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(PIPELINE_DIR))

from circuit_data_model import CircuitGraph
from connectivity_inspector import ConnectivityInspector
from circuit_validator import CircuitValidator
from cad_schematic_renderer import render_circuit_graph
from spice_simulator import SPICESimulator
from ai_assistant import AICircuitAssistant

from mcp.server.mcpserver import MCPServer

# Initialize MCPServer instance
mcp_server = MCPServer("Paper2CAD-Schematic-Inspector")


def _resolve_circuit_graph(circuit_id: str) -> CircuitGraph:
    """Helper to load circuit graph from sample circuits or UI job directories."""
    clean_id = circuit_id.strip()

    # 1. Check UI jobs
    ui_job_json = REPO_ROOT / "outputs" / "ui_jobs" / clean_id / "circuit.json"
    if ui_job_json.exists():
        with open(ui_job_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Check if stored as full graph or components list
            if "components" in data and "nodes" in data:
                return CircuitGraph(**data)
            # Otherwise build from final_json style
            return CircuitGraph.from_final_json(ui_job_json)

    # 2. Check sample final.json
    final_json = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / f"{clean_id}.final.json"
    if final_json.exists():
        return CircuitGraph.from_final_json(final_json)

    # 3. Check ground truth json
    gt_json = REPO_ROOT / "data" / "ground_truth" / f"{clean_id}.gt.json"
    if gt_json.exists():
        return CircuitGraph.from_final_json(gt_json)

    # Fallback to cir1
    fallback = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / "cir1.final.json"
    if fallback.exists():
        return CircuitGraph.from_final_json(fallback)

    raise FileNotFoundError(f"Could not resolve circuit or job ID '{circuit_id}'")


@mcp_server.tool()
def inspect_circuit(circuit_id: str = "cir1") -> str:
    """
    Inspects a reconstructed circuit diagram and returns structured components,
    terminals, connected electrical nodes, and uncertainty records.
    """
    try:
        graph = _resolve_circuit_graph(circuit_id)
        inspector = ConnectivityInspector(graph)
        return json.dumps({
            "circuit_id": graph.image_name,
            "summary": inspector.get_summary(),
            "components": inspector.inspect_components(),
            "nodes": inspector.inspect_nodes(),
            "uncertainties": inspector.inspect_uncertainties()
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.tool()
def validate_circuit(circuit_id: str = "cir1") -> str:
    """
    Runs domain-specific rule-based validation on the circuit graph.
    Detects floating terminals, accidental short circuits, missing ground reference,
    implausible values, and ambiguous wire crossings.
    """
    try:
        graph = _resolve_circuit_graph(circuit_id)
        validator = CircuitValidator(graph)
        findings = validator.validate()
        return json.dumps({
            "circuit_id": graph.image_name,
            "total_findings": len(findings),
            "findings": [f.model_dump() for f in findings]
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.tool()
def generate_schematic(circuit_id: str = "cir1", theme: str = "dark") -> str:
    """
    Renders the reconstructed circuit into standard IEEE electronic vector CAD schematic SVG.
    Returns the generated file paths and SVG markup location.
    """
    try:
        graph = _resolve_circuit_graph(circuit_id)
        out_dir = REPO_ROOT / "outputs" / "mcp_renders" / graph.image_name
        out_dir.mkdir(parents=True, exist_ok=True)
        files = render_circuit_graph(graph, out_dir)
        return json.dumps({
            "circuit_id": graph.image_name,
            "status": "success",
            "output_directory": str(out_dir),
            "files": files
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.tool()
def export_spice_netlist(circuit_id: str = "cir1") -> str:
    """
    Synthesizes and exports a Berkeley SPICE netlist (.cir) from the circuit graph.
    """
    try:
        from build_spice_netlists import export_one
        json_path = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / f"{circuit_id}.final.json"
        if not json_path.exists():
            json_path = REPO_ROOT / "data" / "ground_truth" / f"{circuit_id}.gt.json"

        out_dir = REPO_ROOT / "outputs" / "mcp_spice"
        out_dir.mkdir(parents=True, exist_ok=True)

        if json_path.exists():
            spice_file = export_one(str(json_path), str(out_dir))
            with open(spice_file, "r", encoding="utf-8") as f:
                content = f.read()
            return json.dumps({
                "circuit_id": circuit_id,
                "netlist_path": spice_file,
                "netlist": content
            }, indent=2)
        else:
            return json.dumps({"error": f"Circuit {circuit_id} final JSON not found"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.tool()
def simulate_circuit(circuit_id: str = "cir1", analysis: str = "OP") -> str:
    """
    Validates the circuit netlist and executes SPICE simulation (DC operating point or transient)
    using ngspice if available on the system.
    """
    try:
        netlist_res = json.loads(export_spice_netlist(circuit_id))
        if "netlist" not in netlist_res:
            return json.dumps({"error": "Failed to generate netlist for simulation"}, indent=2)

        simulator = SPICESimulator()
        sim_res = simulator.run_simulation(netlist_res["netlist"], analysis=analysis)
        return json.dumps(sim_res.model_dump(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.tool()
def explain_circuit(circuit_id: str = "cir1", question: str = "") -> str:
    """
    Provides a grounded electrical engineering explanation of the circuit topology,
    active validation findings, or answers a specific question without hallucination.
    """
    try:
        graph = _resolve_circuit_graph(circuit_id)
        validator = CircuitValidator(graph)
        findings = validator.validate()

        assistant = AICircuitAssistant()
        explanation = assistant.explain_circuit(
            graph=graph,
            findings=findings,
            user_question=question if question.strip() else None
        )
        return json.dumps({
            "circuit_id": graph.image_name,
            "question": question or "General circuit overview",
            "explanation": explanation
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def main():
    """Runs the MCP server over stdio transport."""
    mcp_server.run()


if __name__ == "__main__":
    main()
