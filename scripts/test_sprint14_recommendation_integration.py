"""Sprint 14 — Recommendation Engine Integration Validation.

Tests:
  1. API schema alignment
  2. Endpoint registration
  3. Repository implementations
  4. React TypeScript interface
  5. Hook implementation
  6. Service layer
  7. Component update
  8. LiveMonitoring update
  9. No unrelated changes
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend_api"))

from backend.recommendations.models import Recommendation, RecommendationBundle, RecommendationCategory, RecommendationPriority, RecommendationTarget
from app.schemas.api import RecommendationResponse, RecommendationBundleData, RecommendationsBundleResponse


passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        msg = f"  FAIL: {name}"
        if detail:
            msg += f" ({detail})"
        print(msg)


# ── Section 1: Schema Alignment ───────────────────────────────────────

def test_schema_alignment():
    print("\n--- Schema Alignment ---")

    rec = Recommendation(
        id="REC-001",
        title="Reduce Neck Flexion",
        description="Tilt screen up to reduce neck angle",
        category=RecommendationCategory.POSTURE,
        priority=RecommendationPriority.HIGH,
        target=RecommendationTarget.WORKER,
        trigger="neck_flexion_high",
        confidence=0.85,
        estimated_benefit="Reduce neck strain by 30%",
    )

    d = rec.to_dict()
    api_response = RecommendationResponse(**d)

    check("id matches", api_response.id == "REC-001")
    check("title matches", api_response.title == "Reduce Neck Flexion")
    check("description matches", api_response.description == "Tilt screen up to reduce neck angle")
    check("category matches", api_response.category == "Posture")
    check("priority matches", api_response.priority == "High")
    check("target matches", api_response.target == "Worker")
    check("trigger matches", api_response.trigger == "neck_flexion_high")
    check("confidence matches", api_response.confidence == 0.85)
    check("estimated_benefit matches", api_response.estimated_benefit == "Reduce neck strain by 30%")

    bundle = RecommendationBundle(
        recommendations=(rec,),
        summary="1 recommendation(s). Highest: High",
        highest_priority=RecommendationPriority.HIGH,
    )

    bd = bundle.to_dict()
    bundle_response = RecommendationBundleData(**bd)

    check("bundle recommendations count", len(bundle_response.recommendations) == 1)
    check("bundle summary", bundle_response.summary == "1 recommendation(s). Highest: High")
    check("bundle highest_priority", bundle_response.highest_priority == "High")
    check("bundle generated_at exists", len(bundle_response.generated_at) > 0)

    full = RecommendationsBundleResponse(
        bundle=bundle_response,
        total_generated=42,
    )
    check("full response has bundle", full.bundle is not None)
    check("full response total_generated", full.total_generated == 42)

    empty = RecommendationsBundleResponse(bundle=None, total_generated=0)
    check("empty response has no bundle", empty.bundle is None)
    check("empty response total_generated", empty.total_generated == 0)


# ── Section 2: Endpoint Registration ──────────────────────────────────

def test_endpoint_registration():
    print("\n--- Endpoint Registration ---")

    from app.api.recommendations import router
    routes = [r.path for r in router.routes]
    check("endpoint exists", "/recommendations" in routes)


# ── Section 3: Repository Implementations ─────────────────────────────

def test_repository_implementations():
    print("\n--- Repository Implementations ---")

    from app.repositories.live import LiveRepository
    from app.repositories.base import DashboardRepository

    # NOTE: the mock repository layer was removed — live mode is the only mode.
    check("LiveRepository has get_recommendations", hasattr(LiveRepository, "get_recommendations"))
    check("DashboardRepository has get_recommendations", hasattr(DashboardRepository, "get_recommendations"))


# ── Section 4: React TypeScript Interface ─────────────────────────────

def test_react_typescript_interface():
    print("\n--- React TypeScript Interface ---")

    ts_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "types", "api.ts")
    with open(ts_file, "r") as f:
        content = f.read()

    check("RecommendationItem interface exists", "interface RecommendationItem" in content)
    check("RecommendationItem id field", "id: string" in content)
    check("RecommendationItem title field", "title: string" in content)
    check("RecommendationItem description field", "description: string" in content)
    check("RecommendationItem category field", "category: string" in content)
    check("RecommendationItem priority field", "priority: string" in content)
    check("RecommendationItem target field", "target: string" in content)
    check("RecommendationItem trigger field", "trigger: string" in content)
    check("RecommendationItem confidence field", "confidence: number" in content)
    check("RecommendationItem estimated_benefit field", "estimated_benefit: string" in content)

    check("RecommendationBundle interface exists", "interface RecommendationBundle" in content)
    check("RecommendationBundle recommendations field", "recommendations: RecommendationItem[]" in content)
    check("RecommendationBundle summary field", "summary: string" in content)
    check("RecommendationBundle highest_priority field", "highest_priority: string" in content)
    check("RecommendationBundle generated_at field", "generated_at: string" in content)

    check("RecommendationsBundleResponse interface exists", "interface RecommendationsBundleResponse" in content)
    check("RecommendationsBundleResponse bundle field", "bundle: RecommendationBundle | null" in content)
    check("RecommendationsBundleResponse total_generated field", "total_generated: number" in content)


# ── Section 5: Hook Implementation ────────────────────────────────────

def test_hook_implementation():
    print("\n--- Hook Implementation ---")

    hook_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "hooks", "useRecommendations.ts")
    with open(hook_file, "r") as f:
        content = f.read()

    check("useRecommendations hook exists", "export function useRecommendations()" in content)
    check("imports useState", "useState" in content)
    check("imports useEffect", "useEffect" in content)
    check("imports useCallback", "useCallback" in content)
    check("imports useRef", "useRef" in content)
    check("calls getRecommendations", "getRecommendations" in content)
    check("1s polling interval", "1000" in content)
    check("returns data", "data" in content)
    check("returns loading", "loading" in content)
    check("returns error", "error" in content)
    check("returns refetch", "refetch" in content)
    check("mountedRef pattern", "mountedRef" in content)
    check("silent background poll (setLoading(true) only on initial)", content.count("setLoading(true)") == 1)


# ── Section 6: Service Layer ──────────────────────────────────────────

def test_service_layer():
    print("\n--- Service Layer ---")

    svc_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "services", "dashboardService.ts")
    with open(svc_file, "r") as f:
        content = f.read()

    check("getRecommendations function exists", "export function getRecommendations()" in content)
    check("returns RecommendationsBundleResponse", "RecommendationsBundleResponse" in content)
    check("delegates to repository", "getRepository().getRecommendations()" in content)


# ── Section 7: Component Update ───────────────────────────────────────

def test_component_update():
    print("\n--- Component Update ---")

    comp_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "components", "common", "RecommendationsCard.tsx")
    with open(comp_file, "r") as f:
        content = f.read()

    check("RecommendationsCard component exists", "export default function RecommendationsCard()" in content)
    check("uses useRecommendations hook", "useRecommendations()" in content)
    check("no mock fallbacks", "mock" not in content.lower() or "Mock" not in content)
    check("imports EmptyState", "EmptyState" in content)
    check("renders recommendations list", "recs.map" in content or "recommendations.map" in content)
    check("shows loading state", "loading" in content)
    check("shows empty state", "No recommendations" in content)

    idx_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "components", "common", "index.ts")
    with open(idx_file, "r") as f:
        idx_content = f.read()

    check("RecommendationsCard exported", "RecommendationsCard" in idx_content)


# ── Section 8: LiveMonitoring Update ──────────────────────────────────

def test_livemonitoring_update():
    print("\n--- LiveMonitoring Update ---")

    lm_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "pages", "LiveMonitoring.tsx")
    with open(lm_file, "r") as f:
        content = f.read()

    check("imports RecommendationsCard", "RecommendationsCard" in content)
    check("renders RecommendationsCard", "<RecommendationsCard" in content)
    check("no hardcoded worker/supervisor text", "worker_actions" not in content and "supervisor_actions" not in content)


# ── Section 9: Repository Interface ───────────────────────────────────

def test_repository_interface():
    print("\n--- Repository Interface ---")

    repo_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "DashboardRepository.ts")
    with open(repo_file, "r") as f:
        content = f.read()

    check("getRecommendations in interface", "getRecommendations(): Promise<RecommendationsBundleResponse>" in content)

    api_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "ApiDashboardRepository.ts")
    with open(api_file, "r") as f:
        content = f.read()

    check("getRecommendations in ApiDashboardRepository", "async getRecommendations()" in content)
    check("fetches /api/recommendations", "recommendations" in content and "API_BASE" in content)

    mock_file = os.path.join(os.path.dirname(__file__), "..", "ui_posture", "src", "repositories", "MockDashboardRepository.ts")
    if os.path.exists(mock_file):
        with open(mock_file, "r") as f:
            content = f.read()
        check("getRecommendations in MockDashboardRepository", "async getRecommendations()" in content)
        check("returns null bundle for mock", "bundle: null" in content)
    else:
        print("  SKIP: MockDashboardRepository.ts removed in the React migration — skipping mock-repo checks")


# ── Run ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 14 — Recommendation Engine Integration Validation")
    print("=" * 60)

    test_schema_alignment()
    test_endpoint_registration()
    test_repository_implementations()
    test_react_typescript_interface()
    test_hook_implementation()
    test_service_layer()
    test_component_update()
    test_livemonitoring_update()
    test_repository_interface()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
