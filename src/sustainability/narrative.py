"""
Bedrock narrative layer.

Hard rule enforced by this module's design: the LLM never does arithmetic.

Every figure is computed deterministically upstream and passed in as a fact
table. Bedrock's only job is turning that table into two sentences a maintenance
supervisor will read on a phone. If Bedrock is unavailable, the deterministic
fallback still produces a correct explanation -- the demo never depends on a
model call succeeding.

This separation is also the answer to "how do you stop it hallucinating the
carbon savings?": the model is not in a position to. It receives the numbers and
is instructed to restate them.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
)

SYSTEM_PROMPT = """You explain maintenance scheduling decisions to reliability engineers.

You will receive a JSON fact table containing figures that were computed by a
deterministic engine. Your rules:

1. Never compute, adjust, round differently, or invent a number. Restate only
   figures present in the fact table.
2. Never contradict the recommendation or the risk verdict.
3. If an option was blocked on safety grounds, say so plainly and say why.
4. Write two or three short sentences of plain English. No headings, no bullets,
   no preamble. A supervisor reads this on a phone between jobs.
5. Lead with the action, then the reason, then the risk position.
"""


def _fallback_narrative(facts: Dict) -> str:
    """Deterministic explanation. Always correct, slightly stiff."""
    rec = facts.get("recommendation", {})
    baseline = facts.get("baseline", {})
    risk = facts.get("risk", {})

    action = rec.get("option", "unknown").replace("_", " ").lower()
    parts = [f"Recommended action: {action}."]

    co2_saved = baseline.get("co2_saved_kg")
    cost_saved = baseline.get("cost_saved_eur")
    against = str(baseline.get("baseline", "the alternative")).replace("_", " ").lower()
    if co2_saved is not None and cost_saved is not None:
        if cost_saved >= 0:
            parts.append(
                f"Versus {against} this avoids {co2_saved:.1f} kg CO2e and "
                f"EUR {cost_saved:.0f}."
            )
        else:
            parts.append(
                f"Versus {against} this avoids {co2_saved:.1f} kg CO2e but costs "
                f"EUR {abs(cost_saved):.0f} more -- a carbon-led call, not a cost-led one."
            )

    lb = risk.get("ttf_lower_bound_days")
    cov = risk.get("coverage_level")
    if lb is not None and cov is not None:
        parts.append(
            f"At {cov:.0%} coverage the equipment has at least {lb:.1f} days of "
            f"remaining life, so the wait is inside the certified bound."
        )
    elif risk.get("deferral_permitted") is False:
        parts.append("Deferral was blocked: the risk of waiting is not certifiable.")

    return " ".join(parts)


def generate_narrative(
    facts: Dict,
    model_id: str = DEFAULT_MODEL_ID,
    region: Optional[str] = None,
) -> Dict[str, str]:
    """Return {'text': ..., 'source': 'bedrock'|'deterministic'}."""
    fallback = _fallback_narrative(facts)

    try:
        import boto3

        client = boto3.client(
            "bedrock-runtime", region_name=region or os.environ.get("AWS_REGION", "eu-north-1")
        )
        response = client.converse(
            modelId=model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": json.dumps(facts, indent=2, default=str)}],
                }
            ],
            inferenceConfig={"maxTokens": 300, "temperature": 0.2},
        )
        text = response["output"]["message"]["content"][0]["text"].strip()
        return {"text": text, "source": "bedrock", "model_id": model_id}

    except Exception as exc:
        logger.warning("[Narrative] Bedrock unavailable (%s). Using deterministic text.", exc)
        return {"text": fallback, "source": "deterministic"}


def build_fact_table(
    device_id: str,
    equipment_type: str,
    root_cause: str,
    recommendation: Dict,
    all_options: List[Dict],
    risk: Dict,
    grid: Dict,
    baseline: Dict,
) -> Dict:
    """Assemble the fact table handed to Bedrock. This IS the contract."""
    return {
        "device": {
            "id": device_id,
            "type": equipment_type,
            "root_cause": root_cause,
        },
        "grid": grid,
        "recommendation": recommendation,
        "options_considered": all_options,
        "risk": risk,
        "baseline": baseline,
    }
