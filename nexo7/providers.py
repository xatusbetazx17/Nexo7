from dataclasses import dataclass, field
import json
import os
import threading
from .net import fetch_json, TransportError


@dataclass
class Completion:
    text: str = ""
    calls: list = field(default_factory=list)
    carry: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    incomplete: bool = False


class OpenAIProvider:
    def __init__(self, config):
        self.config = config

    def complete(self, instructions, conversation, tools, model, max_tokens):
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY is missing from the environment. Do not enter it in chat.")
        body = {"model": model, "instructions": instructions, "input": conversation,
                "max_output_tokens": max_tokens, "store": False,
                "include": ["reasoning.encrypted_content"]}
        if tools:
            body.update(tools=tools, parallel_tool_calls=False)
        else:
            body["tools"] = []
        data = fetch_json("https://api.openai.com/v1/responses", payload=body,
                          headers={"Authorization": "Bearer " + key}, timeout=self.config.timeout_seconds)
        if data.get("error") or data.get("status") in {"failed", "cancelled"}:
            raise TransportError("The provider could not complete the response")
        output = data.get("output", [])
        texts, calls = [], []
        for item in output:
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        texts.append(part.get("text", ""))
                    elif part.get("type") == "refusal":
                        texts.append(part.get("refusal", ""))
            elif item.get("type") == "function_call":
                calls.append({"id": item.get("call_id", ""), "name": item.get("name", ""), "arguments": item.get("arguments", "{}")})
        usage = data.get("usage", {})
        return Completion("\n".join(texts), calls, output,
                          {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                           "cached_input_tokens": usage.get("input_tokens_details", {}).get("cached_tokens", 0)},
                          data.get("status") == "incomplete")

    @staticmethod
    def tool_result(call, result):
        return {"type": "function_call_output", "call_id": call["id"], "output": json.dumps(result, ensure_ascii=False)}


class OllamaProvider:
    _slot = threading.Lock()

    def __init__(self, config):
        self.config = config

    def complete(self, instructions, conversation, tools, model, max_tokens):
        if not self._slot.acquire(blocking=False):
            raise ValueError("A local query is running; wait for it to finish")
        try:
            return self._complete(instructions, conversation, tools, model, max_tokens)
        finally:
            self._slot.release()

    def _complete(self, instructions, conversation, tools, model, max_tokens):
        from .local_runtime import verify_runtime, inference_options
        if model != self.config.model:
            raise ValueError("Loading a second model outside the selected profile is not allowed")
        verify_runtime(self.config)
        options = inference_options(self.config)
        options["num_predict"] = min(max_tokens, self.config.max_output_tokens)
        body = {"model": model, "messages": [{"role": "system", "content": instructions}] + conversation,
                "stream": False, "options": options, "keep_alive": "2m", "think": False}
        if tools:
            body["tools"] = [{"type": "function", "function": {k: v for k, v in t.items() if k not in {"type", "strict"}}} for t in tools]
        data = fetch_json(self.config.ollama_url.rstrip("/") + "/api/chat", payload=body, timeout=self.config.timeout_seconds)
        if data.get("error"):
            raise TransportError("Ollama could not complete the response; check the installed model")
        if data.get("model") and data["model"] != model:
            raise TransportError("The server returned a model outside the selected profile")
        message = data.get("message", {})
        calls = [{"id": str(i), "name": c.get("function", {}).get("name", ""),
                  "arguments": c.get("function", {}).get("arguments", {})} for i, c in enumerate(message.get("tool_calls", []))]
        # Retain native thinking only in transient provider context, never display or persist it.
        return Completion(message.get("content", ""), calls, [message],
                          {"input_tokens": data.get("prompt_eval_count", 0), "output_tokens": data.get("eval_count", 0),
                           "cached_input_tokens": data.get("prompt_eval_cached_count", 0)}, data.get("done_reason") == "length")

    @staticmethod
    def tool_result(call, result):
        return {"role": "tool", "tool_name": call["name"], "content": json.dumps(result, ensure_ascii=False)}


class NativeProvider(OllamaProvider):
    def _complete(self, instructions, conversation, tools, model, max_tokens):
        from .native_runtime import verify_native
        runtime, url = verify_native(self.config)
        if model != self.config.model:
            raise ValueError("A second model is not allowed")
        body = {"model": model, "messages": [{"role":"system", "content":instructions}] + conversation,
                "stream":False, "max_tokens":min(max_tokens,self.config.max_output_tokens),
                "temperature":0.2, "chat_template_kwargs":{"enable_thinking":False}, "cache_prompt":False}
        if tools:
            body["tools"] = [{"type":"function", "function":{k:v for k,v in t.items() if k not in {"type","strict"}}} for t in tools]
            body["parallel_tool_calls"] = False
        try:
            data = fetch_json(url+'/v1/chat/completions', payload=body,
                              headers={"Authorization":"Bearer "+runtime.key}, timeout=self.config.timeout_seconds)
        except TransportError as exc:
            if "time limit" in str(exc):
                raise TransportError("The model running on this computer did not finish in time. "
                    "Start a New chat, select Chat, and try a short question. Use Fast performance "
                    "in setup and close other apps. This is a local response timeout, not an Internet search failure.") from None
            raise TransportError("Local model request failed: " + str(exc)) from None
        choices = data.get('choices', [])
        if not choices: raise TransportError('Native model returned no choices')
        item = choices[0]; message = item.get('message', {})
        calls = [{"id":c.get('id',str(i)),"name":c.get('function',{}).get('name',''),
                  "arguments":c.get('function',{}).get('arguments','{}')} for i,c in enumerate(message.get('tool_calls') or [])]
        carry = {"role":"assistant", "content":message.get('content') or ''}
        if message.get('tool_calls'): carry['tool_calls']=message['tool_calls']
        usage = data.get('usage',{})
        return Completion(message.get('content') or '', calls, [carry],
                          {"input_tokens":usage.get('prompt_tokens',0),"output_tokens":usage.get('completion_tokens',0),"cached_input_tokens":0},
                          item.get('finish_reason') == 'length')

    @staticmethod
    def tool_result(call, result):
        return {"role":"tool", "tool_call_id":call['id'], "content":json.dumps(result,ensure_ascii=False)}


def provider_for(config):
    if config.provider == "openai":
        return OpenAIProvider(config)
    if config.provider == "native":
        return NativeProvider(config)
    if config.provider == "ollama":
        return OllamaProvider(config)
    return None
