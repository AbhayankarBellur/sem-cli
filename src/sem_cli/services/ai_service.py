"""Google Gemini AI integration for evidence-grounded engineering & business interpretation."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from sem_cli.analytics.hotspots import HotspotItem
from sem_cli.analytics.risk import RiskAssessment
from sem_cli.config.settings import AIConfig
from sem_cli.metrics.schema import Finding, MetricResult

logger = logging.getLogger(__name__)


@dataclass
class EvidencePayload:
    repository_name: str
    commit_sha: str
    business_context: str | None
    metrics_summary: dict[str, Any]
    top_hotspots: list[dict[str, Any]]
    top_findings: list[dict[str, Any]]
    risk_assessment: dict[str, Any]
    limitations: list[str] = field(default_factory=lambda: [
        "No production incident or runtime crash telemetry provided.",
        "Defect prediction models without labeled historical bug tracking are unvalidated.",
        "Static findings represent rule-based indicators, not confirmed exploits.",
    ])


@dataclass
class AIAnalysisResponse:
    mode: str
    executive_summary: str
    evidence_considered: list[str]
    main_risks: list[str]
    recommended_actions: list[str]
    confidence_and_limitations: str
    supporting_files: list[str]
    raw_response: str


def build_evidence_payload(
    repo_name: str,
    commit_sha: str,
    metrics: list[MetricResult],
    findings: list[Finding],
    hotspots: list[HotspotItem],
    risk: RiskAssessment,
    business_context: str | None = None,
) -> EvidencePayload:
    """Build a minimized, sanitized evidence payload without raw source code."""
    repo_metrics: dict[str, Any] = {}
    for m in metrics:
        if m.scope_type == "repository" and m.value is not None:
            repo_metrics[m.name] = m.value

    top_h = [
        {
            "file": h.file_path,
            "hotspot_score": h.hotspot_score,
            "complexity": h.complexity_score,
            "change_frequency": h.change_count,
            "churn": h.churn,
            "priority": h.priority_level,
            "reasons": h.supporting_findings,
        }
        for h in hotspots[:7]
    ]

    top_f = [
        {
            "rule_id": f.rule_id,
            "severity": f.severity,
            "category": f.category,
            "message": f.message,
            "file": f.file_path,
            "line": f.line_start,
        }
        for f in findings[:10]
    ]

    risk_dict = {
        "overall_score": risk.overall_risk_score,
        "level": risk.risk_level,
        "components": risk.component_scores,
    }

    return EvidencePayload(
        repository_name=repo_name,
        commit_sha=commit_sha,
        business_context=business_context,
        metrics_summary=repo_metrics,
        top_hotspots=top_h,
        top_findings=top_f,
        risk_assessment=risk_dict,
    )


class GeminiAIService:
    """Provides optional Gemini-assisted evidence interpretation."""

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.api_key = config.api_key or os.environ.get("GEMINI_API_KEY")

    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    def generate_review(
        self,
        payload: EvidencePayload,
        mode: str = "engineering_review",
        user_question: str | None = None,
    ) -> AIAnalysisResponse:
        """Submit minimized evidence payload to Gemini and return structured interpretation."""
        if not self.is_available():
            raise RuntimeError(
                "Gemini API key is not configured. Set GEMINI_API_KEY environment variable "
                "or pass an API key to enable AI-assisted interpretation."
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "google-genai package is not installed. Install with `pip install google-genai`."
            ) from exc

        client = genai.Client(api_key=self.api_key)

        system_instruction = (
            "You are an expert Principal Software Engineer and Metrics Analyst for sem-cli. "
            "You are provided with verified numeric metrics, Git history mining evidence, static analysis findings, "
            "and hotspot calculations for a software repository. "
            "GUARDRAILS:\n"
            "1. NEVER invent numbers or metrics not present in the evidence.\n"
            "2. NEVER claim a vulnerability exists unless backed by a specific finding in the payload.\n"
            "3. DO NOT claim defect predictions are validated without labeled defect data.\n"
            "4. Base business-impact insights strictly on user-provided business context or label them as potential operational hypotheses.\n"
            "5. Always reference specific files and measurements in your recommendations.\n"
            "Format your response as valid JSON with keys: "
            "'executive_summary' (string), 'evidence_considered' (list of strings), 'main_risks' (list of strings), "
            "'recommended_actions' (list of strings), 'confidence_and_limitations' (string), 'supporting_files' (list of strings)."
        )

        prompt_text = f"""
Mode: {mode}
User Question / Focus: {user_question or 'Comprehensive engineering review of codebase health and hotspots'}

EVIDENCE PAYLOAD:
{json.dumps(asdict(payload), indent=2)}
"""

        try:
            response = client.models.generate_content(
                model=self.config.model,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw_text = response.text or "{}"
            parsed = json.loads(raw_text)

            return AIAnalysisResponse(
                mode=mode,
                executive_summary=parsed.get("executive_summary", "Review completed successfully."),
                evidence_considered=parsed.get("evidence_considered", []),
                main_risks=parsed.get("main_risks", []),
                recommended_actions=parsed.get("recommended_actions", []),
                confidence_and_limitations=parsed.get("confidence_and_limitations", "Based on static analysis and Git history."),
                supporting_files=parsed.get("supporting_files", []),
                raw_response=raw_text,
            )

        except Exception as exc:
            logger.error("Gemini API call failed: %s", exc)
            raise RuntimeError(f"Gemini API request failed: {exc}") from exc
