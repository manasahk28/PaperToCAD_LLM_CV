# -*- coding: utf-8 -*-
"""
Tests for Paper2CAD CircuitDataModel (Phase 2).
Uses standard library unittest for seamless execution.
"""

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.circuit_data_model import (
    CircuitGraph,
    ComponentModel,
    NodeModel,
    TerminalModel,
    UncertaintyRecord
)

CIR1_PATH = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / "cir1.final.json"


class TestCircuitDataModel(unittest.TestCase):

    def test_circuit_graph_from_final_json(self):
        self.assertTrue(CIR1_PATH.exists(), f"Sample final.json not found at {CIR1_PATH}")
        graph = CircuitGraph.from_final_json(CIR1_PATH)

        self.assertEqual(graph.image_name, "cir1")
        self.assertEqual(graph.width, 1198)
        self.assertEqual(graph.height, 683)
        self.assertEqual(len(graph.components), 8)
        self.assertGreater(len(graph.nodes), 0)

        # Verify component details
        c0 = graph.get_component(0)
        self.assertIsNotNone(c0)
        self.assertEqual(c0.type, "inductor")
        self.assertEqual(len(c0.bbox), 4)
        self.assertGreaterEqual(len(c0.terminals), 2)

        # Verify terminal coordinates are retained
        for t in c0.terminals:
            self.assertGreater(t.x, 0)
            self.assertGreater(t.y, 0)
            self.assertEqual(t.component_id, 0)

        # Verify text association
        self.assertTrue(c0.value == "100mH" or c0.label == "100mH")

        # Verify nodes
        connected_comps = graph.get_connected_components(0)
        self.assertGreater(len(connected_comps), 0)

    def test_circuit_graph_mutations(self):
        graph = CircuitGraph.from_final_json(CIR1_PATH)
        c0 = graph.get_component(0)
        self.assertIsNotNone(c0)

        # Test value mutation
        success = graph.update_component_value(0, "220mH")
        self.assertTrue(success)
        self.assertEqual(graph.get_component(0).value, "220mH")

        # Test terminal reconnection
        t0 = c0.terminals[0]
        new_node_id = 99
        success = graph.update_terminal_connection(0, t0.id, new_node_id)
        self.assertTrue(success)
        self.assertEqual(t0.connected_node_id, 99)

        node99 = graph.get_node(99)
        self.assertIsNotNone(node99)
        self.assertTrue(any(conn.component_id == 0 and conn.terminal_id == t0.id for conn in node99.connections))

    def test_circuit_graph_serialization(self):
        graph = CircuitGraph.from_final_json(CIR1_PATH)
        d = graph.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("components", d)
        self.assertIn("nodes", d)
        self.assertIn("uncertainties", d)

        final_json = graph.to_final_json()
        self.assertEqual(final_json["image"], "cir1")
        self.assertEqual(len(final_json["components"]), 8)
        self.assertEqual(len(final_json["nets"]), len(graph.nodes))

    def test_all_sample_circuits(self):
        json_dir = REPO_ROOT / "outputs" / "run1" / "final_result" / "json"
        for json_file in sorted(json_dir.glob("*.final.json")):
            graph = CircuitGraph.from_final_json(json_file)
            self.assertGreater(len(graph.components), 0, f"No components in {json_file.name}")
            self.assertGreater(len(graph.nodes), 0, f"No nodes in {json_file.name}")
            self.assertGreater(graph.width, 0)
            self.assertGreater(graph.height, 0)


if __name__ == "__main__":
    unittest.main()
