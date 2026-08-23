"""Web search for OpenCode, in tiers: Z.AI -> Exa -> OpenRouter. (D3)

Why tiers
---------
The three back-ends are not equivalent, and the order is about money and shape,
not quality:

  1. zai         Z.AI web_search_prime, on the coding-plan subscription. Free at
                 the point of use, and it returns raw results (title, url,
                 snippet) -- which is what a model wants.
  2. exa         api.exa.ai directly. Also raw, also cheap, and measured here at
                 0.22 s. Needs EXA_API_KEY; when that is absent this tier is
                 SKIPPED and says so, rather than pretending to have tried.
  3. openrouter  `:online` with the web plugin. Last on purpose: it queries the
                 same Exa index and then bills a model to write a summary on top
                 -- 16.4 s against 0.22 s, measured. `engine` is pinned to "exa"
                 because the "native" engine returned 404 and an empty body here.
                 This tier is the only one that costs money.

What this file replaces
-----------------------
`zai-web-search.py`, a stdio<->HTTP bridge that proxied every JSON-RPC message
straight to Z.AI. That had one structural problem beyond having no fallback:
because `initialize` and `tools/list` were proxied too, a Z.AI outage did not
degrade search, it removed the search TOOL. This server answers the handshake
itself, so the tool always exists and only its backing tier changes.

It keeps the one hard-won fact from that bridge: Z.AI answers the
`notifications/initialized` ack with HTTP 200, an empty body and no
Content-Type, which trips OpenCode's `content-type.startsWith("text/
event-stream")` guard. Speaking stdio to OpenCode and HTTP to Z.AI is what
avoids it, and that is still the shape here.

Honesty in the payload
----------------------
Every answer names the tier that served it and lists the tiers that were skipped
with the reason. When the paid tier is the one that answered, the answer says so
in as many words, so a reader can tell a free result from a billed one without
reading a log.
"""
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ZAI_MCP_URL = os.environ.get("ZAI_MCP_URL", "https://api.z.ai/api/mcp/web_search_prime/mcp")
EXA_URL = "https://api.exa.ai/search"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Cheap, large-context, and the same model the factory already runs. The web
# plugin does the searching; the model only formats, so paying for a big one
# here would be paying for nothing.
OPENROUTER_MODEL = "deepseek/deepseek-v4-flash-0731"

AUTH_JSON = pathlib.Path.home() / ".local" / "share" / "opencode" / "auth.json"
REPO = pathlib.Path(__file__).resolve().parents[2]
DOTENV = REPO / ".env"
JOURNAL = REPO / ".opencode" / "websearch.jsonl"

# How an MCP server spells "the tool failed" in a text block.
MCP_ERROR = re.compile(r"^MCP error\b|^\s*\{\s*\"error\"\s*:", re.I)

DEFAULT_MAX_RESULTS = 8
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 90


def log(message):
    sys.stderr.write("[web-search] %s\n" % message)
    sys.stderr.flush()


def dotenv_key(name):
    """Read one key from the repo .env. Never logged, never echoed."""
    try:
        for line in DOTENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = re.match(r"\s*%s\s*=\s*(.+)" % re.escape(name), line)
            if match:
                return match.group(1).strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def resolve_key(env_name, auth_section=None):
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    if auth_section:
        try:
            auth = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
            value = (auth.get(auth_section) or {}).get("key", "").strip()
            if value:
                return value
        except (OSError, ValueError, AttributeError):
            pass
    return dotenv_key(env_name)


def http_json(url, payload, headers, timeout=READ_TIMEOUT):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    response = urllib.request.urlopen(request, timeout=timeout)
    return response, response.read().decode("utf-8", "replace")


def parse_sse(raw, content_type):
    """Z.AI answers tools/call as SSE; the same endpoint answers plain JSON for
    other methods. Handle both rather than assuming one."""
    messages = []
    if "text/event-stream" in (content_type or "").lower():
        for block in raw.split("\n\n"):
            lines = [ln[5:].strip() for ln in block.splitlines() if ln.startswith("data:")]
            if lines:
                try:
                    messages.append(json.loads("\n".join(lines)))
                except ValueError:
                    continue
        return messages
    if raw.strip():
        try:
            messages.append(json.loads(raw))
        except ValueError:
            pass
    return messages


# ---------------------------------------------------------------------------
# Tier 1 — Z.AI web_search_prime (subscription)
# ---------------------------------------------------------------------------
class ZaiTier:
    name = "zai"
    cost = "free (coding-plan subscription)"

    def __init__(self):
        self.session = None
        self.key = resolve_key("ZAI_API_KEY", "zai-coding-plan")

    def unavailable(self):
        return None if self.key else "no Z.AI coding-plan key (env ZAI_API_KEY or auth.json)"

    def _rpc(self, payload, expect_reply=True):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + self.key,
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        response, raw = http_json(ZAI_MCP_URL, payload, headers)
        new_session = response.headers.get("Mcp-Session-Id")
        if new_session:
            self.session = new_session
        if not expect_reply:
            return []
        return parse_sse(raw, response.headers.get("Content-Type"))

    def _handshake(self):
        if self.session:
            return
        self._rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "opencode-web-search", "version": "1"}}})
        self._rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_reply=False)

    def search(self, query, max_results, recency=None):
        self._handshake()
        arguments = {"search_query": query[:70] if len(query) > 70 else query}
        if recency:
            arguments["search_recency_filter"] = recency
        replies = self._rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                             "params": {"name": "web_search_prime", "arguments": arguments}})
        results = []
        for message in replies:
            result = message.get("result") or {}
            if message.get("error"):
                raise RuntimeError(str(message["error"])[:200])
            # An MCP server reports a tool failure INSIDE a successful JSON-RPC
            # reply: result.isError, with the message sitting in a normal text
            # block. Read only the envelope and the failure looks like a result.
            # Measured 2026-08-01: the coding-plan weekly cap came back as the
            # text block 'MCP error -429: {"error":{"code":"1310",...}}', and an
            # earlier version of this file rendered it as search result #1 --
            # so the cascade never stepped down and the agent was handed an
            # error message dressed as material. Treat it as a tier failure.
            if result.get("isError"):
                blocks = result.get("content") or [{}]
                raise RuntimeError(str(blocks[0].get("text", "tool reported isError"))[:200])
            for block in result.get("content", []):
                text = block.get("text") if isinstance(block, dict) else None
                if not text:
                    continue
                if MCP_ERROR.match(text.strip()):
                    raise RuntimeError(text.strip()[:200])
                try:
                    parsed = json.loads(text)
                except ValueError:
                    # Unparseable text with no URL in it is not a search result.
                    # Accepting it is how an error becomes a citation.
                    if "http" not in text:
                        raise RuntimeError("tier returned text with no URL: %s" % text[:160])
                    results.append({"title": "", "url": "", "snippet": text})
                    continue
                for item in (parsed if isinstance(parsed, list) else [parsed]):
                    if not isinstance(item, dict):
                        continue
                    results.append({
                        "title": item.get("title") or item.get("name") or "",
                        "url": item.get("url") or item.get("link") or "",
                        "snippet": (item.get("content") or item.get("summary")
                                    or item.get("snippet") or "")[:600],
                    })
        return results[:max_results]


# ---------------------------------------------------------------------------
# Tier 2 — Exa direct
# ---------------------------------------------------------------------------
class ExaTier:
    name = "exa"
    cost = "free tier / cheap, raw results"

    def __init__(self):
        self.key = resolve_key("EXA_API_KEY")

    def unavailable(self):
        if self.key:
            return None
        # Stated as an absent capability, not a failure: OpenCode's own
        # `websearch` tool also reaches Exa and needs no key, so an agent that
        # sees this line has somewhere free to go.
        return ("no EXA_API_KEY (add one to .env to enable this tier; the built-in "
                "`websearch` tool also reaches Exa without a key)")

    def search(self, query, max_results, recency=None):
        headers = {"Content-Type": "application/json", "x-api-key": self.key}
        payload = {"query": query, "numResults": max_results,
                   "contents": {"text": {"maxCharacters": 600}}}
        _response, raw = http_json(EXA_URL, payload, headers)
        parsed = json.loads(raw)
        results = []
        for item in parsed.get("results", []):
            results.append({
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": (item.get("text") or item.get("summary") or "")[:600],
            })
        return results[:max_results]


# ---------------------------------------------------------------------------
# Tier 3 — OpenRouter :online (paid, last)
# ---------------------------------------------------------------------------
class OpenRouterTier:
    name = "openrouter"
    cost = "PAID — model tokens plus the web plugin"

    def __init__(self):
        self.key = resolve_key("OPENROUTER_API_KEY", "openrouter")

    def unavailable(self):
        return None if self.key else "no OPENROUTER_API_KEY"

    def search(self, query, max_results, recency=None):
        headers = {"Content-Type": "application/json",
                   "Authorization": "Bearer " + self.key}
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": query}],
            # engine pinned to "exa": the "native" engine answered 404 with an
            # empty body when this was measured, which reads as a silent search.
            "plugins": [{"id": "web", "engine": "exa", "max_results": max_results}],
            "max_tokens": 1200,
        }
        _response, raw = http_json(OPENROUTER_URL, payload, headers)
        parsed = json.loads(raw)
        message = (parsed.get("choices") or [{}])[0].get("message") or {}
        results = []
        # Prefer the citations: they are the raw material. The prose is the part
        # we are paying extra for and the part a model needs least.
        for annotation in message.get("annotations") or []:
            citation = annotation.get("url_citation") or {}
            if citation.get("url"):
                results.append({
                    "title": citation.get("title") or "",
                    "url": citation.get("url"),
                    "snippet": (citation.get("content") or "")[:600],
                })
        if not results:
            content = message.get("content") or ""
            if content.strip():
                results.append({"title": "(synthesis, no citations returned)",
                                "url": "", "snippet": content[:2000]})
        return results[:max_results]


TIERS = [ZaiTier, ExaTier, OpenRouterTier]


def journal(record):
    try:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with open(JOURNAL, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        pass  # a journal that cannot be written must not break the search


def run_search(query, max_results, recency=None):
    """Walk the tiers in order; return (text, meta). Never raises."""
    skipped = []
    started_all = time.time()
    for tier_class in TIERS:
        tier = tier_class()
        reason = tier.unavailable()
        if reason:
            skipped.append("%s: %s" % (tier.name, reason))
            continue
        started = time.time()
        try:
            results = tier.search(query, max_results, recency)
        except Exception as exc:  # noqa: BLE001 - any failure means: next tier
            detail = "%s: %s" % (type(exc).__name__, str(exc)[:120])
            skipped.append("%s: failed (%s)" % (tier.name, detail))
            log("tier %s failed: %s" % (tier.name, detail))
            continue
        elapsed = time.time() - started
        if not results:
            skipped.append("%s: returned no results" % tier.name)
            continue
        journal({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "query": query[:200], "tier": tier.name, "results": len(results),
                 "duration_s": round(elapsed, 2), "skipped": skipped})
        return render(query, tier, results, skipped, elapsed), {
            "tier": tier.name, "results": len(results)}

    journal({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "query": query[:200], "tier": None, "results": 0,
             "duration_s": round(time.time() - started_all, 2), "skipped": skipped})
    return ("No tier could answer %r.\n\nTiers tried, in order:\n%s\n\n"
            "This is an absent result, not an empty one: do not report it as "
            "'nothing was found on the web'." % (query, "\n".join("  - " + s for s in skipped))), {
        "tier": None, "results": 0}


def render(query, tier, results, skipped, elapsed):
    lines = ["Query: %s" % query,
             "Served by tier: %s (%s) in %.2fs" % (tier.name, tier.cost, elapsed)]
    if tier.name == "openrouter":
        lines.append("NOTE: this is the PAID tier. The free tiers above it were "
                     "unavailable — see the list below. For follow-up questions "
                     "prefer the built-in `websearch` tool, which is free.")
    if skipped:
        lines.append("Tiers skipped: " + "; ".join(skipped))
    lines.append("")
    for i, item in enumerate(results, 1):
        lines.append("%d. %s" % (i, item["title"] or "(untitled)"))
        if item["url"]:
            lines.append("   %s" % item["url"])
        if item["snippet"]:
            lines.append("   %s" % item["snippet"].replace("\n", " ")[:600])
    return "\n".join(lines)


TOOL = {
    "name": "web_search",
    "description": (
        "Search the web. Tries Z.AI (subscription, free), then Exa, then "
        "OpenRouter's paid web plugin, and reports which tier answered. Returns "
        "raw results (title, url, snippet), not a synthesis."),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "the search query; keep it under 70 characters for tier 1"},
            "max_results": {"type": "integer", "description": "how many results to return (default 8)"},
            "recency": {"type": "string", "description": "optional recency filter, e.g. oneWeek, oneMonth, oneYear"},
        },
        "required": ["query"],
    },
}


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def handle(message):
    """Return a JSON-RPC reply, or None for a notification."""
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "web-search-tiered", "version": "1.0"}}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": [TOOL]}}
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != TOOL["name"]:
            return {"jsonrpc": "2.0", "id": request_id, "error": {
                "code": -32601, "message": "unknown tool %r" % params.get("name")}}
        arguments = params.get("arguments") or {}
        query = (arguments.get("query") or "").strip()
        if not query:
            return {"jsonrpc": "2.0", "id": request_id, "error": {
                "code": -32602, "message": "query is required"}}
        try:
            max_results = int(arguments.get("max_results") or DEFAULT_MAX_RESULTS)
        except (TypeError, ValueError):
            max_results = DEFAULT_MAX_RESULTS
        text, meta = run_search(query, max(1, min(max_results, 25)),
                                arguments.get("recency"))
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": text}],
            "isError": meta["tier"] is None}}
    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "error": {
        "code": -32601, "message": "method %r not supported" % method}}


def main():
    log("up — tiers: " + " -> ".join(t.name for t in TIERS))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError as exc:
            log("dropping non-JSON stdin line: %s" % exc)
            continue
        try:
            reply = handle(message)
        except Exception as exc:  # noqa: BLE001 - never die on one bad request
            log("handler error: %s: %s" % (type(exc).__name__, exc))
            reply = {"jsonrpc": "2.0", "id": message.get("id"), "error": {
                "code": -32603, "message": "%s: %s" % (type(exc).__name__, str(exc)[:200])}}
        if reply is not None:
            emit(reply)
    log("stdin closed, exiting")


if __name__ == "__main__":
    main()
