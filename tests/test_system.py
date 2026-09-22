import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from dataclasses import replace
import urllib.request
import urllib.error

from nexo7.config import Config, load_config
from nexo7.engine import Engine
from nexo7.net import TransportError, NoRedirect
from nexo7.providers import Completion, OpenAIProvider, OllamaProvider
from nexo7.server import make_server
from nexo7.store import Store
from nexo7.tools import calculate, PubMed, ToolBox


class ScriptedProvider:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []
    def complete(self, instructions, conversation, tools, model, max_tokens):
        self.requests.append(json.loads(json.dumps({"instructions": instructions, "conversation": conversation, "tools": tools, "model": model, "max_tokens": max_tokens})))
        return self.outputs.pop(0)
    tool_result = staticmethod(OpenAIProvider.tool_result)


class CalculatorTests(unittest.TestCase):
    def test_precedence_and_functions(self):
        self.assertEqual(calculate("2+3*4"), 14)
        self.assertEqual(calculate("sqrt(81) + abs(-3)"), 12)
        self.assertEqual(calculate("round(10/3, 2)"), 3.33)
    def test_executable_input_is_rejected(self):
        for code in ["__import__('os').system('id')", "(1).__class__", "[1]*9999999", "True", "open('secret')", "sum(range(999))"]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                calculate(code)
    def test_bounded_and_finite(self):
        for code in ["9**9999999", "1/0", "1e309", "(-1)**0.5", "sqrt(-1)", "+".join(["1"]*40)]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                calculate(code)


class StoreAndEngineTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.config = Config()
    def tearDown(self):
        self.store.close()
    def test_retrieval_and_deletion(self):
        doc = self.store.add_document("Wi-Fi", "El identificador del router de prueba es Faro-42.")
        hits = self.store.search("¿Cuál es el router de prueba?")
        self.assertIn("Faro-42", hits[0]["text"])
        self.assertTrue(self.store.delete_document(doc))
        self.assertEqual(self.store.search("router"), [])
    def test_fts_query_is_literal(self):
        self.store.add_document("Nota", "router seguro")
        self.store.search('" OR * NOT ) ; DROP TABLE documents;')
        self.assertEqual(len(self.store.documents()), 1)
    def test_direct_math_uses_no_model(self):
        spy = ScriptedProvider([])
        result = Engine(self.config, self.store, spy).chat("24.5*40")
        self.assertEqual(result["answer"], "980.0")
        self.assertEqual(result["stats"]["model_calls"], 0)
        self.assertEqual(spy.requests, [])
    def test_exact_cache_invalidation(self):
        engine = Engine(replace(self.config, persist_history=False), self.store)
        one = engine.chat("2+3")
        two = engine.chat("2+3")
        self.assertFalse(one["stats"]["cache_hit"])
        self.assertTrue(two["stats"]["cache_hit"])
        self.store.add_document("Otro", "Un documento nuevo")
        self.assertFalse(engine.chat("2+3")["stats"]["cache_hit"])
    def test_cache_keys_include_mode_and_context(self):
        engine = Engine(self.config, self.store)
        engine.chat("2+3", session="first")
        self.assertFalse(engine.chat("2+3", session="first")["stats"]["cache_hit"])
        self.assertFalse(engine.chat("2+3", session="other", mode="eco")["stats"]["cache_hit"])
    def test_private_turn_leaves_no_history_or_answer_cache(self):
        result = Engine(self.config, self.store).chat("1+2", session="private", private=True)
        self.assertEqual(result["answer"], "3")
        self.assertEqual(self.store.history("private"), [])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)
    def test_history_is_persistent_and_deletable(self):
        Engine(self.config, self.store).chat("2+3", session="history")
        self.assertEqual(len(self.store.history("history")), 2)
        self.store.delete_history("history")
        self.assertEqual(self.store.history("history"), [])
    def test_tool_loop_preserves_native_context_and_usage(self):
        carry = [{"type": "reasoning", "id": "r1", "encrypted_content": "test-only"},
                 {"type": "function_call", "name": "calculate", "arguments": '{"expression":"6*7"}', "call_id": "c1"}]
        fake = ScriptedProvider([Completion(calls=[{"id": "c1", "name": "calculate", "arguments": '{"expression":"6*7"}'}], carry=carry, usage={"input_tokens": 20, "output_tokens": 12}),
                                 Completion(text="42", usage={"input_tokens": 35, "output_tokens": 2})])
        cfg = replace(self.config, provider="openai", model="explicit-test-model")
        result = Engine(cfg, self.store, fake).chat("Multiplica seis por siete")
        self.assertEqual(result["answer"], "42")
        self.assertEqual(result["stats"]["input_tokens"], 55)
        self.assertEqual(result["stats"]["output_tokens"], 14)
        self.assertIn(carry[0], fake.requests[1]["conversation"])
        self.assertEqual(fake.requests[1]["conversation"][-1]["call_id"], "c1")
    def test_unregistered_function_cannot_execute(self):
        fake = ScriptedProvider([Completion(calls=[{"id": "c", "name": "run_shell", "arguments": {"command": "id"}}], carry=[]), Completion(text="No disponible")])
        result = Engine(replace(self.config, provider="openai", model="test"), self.store, fake).chat("Usa una herramienta")
        self.assertEqual(result["trace"][0]["status"], "error")
        self.assertIn("Tool not authorized", fake.requests[1]["conversation"][-1]["output"])
    def test_tool_batch_cannot_exceed_budget(self):
        fake = ScriptedProvider([Completion(calls=[{"id":str(i),"name":"calculate","arguments":{"expression":"1+1"}} for i in range(3)])])
        cfg = replace(self.config, provider="openai", model="test", max_tool_calls=2)
        result = Engine(cfg, self.store, fake).chat("Usa funciones")
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(result["stats"]["tool_calls"], 0)
    def test_disabled_tools_and_last_round(self):
        cfg = replace(self.config, max_tool_calls=0)
        self.assertEqual(Engine(cfg, self.store).chat("2+3")["status"], "unavailable")
        fake = ScriptedProvider([Completion(calls=[{"id":"x","name":"calculate","arguments":{"expression":"1+1"}}])])
        cfg = replace(self.config, provider="openai", model="test", max_model_calls=1)
        result = Engine(cfg, self.store, fake).chat("Usa funciones")
        self.assertEqual(fake.requests[0]["tools"], [])
        self.assertEqual(result["status"], "budget_exhausted")
    def test_context_bound_keeps_latest_user(self):
        for i in range(8):
            self.store.save_turn("large", "historia "*500, "respuesta "*500)
        fake = ScriptedProvider([Completion(text="Respuesta")])
        cfg = replace(self.config, provider="openai", model="test", max_context_chars=7000)
        Engine(cfg, self.store, fake).chat("Pregunta final", session="large")
        req = fake.requests[0]
        size = len(req["instructions"])+len(json.dumps(req["conversation"],ensure_ascii=False))+len(json.dumps(req["tools"],ensure_ascii=False))
        self.assertLessEqual(size, 7000)
        self.assertEqual(req["conversation"][-1]["content"], "Pregunta final")
    def test_incomplete_provider_result_is_not_cached(self):
        fake = ScriptedProvider([Completion(text="Parcial", incomplete=True)])
        cfg = replace(self.config, provider="openai", model="test")
        result = Engine(cfg, self.store, fake).chat("Saluda")
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)
    def test_provider_failure_preserves_unknown_usage(self):
        fake = ScriptedProvider([])
        fake.complete = lambda *args: (_ for _ in ()).throw(TransportError("No disponible"))
        result = Engine(replace(self.config, provider="openai", model="test"), self.store, fake).chat("Saluda")
        self.assertEqual(result["status"], "upstream_error")
        self.assertFalse(result["stats"]["usage_complete"])
        self.assertIsNone(result["stats"]["estimated_cost_usd"])
    def test_unknown_citations_marked(self):
        text, warnings = Engine._check_citations("[P123] [P999] https://evil.example", [{"id":"P123","url":"https://pubmed.ncbi.nlm.nih.gov/123/"}], True)
        self.assertIn("[P123]", text)
        self.assertNotIn("[P999]", text)
        self.assertNotIn("evil.example", text)
        self.assertTrue(warnings)
    def test_total_output_budget_stops_followup(self):
        fake = ScriptedProvider([Completion(calls=[{"id":"c","name":"calculate","arguments":{"expression":"1+1"}}],usage={"output_tokens":100})])
        cfg = replace(self.config, provider="openai", model="test", max_output_tokens=128, max_total_output_tokens=128)
        result = Engine(cfg,self.store,fake).chat("Usa la calculadora")
        self.assertEqual(result["status"],"budget_exhausted")
        self.assertEqual(len(fake.requests),1)
        self.assertEqual(fake.requests[0]["max_tokens"],128)
    def test_estimated_cost_respects_cached_tokens_and_model(self):
        usage={"input_tokens":100,"cached_input_tokens":40,"output_tokens":20}
        cfg=replace(self.config,provider="openai",model="base",fast_model="other",input_price_per_million=2,cached_input_price_per_million=1,output_price_per_million=4)
        fake=ScriptedProvider([Completion(text="Respuesta",usage=usage),Completion(text="Otra",usage=usage)])
        engine=Engine(cfg,self.store,fake)
        self.assertAlmostEqual(engine.chat("Pregunta uno")["stats"]["estimated_cost_usd"],.00024)
        self.assertIsNone(engine.chat("Pregunta dos",mode="eco")["stats"]["estimated_cost_usd"])
    def test_research_network_failure_does_not_fabricate(self):
        class Failed:
            def search(self, *args, **kwargs):
                raise TransportError("Red no disponible")
        fake = ScriptedProvider([])
        result = Engine(self.config, self.store, fake, Failed()).chat("condition systematic review", mode="research")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sources"], [])
        self.assertEqual(fake.requests, [])
    def test_research_needs_real_records(self):
        class Empty:
            def search(self, *args, **kwargs):
                return {"papers": []}
        result = Engine(self.config, self.store, pubmed=Empty()).chat("condition review", mode="research")
        self.assertEqual(result["status"], "no_evidence")
    def test_research_records_reach_provider_and_private_disables_cache(self):
        class Papers:
            use_cache = None
            def search(self, query, use_cache=True):
                self.use_cache = use_cache
                return {"papers":[{"id":"P123","title":"Synthetic test fixture","text":"Fixture only","url":"https://pubmed.ncbi.nlm.nih.gov/123/"}]}
        paper = Papers()
        fake = ScriptedProvider([Completion(text="El registro de prueba no demuestra eficacia [P123].")])
        cfg = replace(self.config, provider="openai", model="test", deep_model="research-test")
        result = Engine(cfg, self.store, fake, paper).chat("condition review", mode="research", private=True)
        self.assertEqual(fake.requests[0]["model"], "research-test")
        self.assertIn("Fixture only", json.dumps(fake.requests[0]["conversation"]))
        self.assertFalse(paper.use_cache)
        self.assertEqual(result["sources"][0]["id"], "P123")


class AdaptersTests(unittest.TestCase):
    def test_openai_request_and_response_contract(self):
        fixture = {"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"hello"}]}],
                   "usage":{"input_tokens":30,"output_tokens":5,"input_tokens_details":{"cached_tokens":10}}}
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-key"}), patch("nexo7.providers.fetch_json", return_value=fixture) as request:
            result = OpenAIProvider(Config()).complete("rules", [{"role":"user","content":"hello"}], [], "explicit-model", 200)
            self.assertEqual(result.text, "hello")
            self.assertEqual(result.usage["cached_input_tokens"], 10)
            body=request.call_args.kwargs["payload"]
            self.assertFalse(body["store"])
            self.assertEqual(body["max_output_tokens"], 200)
            self.assertEqual(request.call_args.args[0], "https://api.openai.com/v1/responses")
    def test_ollama_normalizes_tools_and_usage(self):
        fixture={"message":{"role":"assistant","content":"","tool_calls":[{"function":{"name":"calculate","arguments":{"expression":"1+1"}}}]},"prompt_eval_count":10,"eval_count":8}
        with patch("nexo7.providers.fetch_json", return_value=fixture) as request, patch("nexo7.local_runtime.verify_runtime"):
            provider=OllamaProvider(Config(provider="ollama",model="qwen3.5:4b"))
            result=provider.complete("rules",[],[],"qwen3.5:4b",100)
            self.assertEqual(result.calls[0]["arguments"], {"expression":"1+1"})
            self.assertFalse(request.call_args.kwargs["payload"]["stream"])
            self.assertEqual(result.usage["output_tokens"],8)
    def test_pubmed_xml_preserves_abstract_and_retraction(self):
        xml=b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>Trial <i>example</i></ArticleTitle><Abstract><AbstractText Label="RESULTS">Synthetic fixture.</AbstractText></Abstract><PublicationTypeList><PublicationType>Retracted Publication</PublicationType></PublicationTypeList></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>'
        papers=PubMed.parse(xml,["123"])
        self.assertEqual(papers[0]["title"],"Trial example")
        self.assertTrue(papers[0]["retraction_flag"])
        self.assertIn("RESULTS",papers[0]["text"])
        self.assertEqual(PubMed.parse(xml,["999"]),[])
    def test_pubmed_search_then_fetch_without_arbitrary_host(self):
        store=Store(":memory:")
        try:
            pubmed=PubMed(store)
            fixture=b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><ArticleTitle>Fixture</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>'
            with patch.object(pubmed,"_request",side_effect=[{"esearchresult":{"idlist":["123","bad-id"]}},fixture]) as request:
                result=pubmed.search("test trial")
                self.assertEqual(result["papers"][0]["pmid"],"123")
                self.assertEqual(request.call_args_list[1].args[1]["id"],"123")
                self.assertEqual(pubmed.search("test trial"),result)
                self.assertEqual(request.call_count,2)
        finally:
            store.close()
    def test_redirects_disabled(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,"",{},"http://127.0.0.1"))
    def test_local_provider_destination_restrictions(self):
        for url in ["https://remote.example","http://127.0.0.1.evil.example","http://user:password@localhost:11434","http://localhost:11434/path"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                Config(ollama_url=url)
    def test_configuration_errors_fail_early(self):
        for kwargs in [{"provider":"openai"},{"max_model_calls":99},{"research_network":"yes"}]:
            with self.assertRaises(ValueError): Config(**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"config.toml";p.write_text('misspelled = 1')
            with self.assertRaises(ValueError):load_config(p)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(":memory:")
        self.server=make_server(Config(),self.store,port=0,token="test-access-token")
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_port}"
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.store.close()
    def call(self,path,method="GET",body=None,headers=None,auth=True):
        hdr={"Content-Type":"application/json",**({"X-Nexo-Key":"test-access-token"} if auth else {}),**(headers or {})}
        req=urllib.request.Request(self.base+path, data=json.dumps(body).encode() if body is not None else None,method=method,headers=hdr)
        return urllib.request.urlopen(req,timeout=5)
    def test_auth_host_origin_and_static_token(self):
        for params,code in [({"auth":False},401),({"headers":{"Origin":"https://evil.example"}},403),({"headers":{"Host":"evil.example"}},403)]:
            with self.assertRaises(urllib.error.HTTPError) as raised:self.call("/api/status",**params)
            self.assertEqual(raised.exception.code,code)
        with self.call("/",auth=False) as response:
            self.assertNotIn(b"test-access-token",response.read())
            self.assertIn("frame-ancestors 'none'",response.headers["Content-Security-Policy"])
    def test_chat_and_document_lifecycle(self):
        with self.call("/api/chat","POST",{"message":"10*7","session":"test"}) as response:
            self.assertEqual(json.load(response)["answer"],"70")
        with self.call("/api/documents","POST",{"title":"test","content":"router Faro"}) as response:doc=json.load(response)["id"]
        with self.call("/api/documents") as response:self.assertEqual(len(json.load(response)["documents"]),1)
        with self.call("/api/documents/"+doc,"DELETE") as response:self.assertTrue(json.load(response)["deleted"])
        with self.call("/api/history/test","DELETE") as response:self.assertTrue(json.load(response)["deleted"])
    def test_invalid_json_and_oversized_body(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:self.call("/api/chat","POST",{"message":"x"*8001})
        self.assertEqual(raised.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as raised:self.call("/api/chat","POST",{},headers={"Content-Length":"600000"})
        self.assertEqual(raised.exception.code,413)
    def test_no_arbitrary_file_serving(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:self.call("/../../config.toml")
        self.assertEqual(raised.exception.code,404)


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optional PyTorch is not installed")
class ExperimentalModelTests(unittest.TestCase):
    def test_causal_prefix_invariance_and_gradient(self):
        import torch
        from experiments.tiny_transformer import ModelConfig,TinyTransformer
        torch.manual_seed(42)
        model=TinyTransformer(ModelConfig(context=16,width=16,heads=2,layers=1)).eval()
        a=torch.tensor([[1,2,3,4]])
        b=torch.tensor([[1,2,9,8]])
        self.assertTrue(torch.allclose(model(a)[:,:2],model(b)[:,:2],atol=1e-6))
        loss=model(a).sum();loss.backward()
        self.assertTrue(any(p.grad is not None for p in model.parameters()))


if __name__ == "__main__":unittest.main()
