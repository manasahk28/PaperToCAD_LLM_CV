# -*- coding: utf-8 -*-
"""
Paper2CAD Master Regression & Evaluation Test Suite (Phase 10).

Covers end-to-end verification across:
1. Component & wire extraction
2. Connectivity graph construction & terminal mapping
3. Junction & crossing handling
4. JSON schema consistency & serialization roundtrip
5. Rule-based circuit validation
6. SPICE netlist generation
7. Interactive CAD Schematic SVG rendering
8. Official MCP tool outputs
9. User correction mutation and re-rendering flow
10. Controlled Canonical Circuit (DC Voltage Source + Resistor + LED + Ground)
"""

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "src" / "pipeline"))

from circuit_data_model import CircuitGraph, ComponentModel, NodeModel, TerminalModel
from connectivity_inspector import ConnectivityInspector
from circuit_validator import CircuitValidator
from cad_schematic_renderer import CADSchematicRenderer, render_circuit_graph
from spice_simulator import SPICESimulator
from ai_assistant import AICircuitAssistant
from mcp_server import (
    inspect_circuit,
    validate_circuit,
    generate_schematic,
    export_spice_netlist,
    simulate_circuit,
    explain_circuit
)


class TestPaper2CADMasterSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cir1_path = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / "cir1.final.json"
        cls.assertTrue(cls.cir1_path.exists(), f"cir1.final.json missing at {cls.cir1_path}")

    # 1. Component & Wire Extraction
    def test_01_component_wire_extraction(self):
        json_dir = REPO_ROOT / "outputs" / "run1" / "final_result" / "json"
        samples = ["cir1", "cir2", "cir3", "cir4", "cir5"]
        for s in samples:
            p = json_dir / f"{s}.final.json"
            if p.exists():
                graph = CircuitGraph.from_final_json(p)
                self.assertGreater(len(graph.components), 0, f"{s} has no components")
                self.assertGreater(len(graph.nodes), 0, f"{s} has no nodes")
                self.assertGreater(graph.width, 0)
                self.assertGreater(graph.height, 0)

    # 2. Connectivity Graph & Terminal Mapping
    def test_02_connectivity_graph_and_terminals(self):
        graph = CircuitGraph.from_final_json(self.cir1_path)
        # Check component 0 (inductor)
        c0 = graph.get_component(0)
        self.assertIsNotNone(c0)
        self.assertEqual(len(c0.terminals), 2)
        # Confirm terminals have positive coordinates and connected nodes
        for t in c0.terminals:
            self.assertGreater(t.x, 0)
            self.assertGreater(t.y, 0)
            self.assertIsNotNone(t.connected_node_id)

    # 3. Junction & Crossing Handling
    def test_03_junction_and_crossing_handling(self):
        graph = CircuitGraph.from_final_json(self.cir1_path)
        self.assertIsInstance(graph.junctions, list)
        self.assertIsInstance(graph.wires, list)
        # Verify wire coordinates
        for w in graph.wires:
            self.assertGreater(w.length, 0)

    # 4. JSON Schema Consistency & Roundtrip
    def test_04_json_schema_consistency(self):
        graph = CircuitGraph.from_final_json(self.cir1_path)
        d = graph.to_dict()
        self.assertIn("components", d)
        self.assertIn("nodes", d)
        self.assertIn("uncertainties", d)

        # Roundtrip check
        graph2 = CircuitGraph(**d)
        self.assertEqual(len(graph2.components), len(graph.components))
        self.assertEqual(len(graph2.nodes), len(graph.nodes))

    # 5. Circuit Validation Rules
    def test_05_circuit_validation(self):
        graph = CircuitGraph.from_final_json(self.cir1_path)
        validator = CircuitValidator(graph)
        findings = validator.validate()
        self.assertIsInstance(findings, list)
        for f in findings:
            self.assertIn(f.severity, ("error", "warning", "info"))
            self.assertTrue(len(f.rule_id) > 0)
            self.assertTrue(len(f.explanation) > 0)

    # 6. SPICE Netlist Generation
    def test_06_spice_netlist_generation(self):
        res_str = export_spice_netlist("cir1")
        res = json.loads(res_str)
        self.assertIn("netlist", res)
        netlist = res["netlist"]
        self.assertIn(".TITLE", netlist)
        self.assertIn(".END", netlist)
        # Confirm components are present
        self.assertTrue(any(line.startswith(("R", "L", "C", "V", "I")) for line in netlist.splitlines()))

    # 7. CAD Schematic Rendering (SVG)
    def test_07_schematic_rendering(self):
        graph = CircuitGraph.from_final_json(self.cir1_path)
        out_dir = REPO_ROOT / "outputs" / "test_schematic_render"
        out_dir.mkdir(parents=True, exist_ok=True)
        files = render_circuit_graph(graph, out_dir)
        self.assertIn("cad_dark_svg", files)
        self.assertIn("cad_light_svg", files)

        svg_dark_path = out_dir / files["cad_dark_svg"]
        self.assertTrue(svg_dark_path.exists())
        with open(svg_dark_path, "r", encoding="utf-8") as f:
            svg_content = f.read()
        self.assertIn("<svg", svg_content)
        self.assertIn("cad-component-group", svg_content)
        self.assertIn("data-comp-id", svg_content)

    # 8. MCP Tools Verification
    def test_08_mcp_tools(self):
        # 1. inspect_circuit
        insp = json.loads(inspect_circuit("cir1"))
        self.assertEqual(insp["circuit_id"], "cir1")
        self.assertIn("components", insp)

        # 2. validate_circuit
        val = json.loads(validate_circuit("cir1"))
        self.assertIn("findings", val)

        # 3. explain_circuit
        exp = json.loads(explain_circuit("cir1", question="What is connected to component 0?"))
        self.assertIn("explanation", exp)

        # 4. simulate_circuit (verifies honest simulator response)
        sim = json.loads(simulate_circuit("cir1"))
        self.assertIn("available", sim)

    # 9. User Correction & Re-validation Flow
    def test_09_user_corrections_flow(self):
        graph = CircuitGraph.from_final_json(self.cir1_path)
        inspector = ConnectivityInspector(graph)

        # 1. Update component value
        ok, msg = inspector.apply_correction("update_value", {"comp_id": 0, "value": "250mH"})
        self.assertTrue(ok)
        self.assertEqual(graph.get_component(0).value, "250mH")

        # 2. Update component type
        ok, msg = inspector.apply_correction("update_type", {"comp_id": 0, "type": "inductor"})
        self.assertTrue(ok)

        # 3. Re-run validator
        validator = CircuitValidator(graph)
        findings = validator.validate()
        self.assertIsInstance(findings, list)

    # 10. Controlled Canonical Circuit: DC Source + Resistor + LED + Ground
    def test_10_controlled_canonical_circuit(self):
        """
        Tests controlled circuit:
        Node 0: Ground
        Node 1: V_BAT (+) to R1
        Node 2: R1 to LED Anode
        Node 0: LED Cathode to Ground
        """
        comps = [
            ComponentModel(
                id=1,
                type="voltage.battery",
                label="V1",
                value="9V",
                bbox=[50, 100, 120, 250],
                terminals=[
                    TerminalModel(id=1, name="+", x=85, y=100, component_id=1, connected_node_id=1),
                    TerminalModel(id=2, name="-", x=85, y=250, component_id=1, connected_node_id=0),
                ]
            ),
            ComponentModel(
                id=2,
                type="resistor",
                label="R1",
                value="330Ω",
                bbox=[180, 80, 320, 120],
                terminals=[
                    TerminalModel(id=3, name="T1", x=180, y=100, component_id=2, connected_node_id=1),
                    TerminalModel(id=4, name="T2", x=320, y=100, component_id=2, connected_node_id=2),
                ]
            ),
            ComponentModel(
                id=3,
                type="diode.light_emitting",
                label="LED1",
                value="Red",
                bbox=[380, 80, 460, 200],
                terminals=[
                    TerminalModel(id=5, name="A", x=380, y=100, component_id=3, connected_node_id=2),
                    TerminalModel(id=6, name="K", x=460, y=100, component_id=3, connected_node_id=0),
                ]
            ),
            ComponentModel(
                id=4,
                type="gnd",
                label="GND",
                value="0",
                bbox=[260, 240, 310, 290],
                terminals=[
                    TerminalModel(id=7, name="GND", x=285, y=240, component_id=4, connected_node_id=0),
                ]
            ),
        ]

        nodes = [
            NodeModel(id=0, name="0", is_ground=True, connections=[]),
            NodeModel(id=1, name="N1", is_ground=False, connections=[]),
            NodeModel(id=2, name="N2", is_ground=False, connections=[]),
        ]

        canonical_graph = CircuitGraph(
            image_name="test_battery_resistor_led",
            width=600,
            height=400,
            components=comps,
            nodes=nodes
        )

        validator = CircuitValidator(canonical_graph)
        findings = validator.validate()

        # Should have NO error findings (properly closed loop with ground and current-limiting resistor)
        errors = [f for f in findings if f.severity == "error"]
        self.assertEqual(len(errors), 0, f"Unexpected validation errors: {errors}")

        # Test digital schematic generation
        out_dir = REPO_ROOT / "outputs" / "test_canonical_led"
        out_dir.mkdir(parents=True, exist_ok=True)
        files = render_circuit_graph(canonical_graph, out_dir)
        self.assertTrue((out_dir / files["cad_dark_svg"]).exists())


if __name__ == "__main__":
    unittest.main()
