# -*- coding: utf-8 -*-
"""
Tests for Paper2CAD Rule-Based Circuit Validator (Phase 4).
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src" / "pipeline"))

from circuit_data_model import CircuitGraph, ComponentModel, NodeModel, TerminalModel
from circuit_validator import CircuitValidator, ValidationFinding

CIR1_PATH = REPO_ROOT / "outputs" / "run1" / "final_result" / "json" / "cir1.final.json"


class TestCircuitValidator(unittest.TestCase):

    def test_cir1_validation(self):
        graph = CircuitGraph.from_final_json(CIR1_PATH)
        validator = CircuitValidator(graph)
        findings = validator.validate()

        self.assertIsInstance(findings, list)
        for f in findings:
            self.assertIn(f.severity, ("error", "warning", "info"))
            self.assertTrue(len(f.rule_id) > 0)
            self.assertTrue(len(f.explanation) > 0)
            self.assertTrue(len(f.suggested_action) > 0)

    def test_detect_accidental_short_circuit(self):
        graph = CircuitGraph.from_final_json(CIR1_PATH)
        c0 = graph.get_component(0)
        self.assertIsNotNone(c0)

        # Force both terminals of inductor #0 to connect to the exact same node (Node 2)
        c0.terminals[0].connected_node_id = 2
        c0.terminals[1].connected_node_id = 2

        validator = CircuitValidator(graph)
        findings = validator.validate()

        short_findings = [f for f in findings if f.rule_id == "RULE-SHORT-002"]
        self.assertGreater(len(short_findings), 0)
        self.assertIn(0, short_findings[0].affected_components)
        self.assertIn(2, short_findings[0].affected_nodes)

    def test_detect_missing_ground(self):
        graph = CircuitGraph.from_final_json(CIR1_PATH)
        # Strip all ground markers
        graph.components = [c for c in graph.components if c.type != "gnd"]
        for n in graph.nodes:
            n.is_ground = False
            if n.name == "0":
                n.name = "N0"

        validator = CircuitValidator(graph)
        findings = validator.validate()

        gnd_findings = [f for f in findings if f.rule_id == "RULE-GND-001"]
        self.assertEqual(len(gnd_findings), 1)
        self.assertEqual(gnd_findings[0].severity, "warning")

    def test_detect_negative_passive_value(self):
        graph = CircuitGraph.from_final_json(CIR1_PATH)
        c2 = graph.get_component(2)
        self.assertIsNotNone(c2)
        c2.value = "-100"

        validator = CircuitValidator(graph)
        findings = validator.validate()

        val_findings = [f for f in findings if f.rule_id == "RULE-VAL-006"]
        self.assertEqual(len(val_findings), 1)
        self.assertEqual(val_findings[0].severity, "error")


if __name__ == "__main__":
    unittest.main()
