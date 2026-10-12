# -*- coding: utf-8 -*-
"""
Paper2CAD SPICE Simulator Engine (Phase 8).

Wraps ngspice execution for DC Operating Point (.OP) and Transient (.TRAN) simulations.
Features:
- Auto-detection of ngspice executable (PATH or NGSPICE_PATH environment variable)
- Robust netlist validation before simulation
- Standard output, errors, and numerical result parsing (node voltages, device currents)
- Graceful degradation when ngspice is not installed (honest status, no fabricated data)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class SimulationResult(BaseModel):
    """
    Standardized numerical output from a SPICE simulation run.
    """
    available: bool
    success: bool
    analysis_type: str = "OP"  # "OP", "TRAN", "AC"
    node_voltages: Dict[str, float] = Field(default_factory=dict)
    branch_currents: Dict[str, float] = Field(default_factory=dict)
    operating_points: List[Dict[str, Any]] = Field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""
    message: str = ""


class SPICESimulator:
    """
    Execution engine for Berkeley SPICE / ngspice circuit simulations.
    """

    def __init__(self, ngspice_path: Optional[str] = None):
        self.ngspice_bin = ngspice_path or os.environ.get("NGSPICE_PATH") or shutil.which("ngspice")

    def is_available(self) -> bool:
        """Checks if ngspice binary is found and executable."""
        if not self.ngspice_bin:
            return False
        try:
            res = subprocess.run([self.ngspice_bin, "--version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def validate_netlist(self, netlist_text: str) -> Tuple[bool, List[str]]:
        """
        Validates syntax prerequisites for Berkeley SPICE netlists.
        """
        errors = []
        lines = [line.strip() for line in netlist_text.splitlines() if line.strip() and not line.startswith("*")]

        if not lines:
            errors.append("Netlist is empty.")
            return False, errors

        # Must have ground node (0)
        has_ground = False
        has_elements = False
        has_end = False

        for line in lines:
            tokens = line.split()
            if tokens[0].upper() == ".END":
                has_end = True
                continue
            if tokens[0].startswith("."):
                continue  # SPICE control directive

            has_elements = True
            # Check node tokens for reference node 0
            if len(tokens) >= 3:
                nodes = tokens[1:3]
                if "0" in nodes:
                    has_ground = True

        if not has_elements:
            errors.append("Netlist contains no electrical circuit elements.")
        if not has_ground:
            errors.append("Netlist has no connection to reference Ground (Node 0).")
        if not has_end:
            errors.append("Netlist is missing required '.END' termination card.")

        return len(errors) == 0, errors

    def run_simulation(
        self,
        netlist_text: str,
        analysis: str = "OP",
        temp_dir: Optional[Path] = None
    ) -> SimulationResult:
        """
        Executes a real simulation using ngspice in batch mode.
        If ngspice is unavailable, returns honest diagnostic report without hallucination.
        """
        if not self.is_available():
            return SimulationResult(
                available=False,
                success=False,
                analysis_type=analysis,
                message=(
                    "ngspice simulator executable was not found on this system. "
                    "To enable SPICE simulation, install ngspice (e.g. 'winget install ngspice' or from https://ngspice.sourceforge.io) "
                    "and ensure 'ngspice' is in your PATH."
                )
            )

        valid, errors = self.validate_netlist(netlist_text)
        if not valid:
            return SimulationResult(
                available=True,
                success=False,
                analysis_type=analysis,
                message=f"Netlist pre-validation failed: {'; '.join(errors)}"
            )

        # Inject simulation command if not already present
        sim_netlist = self._prepare_simulation_cards(netlist_text, analysis)

        work_dir = temp_dir or Path(tempfile.gettempdir())
        netlist_file = work_dir / "sim_circuit.cir"
        raw_out_file = work_dir / "sim_output.raw"

        with open(netlist_file, "w", encoding="utf-8") as f:
            f.write(sim_netlist)

        cmd = [self.ngspice_bin, "-b", "-r", str(raw_out_file), str(netlist_file)]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            stdout = res.stdout
            stderr = res.stderr

            node_voltages, branch_currents = self._parse_ngspice_output(stdout)

            success = res.returncode == 0 and bool(node_voltages or branch_currents)

            return SimulationResult(
                available=True,
                success=success,
                analysis_type=analysis,
                node_voltages=node_voltages,
                branch_currents=branch_currents,
                raw_stdout=stdout,
                raw_stderr=stderr,
                message="Simulation completed successfully." if success else "Simulation finished with warnings or matrix singularity."
            )
        except subprocess.TimeoutExpired:
            return SimulationResult(
                available=True,
                success=False,
                analysis_type=analysis,
                message="SPICE simulation timed out after 15 seconds (possible convergence loop)."
            )
        except Exception as e:
            return SimulationResult(
                available=True,
                success=False,
                analysis_type=analysis,
                message=f"Execution error running ngspice: {str(e)}"
            )

    def _prepare_simulation_cards(self, netlist: str, analysis: str) -> str:
        """Injects control blocks for batch ngspice execution."""
        lines = netlist.splitlines()
        clean_lines = [l for l in lines if not l.strip().upper().startswith((".OP", ".TRAN", ".END"))]

        # Add control block
        control_cards = [
            "",
            ".control",
            "run",
            "display",
            "print all",
            ".endc",
            ""
        ]

        if analysis.upper() == "TRAN":
            control_cards.insert(0, ".TRAN 1u 10m")
        else:
            control_cards.insert(0, ".OP")

        clean_lines.extend(control_cards)
        clean_lines.append(".END")
        return "\n".join(clean_lines)

    def _parse_ngspice_output(self, output: str) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Parses printed node voltages and branch currents from ngspice batch output."""
        node_voltages: Dict[str, float] = {}
        branch_currents: Dict[str, float] = {}

        # Look for pattern: v(node) = 1.2345e+00 or Node = Voltage
        for line in output.splitlines():
            line_str = line.strip()
            # Match V(node) = 5.000000e+00
            m_v = re.search(r"v\(([^)]+)\)\s*=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", line_str, re.IGNORECASE)
            if m_v:
                node = m_v.group(1).upper()
                try:
                    val = float(m_v.group(2))
                    node_voltages[node] = val
                except ValueError:
                    pass

            # Match I(dev) or device#branch = 0.05
            m_i = re.search(r"(?:i\(([^)]+)\)|(\S+#branch))\s*=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", line_str, re.IGNORECASE)
            if m_i:
                dev = (m_i.group(1) or m_i.group(2)).upper()
                try:
                    val = float(m_i.group(3))
                    branch_currents[dev] = val
                except ValueError:
                    pass

        return node_voltages, branch_currents
