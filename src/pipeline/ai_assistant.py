# -*- coding: utf-8 -*-
"""
Paper2CAD Grounded AI Circuit Assistant (Phase 6).

Provides circuit analysis, domain explanations, and interactive Q&A
grounded strictly in:
1. Reconstructed CircuitGraph data (components, nets, coordinates, values)
2. Rule-based Validation findings (errors, warnings, suggested actions)
3. SPICE simulation outputs (when available)

Design Principles:
- Never hallucinate invisible components or phantom connections.
- Configurable LLM backend (OpenAI, Anthropic, Ollama, LM Studio via OpenAI-compatible API).
- High-quality offline grounded fallback mode when no external LLM API key is present.
- Every suggested correction is surfaced for explicit user confirmation.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from circuit_data_model import CircuitGraph, ComponentModel, NodeModel
from circuit_validator import ValidationFinding


SYSTEM_PROMPT = """You are Paper2CAD Assistant, an expert electrical engineering AI assistant.
You inspect and explain hand-drawn electrical circuits that have been reconstructed into digital schematics.

STRICT OPERATIONAL GUIDELINES:
1. Ground every answer STRICTLY in the supplied Circuit Data, Validation Findings, and Simulation Results.
2. DO NOT invent invisible wires, assume unverified connections, or fabricate simulation results.
3. If an OCR label or component connection is uncertain or missing, clearly state that it is unverified or flagged for user review.
4. When asked what is connected to a component, state the exact connected node IDs and neighboring components.
5. Provide clear, educational explanations of electrical behavior (e.g. how RLC filters operate, how voltage dividers work, how LEDs should be current-limited).
6. Any proposed graph edit must be phrased as a recommendation for user confirmation.
"""


class AICircuitAssistant:
    """
    AI Circuit Assistant providing grounded explanations and answering user questions.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")

    def explain_circuit(
        self,
        graph: CircuitGraph,
        findings: Optional[List[ValidationFinding]] = None,
        sim_result: Optional[Dict[str, Any]] = None,
        user_question: Optional[str] = None
    ) -> str:
        """
        Generates an insightful, grounded explanation of the circuit or answers a specific question.
        Uses external LLM if configured; otherwise uses deterministic topological analyzer.
        """
        # If external LLM key is configured, query LLM
        if self.api_key and self.api_key != "none":
            try:
                return self._call_llm(graph, findings or [], sim_result, user_question)
            except Exception as e:
                # Fall back gracefully to local grounded response
                fallback = self._generate_grounded_response(graph, findings or [], sim_result, user_question)
                return f"{fallback}\n\n*(Note: LLM API request failed: {e}; switched to deterministic grounded analysis)*"

        # Deterministic Grounded Analysis Mode (Always available, zero dependencies, zero hallucinations)
        return self._generate_grounded_response(graph, findings or [], sim_result, user_question)

    def _call_llm(
        self,
        graph: CircuitGraph,
        findings: List[ValidationFinding],
        sim_result: Optional[Dict[str, Any]],
        question: Optional[str]
    ) -> str:
        """Sends grounded JSON payload to OpenAI-compatible chat completion endpoint."""
        context_payload = {
            "image": graph.image_name,
            "components": [
                {
                    "id": c.id,
                    "type": c.display_type,
                    "label": c.label,
                    "value": c.value,
                    "terminals": [
                        {"id": t.id, "name": t.name, "connected_node": t.connected_node_id}
                        for t in c.terminals
                    ]
                }
                for c in graph.components
            ],
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "is_ground": n.is_ground,
                    "connected_components": [conn.component_id for conn in n.connections]
                }
                for n in graph.nodes
            ],
            "validation_findings": [f.model_dump() for f in findings],
            "simulation": sim_result or "Not run"
        }

        user_content = f"Here is the verified circuit representation extracted from the sketch:\n```json\n{json.dumps(context_payload, indent=2)}\n```\n\n"
        if question:
            user_content += f"User Question: {question}"
        else:
            user_content += "Please explain the circuit topology, identify the main electrical path, summarize validation findings, and provide your assessment."

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.2
        }

        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _generate_grounded_response(
        self,
        graph: CircuitGraph,
        findings: List[ValidationFinding],
        sim_result: Optional[Dict[str, Any]],
        question: Optional[str]
    ) -> str:
        """
        Generates a rigorous, deterministic grounded analysis of the circuit graph.
        Never hallucinates; derives strictly from topological nodes and components.
        """
        # If question is about a specific component (e.g. "What is connected to component 2?" or "resistor")
        if question:
            q_lower = question.lower()
            
            # Check for specific component ID query
            comp_match = re.search(r"(?:component|comp|#|r|c|l|v|d)\s*(\d+)", q_lower)
            if comp_match:
                cid = int(comp_match.group(1))
                comp = graph.get_component(cid)
                if comp:
                    connected_nodes = [t.connected_node_id for t in comp.terminals if t.connected_node_id is not None]
                    adjacent_comps = []
                    for nid in connected_nodes:
                        for other in graph.get_connected_components(nid):
                            if other.id != comp.id and other not in adjacent_comps:
                                adjacent_comps.append(other)

                    adj_str = ", ".join(f"**{c.display_type} #{c.id}** ({c.value or c.label or 'unlabeled'})" for c in adjacent_comps) or "No adjacent components (floating net)"
                    return (
                        f"### Component #{comp.id}: {comp.display_type.capitalize()} ({comp.value or comp.label or 'No value'})\n\n"
                        f"- **Type:** `{comp.display_type}` (confidence: {comp.confidence:.2f})\n"
                        f"- **Bounding Box:** `[{', '.join(f'{b:.1f}' for b in comp.bbox)}]`\n"
                        f"- **Connected Nodes:** {', '.join(f'Node #{nid}' for nid in connected_nodes) if connected_nodes else 'None (Open/Floating)'}\n"
                        f"- **Neighboring Components:** {adj_str}\n\n"
                        f"**Terminals:**\n" +
                        "\n".join(f"- Pin `{t.name}`: Attached to Node `{t.connected_node_id}` at sketch pixel `({t.x:.1f}, {t.y:.1f})`" for t in comp.terminals)
                    )

            # Check for validation question
            if "flag" in q_lower or "warning" in q_lower or "error" in q_lower or "rule" in q_lower:
                if not findings:
                    return "No validation errors or warnings are currently flagged on this circuit graph."
                res = ["### Active Validation Findings:\n"]
                for idx, f in enumerate(findings, 1):
                    res.append(f"**{idx}. [{f.severity.upper()}] {f.title}** ({f.rule_id})")
                    res.append(f"- **Explanation:** {f.explanation}")
                    res.append(f"- **Evidence:** {f.evidence}")
                    res.append(f"- **Suggested Action:** {f.suggested_action}\n")
                return "\n".join(res)

        # Standard comprehensive circuit explanation
        total_comps = len(graph.components)
        active_comps = [c for c in graph.components if c.type not in ("text", "junction")]
        sources = [c for c in active_comps if any(k in c.type for k in ("voltage", "current", "battery"))]
        passives = [c for c in active_comps if c.type in ("resistor", "capacitor", "inductor")]
        semiconductors = [c for c in active_comps if any(k in c.type for k in ("diode", "transistor", "amplifier", "opamp", "led"))]

        res = [f"## Circuit Overview: `{graph.image_name}`\n"]
        res.append(f"The hand-drawn diagram contains **{len(active_comps)} components** interconnected across **{len(graph.nodes)} electrical nodes**.\n")

        # Composition breakdown
        res.append("### Component Inventory:")
        if sources:
            res.append(f"- **Power Sources:** " + ", ".join(f"{s.display_type} #{s.id} ({s.value or 'nominal'})" for s in sources))
        if passives:
            res.append(f"- **Passives (R/L/C):** " + ", ".join(f"{p.display_type} #{p.id} ({p.value or 'unlabeled'})" for p in passives))
        if semiconductors:
            res.append(f"- **Active / Semiconductor:** " + ", ".join(f"{sc.display_type} #{sc.id}" for sc in semiconductors))
        if not sources and not passives and not semiconductors:
            res.append("- (No recognized electronic primitives)")

        # Topological Connectivity Summary
        res.append("\n### Electrical Network Topology:")
        has_ground = any(n.is_ground for n in graph.nodes)
        res.append(f"- **Reference Ground:** {'Detected (Node 0)' if has_ground else '⚠️ Not detected (floating)'}")
        res.append(f"- **Total Nodes:** {len(graph.nodes)} distinct equivalence nets.")

        # Validation Summary
        res.append("\n### Inspection & Rule Validation:")
        if not findings:
            res.append("✅ **All electrical validation checks passed.** No floating terminals, shorts, or dangling branches detected.")
        else:
            errors = [f for f in findings if f.severity == "error"]
            warnings = [f for f in findings if f.severity == "warning"]
            infos = [f for f in findings if f.severity == "info"]
            res.append(f"- **Errors:** {len(errors)}, **Warnings:** {len(warnings)}, **Notes:** {len(infos)}")
            for f in findings[:3]:  # Top 3 findings
                res.append(f"  - `[{f.severity.upper()}]` **{f.title}:** {f.suggested_action}")

        # SPICE Simulation Summary
        if sim_result and sim_result.get("success"):
            res.append("\n### SPICE Simulation (DC Operating Point):")
            voltages = sim_result.get("node_voltages", {})
            if voltages:
                res.append("- **Node Voltages:** " + ", ".join(f"`V({k}) = {v:.2f}V`" for k, v in list(voltages.items())[:6]))

        return "\n".join(res)
