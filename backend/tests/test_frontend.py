import pytest

from app import create_app
from app.config import Config


@pytest.fixture
def client(tmp_path):
    (tmp_path / "index.html").write_text("<html>Termtable SPA</html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('Termtable');")
    app = create_app(Config)
    app.config.update(TESTING=True, FRONTEND_DIST=str(tmp_path))
    return app.test_client()


@pytest.mark.parametrize("path", ["/", "/calendar", "/planner", "/grades/1/2"])
def test_frontend_routes_return_spa(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"Termtable SPA" in response.data


def test_compiled_assets_are_served(client):
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert b"console.log" in response.data


@pytest.mark.parametrize("path", ["/api", "/api/unknown", "/assets/missing.js", "/missing.css", "/../.env"])
def test_missing_api_assets_and_unsafe_paths_do_not_return_spa(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert b"Termtable SPA" not in response.data


def test_api_routes_still_work(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json == {"ok": True}