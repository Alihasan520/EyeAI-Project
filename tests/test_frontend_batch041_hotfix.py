from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "Frontend"


def test_active_product_routes() -> None:
    app = (FRONTEND / "src/App.tsx").read_text(encoding="utf-8")
    assert '<Route path="assistant" element={<AssistantPage />} />' in app
    assert '<Route path="reports" element={<ReportsPage />} />' in app
    assert '<Route path="alerts" element={<AlertsPage />} />' in app


def test_image_modal_uses_blob_loader() -> None:
    modal = (FRONTEND / "src/components/analysis/ImageReviewModal.tsx").read_text(
        encoding="utf-8"
    )
    assert 'fetchAuthenticatedFile' in modal
    assert 'URL.createObjectURL(blob)' in modal
    assert 'setTimeout' in modal
    assert 'crossOrigin = "anonymous"' not in modal


def test_alert_api_and_page_present() -> None:
    api = (FRONTEND / "src/lib/api.ts").read_text(encoding="utf-8")
    assert "export function listAlerts" in api
    assert "export function acknowledgeAlert" in api
    assert (FRONTEND / "src/pages/AlertsPage.tsx").is_file()


def test_frontend_version() -> None:
    package = (FRONTEND / "package.json").read_text(encoding="utf-8")
    assert '"version": "0.4.1"' in package
