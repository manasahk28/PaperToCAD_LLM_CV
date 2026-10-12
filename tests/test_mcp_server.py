# -*- coding: utf-8 -*-
"""
Tests for Paper2CAD MCP Server Tools (Phase 7).
Directly tests invocations of all 6 exposed tools:
- inspect_circuit
- validate_circuit
- generate_schematic
- export_spice_netlist
- simulate_circuit
- explain_circuit
"""

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "src" / "pipeline"))

from src.mcp_server import (
    inspect_circuit,
    validate_circuit,
    generate_schematic,
    export_spice_netlist,
    simulate_circuit,
    explain_circuit
)


class TestMCPServer(unittest.TestCase):

    def test_inspect_circuit_tool(self):
        res_str = inspect_circuit("cir1")
        res = json.loads(res_str)
        self.assertNotIn("error", res)
        self.assertEqual(res["circuit_id"], "cir1")
        self.assertIn("components", res)
        self.assertIn("nodes", res)
        self.assertGreater(len(res["components"]), 0)

    def test_validate_circuit_tool(self):
        res_str = validate_circuit("cir1")
        res = json.loads(res_str)
        self.assertNotIn("error", res)
        self.assertEqual(res["circuit_id"], "cir1")
        self.assertIn("findings", res)

    def test_generate_schematic_tool(self):
        res_str = generate_schematic("cir1", theme="dark")
        res = json.loads(res_str)
        self.assertNotIn("error", res)
        self.assertEqual(res["status"], "success")
        self.assertIn("files", res)
        self.assertIn("cad_dark_svg", res["files"])

    def test_export_spice_netlist_tool(self):
        res_str = export_spice_netlist("cir1")
        res = json.loads(res_str)
        self.assertNotIn("error", res)
        self.assertIn("netlist", res)
        self.assertIn(".END", res["netlist"].upper())

    def test_simulate_circuit_tool(self):
        res_str = simulate_circuit("cir1", analysis="OP")
        res = json.loads(res_str)
        self.assertNotIn("error", res)
        self.assertIn("available", res)
        self.assertIn("success", res)
        # Verify honest status report (whether ngspice is present or absent)
        self.assertIsInstance(res["available"], bool)

    def test_explain_circuit_tool(self):
        res_str = explain_circuit("cir1", question="What is connected to component 0?")
        res = json.loads(res_str)
        self.assertNotIn("error", res)
        self.assertEqual(res["circuit_id"], "cir1")
        self.assertIn("Component #0", res["explanation"])
        self.assertIn("Node", res["explanation"])


if __name__ == "__main__":
    unittest.main()
