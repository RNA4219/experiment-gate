"""Persona routing module.

This module provides persona routing functionality for the Insight Agent.
"""

from experiment_gate.router.density_estimator import estimate_evidence_density
from experiment_gate.router.lead_persona import generate_routing_plan_async, generate_routing_plan
from experiment_gate.router.validator import validate_routing_plan, ensure_mandatory_audit_persona
from experiment_gate.router.fallback import (
    create_fallback_routing_plan,
    create_minimal_routing_plan,
    create_all_personas_routing_plan,
)
from experiment_gate.router.config import load_routing_config, get_default_routing_config, RoutingConfig

__all__ = [
    "estimate_evidence_density",
    "generate_routing_plan_async",
    "generate_routing_plan",
    "validate_routing_plan",
    "ensure_mandatory_audit_persona",
    "create_fallback_routing_plan",
    "create_minimal_routing_plan",
    "create_all_personas_routing_plan",
    "load_routing_config",
    "get_default_routing_config",
    "RoutingConfig",
]