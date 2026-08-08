from __future__ import annotations

from app.domain.routing import NearestExampleMatch, RouteJudgment


class MockRouteClassifier:
    """0028 M4.5 gate: stand-in for NvidiaNimRouteClassifier until a real API key is
    wired in for tier 2 (parallel to 0025 M5 item 3/6 for the answer model).

    Makes no real judgment. If a nearest-example hint is available, it trusts the hint's
    route at the hint's own similarity as confidence (still labeled "mock" in the reason
    so it's never confused with a real LLM judgment in logs/diagnostics). With no hint it
    defaults to legal_search: the other three routes block search entirely, so a random
    or fixed default among them would incorrectly block answerable questions far more
    often than defaulting to legal_search would incorrectly search unanswerable ones.

    MUST be replaced with NvidiaNimRouteClassifier before tier 2's misclassification/
    cost-gate numbers can be trusted for a real routing decision - the fixture evaluation
    run against this mock measures the mock's own default behavior, not model judgment.
    """

    async def classify(
        self, question: str, hint: NearestExampleMatch | None
    ) -> RouteJudgment:
        if hint is not None:
            return RouteJudgment(
                route=hint.route,
                confidence=hint.similarity,
                reason="mock_classifier: no real LLM call, using nearest-example hint only",
                missing_fields=hint.missing_fields,
            )
        return RouteJudgment(
            route="legal_search",
            confidence=0.0,
            reason="mock_classifier: no real LLM call and no hint, defaulting to legal_search",
        )
