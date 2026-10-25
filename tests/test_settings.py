"""Settings: multi-provider config, encrypted key storage, rate limit (plan §6, §9-P6)."""
import json

from app import db, keys, providers


def test_key_encrypted_at_rest():
    keys.set_api_key("gemini", "AIza-super-secret-123")
    raw = db.get_conn().execute(
        "SELECT value FROM settings WHERE key = 'provider:gemini:key'").fetchone()["value"]
    assert "AIza-super-secret-123" not in raw          # never stored in plaintext
    assert keys.decrypt(raw) == "AIza-super-secret-123"
    assert keys.get_api_key("gemini") == "AIza-super-secret-123"
    keys.set_api_key("gemini", "")                     # clearing works
    assert keys.get_api_key("gemini") == ""


def test_per_role_models_and_default_provider():
    keys.set_model("writer", "gemini-2.5-pro")
    keys.set_model("reviewer", "gemini-2.5-flash")
    assert keys.get_model("writer") == "gemini-2.5-pro"
    assert keys.get_model("reviewer") == "gemini-2.5-flash"
    assert keys.get_model("reviser")  # falls back to config default

    keys.set_default_provider("mock")
    assert keys.get_default_provider() == "mock"
    try:
        keys.set_default_provider("nonsense")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_settings_roundtrip_via_api(client):
    resp = client.post("/api/settings", json={
        "default_provider": "mock",
        "models": {"writer": "m-writer", "reviewer": "m-reviewer"},
        "api_keys": {"openai": "sk-test-abc"},
        "base_urls": {"local": "http://localhost:1234/v1"},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["default_provider"] == "mock"
    assert body["models"]["writer"] == "m-writer"
    assert body["keys_set"]["openai"] is True
    # GET never leaks the key
    assert "sk-test-abc" not in json.dumps(client.get("/api/settings").json())
    assert keys.get_api_key("openai") == "sk-test-abc"
    assert keys.get_base_url("local") == "http://localhost:1234/v1"


def test_unknown_provider_rejected_by_generate():
    keys.set_default_provider("openai")
    try:
        providers.generate(
            [{"role": "system", "content": "[VAI TRÒ: intake]"},
             {"role": "user", "content": "x"}],
            provider="openai")
        raised = False
    except providers.ProviderError as exc:
        raised = True
        assert "HTTP" in str(exc) or "khoá" in str(exc) or "kết nối" in str(exc)
    finally:
        keys.set_default_provider("mock")
    assert raised


def test_rate_limit_blocks_after_burst(client, monkeypatch):
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "RATE_LIMIT_RUNS", 3)
    main_mod._run_times.clear()
    statuses = []
    for _ in range(5):
        resp = client.post("/api/generate", data={"text": "giáo án toán lớp 1 bài x"})
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            break
    main_mod._run_times.clear()
    assert 429 in statuses, f"rate limit never fired: {statuses}"
