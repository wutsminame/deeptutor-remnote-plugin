"""Run with PYTHONPATH pointing at the patched DeepTutor checkout.

These tests use upstream classes; only user-account lookup and HTTP transport
are mocked. Run in an isolated DEEPTUTOR_HOME directory.
"""
import json
import gzip

import httpx
import pytest

from deeptutor.capabilities.remnote.capability import RemNoteCapability
from deeptutor.capabilities.remnote.tools import MAX_RESPONSE_BYTES, RemNoteSearchTool
from deeptutor.core.context import UnifiedContext
from deeptutor.knowledge.kb_types import is_connected_kb, supports_rag_retrieval
from deeptutor.knowledge.manager import KnowledgeBaseManager
from deeptutor.runtime.registry.tool_registry import ToolRegistry


@pytest.fixture
def configured(tmp_path, monkeypatch):
    connections = tmp_path/"connections.json"
    connections.write_text(json.dumps({"private": {"url": "http://127.0.0.1:8081", "read_token": "r"*32}}))
    monkeypatch.setenv("DEEPTUTOR_REMNOTE_CONNECTIONS", str(connections))
    return connections


def test_manager_persists_pointer_and_metadata(configured, tmp_path):
    manager = KnowledgeBaseManager(base_dir=str(tmp_path/"kbs"))
    manager.register_remnote_kb("RemNote", connection_id="private")
    restored = KnowledgeBaseManager(base_dir=str(tmp_path/"kbs"))
    assert "RemNote" in restored.list_knowledge_bases()
    meta = restored.get_metadata("RemNote")
    assert meta["connection_id"] == "private" and meta["type"] == "remnote"
    assert "read_token" not in json.dumps(meta)
    assert is_connected_kb(meta) and not supports_rag_retrieval(meta)
    with pytest.raises(ValueError):
        restored.register_remnote_kb("RemNote", connection_id="private")


def test_registry_loads_real_tools_and_extension(configured):
    registry = ToolRegistry()
    registry.load_builtins()
    for name in RemNoteCapability.owned_tools:
        assert registry.get(name) is not None
        schema = registry.get(name).get_definition().to_openai_schema()
        assert "_connection_id" not in json.dumps(schema)
    from deeptutor.capabilities.registry import BUILTIN_LOOP_CAPABILITY_SPECS
    spec = next(s for s in BUILTIN_LOOP_CAPABILITY_SPECS if s.name == "remnote")
    assert isinstance(spec.create(), RemNoteCapability)


def test_capability_gates_and_overrides_model_arguments(configured, monkeypatch):
    from deeptutor.multi_user import knowledge_access
    monkeypatch.setattr(knowledge_access, "resolve_kb_metadata", lambda ref: {"type": "remnote", "connection_id": "private"})
    context = UnifiedContext(knowledge_bases=["RemNote"])
    cap = RemNoteCapability()
    assert cap.is_active(context) and cap.exclusive_tools
    assert cap.owned_kbs(context) == {"RemNote"}
    assert cap.augment_kwargs("remnote_search", {"_connection_id": "attacker"}, context)["_connection_id"] == "private"
    empty = UnifiedContext()
    assert not cap.is_active(empty)
    assert cap.augment_kwargs("remnote_search", {"_connection_id": "attacker"}, empty)["_connection_id"] == ""


def test_private_http_requires_explicit_admin_opt_in(configured, monkeypatch):
    from deeptutor.capabilities.remnote.binding import load_connection

    configured.write_text(json.dumps({"private": {
        "url": "http://remnote-sync:8081", "read_token": "r" * 32
    }}))
    with pytest.raises(ValueError, match="HTTPS or allowlisted private HTTP"):
        load_connection("private")
    monkeypatch.setenv("DEEPTUTOR_REMNOTE_ALLOW_PRIVATE_HTTP", "1")
    monkeypatch.setenv("DEEPTUTOR_REMNOTE_PRIVATE_HTTP_HOSTS", "remnote-sync")
    assert load_connection("private")["url"] == "http://remnote-sync:8081"

    configured.write_text(json.dumps({"private": {
        "url": "http://203.0.113.10:8081", "read_token": "r" * 32
    }}))
    with pytest.raises(ValueError, match="HTTPS or allowlisted private HTTP"):
        load_connection("private")


@pytest.mark.asyncio
async def test_tool_http_request_uses_server_owned_connection(configured, monkeypatch):
    calls = []
    async def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"results": [{"id": "r", "url": "https://www.remnote.com/w/kb/r"}]})
    client_class = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(respond), **kwargs))
    result = await RemNoteSearchTool().execute(query="中文语义问题", _connection_id="private")
    assert result.success and json.loads(result.content)["results"][0]["id"] == "r"
    assert calls[0].headers["authorization"] == "Bearer " + "r"*32
    assert str(calls[0].url) == "http://127.0.0.1:8081/v1/search"
    assert not (await RemNoteSearchTool().execute(query="test")).success


@pytest.mark.asyncio
async def test_tool_rejects_oversized_response(configured, monkeypatch):
    async def respond(request):
        return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await RemNoteSearchTool().execute(query="test", _connection_id="private")
    assert not result.success
    assert result.content == "RemNote response exceeded the safe size limit."


@pytest.mark.asyncio
async def test_tool_rejects_compressed_response(configured, monkeypatch):
    async def respond(request):
        return httpx.Response(
            200,
            headers={"Content-Encoding": "gzip"},
            content=gzip.compress(b'{"results": []}'),
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await RemNoteSearchTool().execute(query="test", _connection_id="private")
    assert not result.success
    assert result.content == "Compressed RemNote responses are not accepted."
