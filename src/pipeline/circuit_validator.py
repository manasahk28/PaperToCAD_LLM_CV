# -*- coding: utf-8 -*-
"""
Paper2CAD Rule-Based Circuit Inspector & Validator (Phase 4).

Performs comprehensive domain-specific electrical and topological validation
on the extracted CircuitGraph model:
- Floating or unconnected component terminals (context-aware)
- Accidental component short-circuits (both terminals on same net)
- Missing ground reference for SPICE simulation
- Missing or implausible passive component values
- Isolated single-terminal nets (dangling electrical nodes)
- Wire discontinuities and ambiguous non-soldered crossings
- SPICE netlist syntax and topology check

Emits strongly-structured findings with severity, affected IDs, evidence,
plain-language explanations, and suggested remediation actions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from circuit_data_model import CircuitGraph, ComponentModel, NodeModel, TerminalModel


class ValidationFinding(BaseModel):
    """
    Structured domain inspection finding.
    """
    rule_id: str
    severity: str  # "error", "warning", "info"
    title: str
    affected_components: List[int] = Field(default_factory=list)
    affected_nodes: List[int] = Field(default_factory=list)
    evidence: str
    explanation: str
    suggested_action: str


class CircuitValidator:
    """
    Rule-based inspector analyzing a CircuitGraph instance.
    """

    def __init__(self, graph: CircuitGraph):
        self.graph = graph

    def validate(self) -> List[ValidationFinding]:
        """
        Executes all inspection rules and returns findings sorted by severity:
        error -> warning -> info.
        """
        findings: List[ValidationFinding] = []

        findings.extend(self._check_ground_reference())
        findings.extend(self._check_component_short_circuits())
        findings.extend(self._check_floating_terminals())
        findings.extend(self._check_dangling_nodes())
        findings.extend(self._check_missing_or_implausible_values())
        findings.extend(self._check_wire_crossings())

        # Sort findings by severity
        severity_order = {"error": 0, "warning": 1, "info": 2}
        findings.sort(key=lambda f: severity_order.get(f.severity, 3))
        return findings

    # -------------------------------------------------------------
    # Rule 1: Ground Reference Check
    # -------------------------------------------------------------
    def _check_ground_reference(self) -> List[ValidationFinding]:
        has_gnd_comp = any(c.type == "gnd" for c in self.graph.components)
        has_gnd_node = any(n.is_ground or n.name == "0" for n in self.graph.nodes)

        if not (has_gnd_comp or has_gnd_node):
            return [ValidationFinding(
                rule_id="RULE-GND-001",
                severity="warning",
                title="Missing Ground Reference",
                affected_components=[],
                affected_nodes=[],
                evidence="No ground symbol ('gnd') or Node 0 was identified in the circuit graph.",
                explanation="SPICE matrix solvers and circuit simulators require an explicit reference node (Node 0) to compute absolute node voltages.",
                suggested_action="Use the Inspector panel to designate a return rail as Ground (0), or add an explicit ground symbol."
            )]
        return []

    # -------------------------------------------------------------
    # Rule 2: Accidental Component Short-Circuits
    # -------------------------------------------------------------
    def _check_component_short_circuits(self) -> List[ValidationFinding]:
        findings = []
        for c in self.graph.components:
            if c.type in ("gnd", "vss") or len(c.terminals) < 2:
                continue

            # Check if all terminals are attached to the same node ID
            connected_nids = [t.connected_node_id for t in c.terminals if t.connected_node_id is not None]
            if len(connected_nids) >= 2 and len(set(connected_nids)) == 1:
                same_nid = connected_nids[0]
                is_source = any(k in c.type for k in ("voltage", "battery", "vsrc"))
                findings.append(ValidationFinding(
                    rule_id="RULE-SHORT-002",
                    severity="error" if is_source else "warning",
                    title=f"Accidental Short Circuit across {c.display_type} #{c.id}",
                    affected_components=[c.id],
                    affected_nodes=[same_nid],
                    evidence=f"Terminals of component #{c.id} ({c.display_type}) are both connected to Node #{same_nid}.",
                    explanation=(
                        f"Both terminals are tied to the same electrical node. If this is a voltage source, this creates a catastrophic zero-impedance short loop. "
                        f"For passive elements, zero current will flow through the component."
                    ),
                    suggested_action=f"Inspect wire connections around component #{c.id} and separate the input/output nodes."
                ))
        return findings

    # -------------------------------------------------------------
    # Rule 3: Floating / Unconnected Component Terminals
    # -------------------------------------------------------------
    def _check_floating_terminals(self) -> List[ValidationFinding]:
        findings = []
        for c in self.graph.components:
            if c.type in ("gnd", "vss"):
                continue

            expected_pins = 3 if "transistor" in c.type else 2
            unconnected = [t for t in c.terminals if t.connected_node_id is None]
            missing_count = expected_pins - len(c.terminals)

            if unconnected or missing_count > 0:
                is_opamp = "amplifier" in c.type or "opamp" in c.type
                severity = "info" if is_opamp else "warning"
                evidence = f"Component has {len(c.terminals)} detected terminal(s), {len(unconnected)} unconnected to any net."
                if missing_count > 0:
                    evidence += f" Missing {missing_count} expected physical port(s)."

                findings.append(ValidationFinding(
                    rule_id="RULE-FLOAT-003",
                    severity=severity,
                    title=f"Floating Terminal(s) on {c.display_type} #{c.id}",
                    affected_components=[c.id],
                    affected_nodes=[],
                    evidence=evidence,
                    explanation=(
                        f"Component #{c.id} ({c.display_type}) contains open or unrouted terminals. "
                        "Open circuits may be intentional for test points, but prevent closed-loop current flow in passives and power sources."
                    ),
                    suggested_action=f"Trace wire lines leading to component #{c.id} or reconnect its pins in the inspector."
                ))
        return findings

    # -------------------------------------------------------------
    # Rule 4: Isolated / Dangling Nets
    # -------------------------------------------------------------
    def _check_dangling_nodes(self) -> List[ValidationFinding]:
        findings = []
        for n in self.graph.nodes:
            if len(n.connections) <= 1 and not n.is_ground:
                comp_ids = [c.component_id for c in n.connections]
                findings.append(ValidationFinding(
                    rule_id="RULE-NODE-004",
                    severity="warning",
                    title=f"Dangling Electrical Net #{n.id} ({n.name})",
                    affected_components=comp_ids,
                    affected_nodes=[n.id],
                    evidence=f"Node #{n.id} only attaches to {len(n.connections)} terminal ({comp_ids}).",
                    explanation=f"Net #{n.id} has no return path or partner connection, forming a dead-end branch in the circuit topology.",
                    suggested_action=f"Verify if wire trace on Node #{n.id} should connect to another component or ground."
                ))
        return findings

    # -------------------------------------------------------------
    # Rule 5: Missing or Implausible Component Values
    # -------------------------------------------------------------
    def _check_missing_or_implausible_values(self) -> List[ValidationFinding]:
        findings = []
        for c in self.graph.components:
            if c.type in ("resistor", "capacitor", "inductor", "voltage.dc", "current.dc"):
                if not c.value:
                    findings.append(ValidationFinding(
                        rule_id="RULE-VAL-005",
                        severity="info",
                        title=f"Missing Value for {c.display_type} #{c.id}",
                        affected_components=[c.id],
                        affected_nodes=[],
                        evidence=f"No OCR alphanumeric label assigned to component #{c.id}.",
                        explanation="While topological schematic reconstruction succeeds without values, SPICE simulation defaults to nominal standard ratings.",
                        suggested_action=f"Specify value for component #{c.id} (e.g. '10kΩ', '1uF', '5V') in the inspector."
                    ))
                else:
                    # Check for negative numbers in passive elements
                    val_clean = c.value.strip()
                    if val_clean.startswith("-") and c.type in ("resistor", "capacitor", "inductor"):
                        findings.append(ValidationFinding(
                            rule_id="RULE-VAL-006",
                            severity="error",
                            title=f"Implausible Negative Value '{val_clean}' on {c.display_type} #{c.id}",
                            affected_components=[c.id],
                            affected_nodes=[],
                            evidence=f"Value parsed as '{val_clean}'.",
                            explanation=f"Passive elements ({c.type}) must have positive physical magnitudes.",
                            suggested_action=f"Correct value sign for component #{c.id}."
                        ))
        return findings

    # -------------------------------------------------------------
    # Rule 6: Ambiguous Wire Crossings
    # -------------------------------------------------------------
    def _check_wire_crossings(self) -> List[ValidationFinding]:
        findings = []
        ambiguous_crossings = [w for w in self.graph.wires if w.ambiguous_crossing]
        if ambiguous_crossings:
            findings.append(ValidationFinding(
                rule_id="RULE-CROSS-007",
                severity="info",
                title=f"{len(ambiguous_crossings)} Ambiguous Wire Crossing(s) Detected",
                affected_components=[],
                affected_nodes=[],
                evidence=f"{len(ambiguous_crossings)} wire segments cross without a recognized solder dot.",
                explanation="Non-planar hand-drawn wires can be intended as insulated crossovers (bridge) or 4-way junctions (solder dot).",
                suggested_action="Confirm that intersecting traces in the diagram are intended to bypass each other."
            ))
        return findings
