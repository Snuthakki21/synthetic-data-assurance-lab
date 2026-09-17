import unittest
from unittest.mock import patch
from portfolio.runtime import Context, validate_schema, ProviderError
from portfolio.mcp import dispatch
from portfolio.registry import projects, execute

class RuntimeTests(unittest.TestCase):
    def test_no_network_local(self):
        with patch("urllib.request.build_opener", side_effect=AssertionError("network")):
            self.assertIsNone(Context().generate_json(task="x", data={}, schema={}))

    def test_nested_schema(self):
        schema = {"type": "object", "properties": {"ids": {"type": "array", "items": {"type": "string", "enum": ["a"]}}}, "required": ["ids"], "additionalProperties": False}
        validate_schema({"ids": ["a"]}, schema)
        for invalid in ({"ids": ["invented"]}, {"ids": [1]}, {"ids": [], "injected": True}, {}):
            with self.assertRaises(ValueError): validate_schema(invalid, schema)

    def test_boolean_is_not_integer(self):
        with self.assertRaises(ValueError): validate_schema(True, {"type": "integer"})

    def test_live_requires_explicit_model(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ProviderError): Context("live").generate_json(task="x", data={}, schema={})

    def test_non_tls_remote_rejected(self):
        with patch.dict("os.environ", {"AI_MODEL": "example", "AI_BASE_URL": "http://example.com/v1"}, clear=True):
            with self.assertRaises(ProviderError): Context("live").generate_json(task="x", data={}, schema={})

    def test_mcp_handshake(self):
        r = dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-11-25")

    def test_mcp_unknown_action_rejected(self):
        r = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "shell", "arguments": {}}})
        self.assertTrue(r["result"]["isError"])

    def test_mcp_inventory_and_run(self):
        r = dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(len(r["result"]["tools"]), len(projects()))
        pid = next(iter(projects()))
        r = dispatch({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": pid}})
        self.assertFalse(r["result"]["isError"])

    def test_report_provenance(self):
        pid = next(iter(projects()))
        report = execute(pid)
        self.assertEqual(report["provenance"]["mode"], "local")
        self.assertEqual(len(report["provenance"]["input_sha256"]), 64)
        self.assertEqual(report["provenance"]["model_calls"], [])
