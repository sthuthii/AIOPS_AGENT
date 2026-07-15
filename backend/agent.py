"""
The agent: takes a natural-language request, lets Gemini decide which
GCP operations are needed (via function calling), executes those
operations against the signed-in user's own project, and returns a
formatted summary in the style of the assignment's example output.
"""
from concurrent.futures import ThreadPoolExecutor
from inspect import signature

from google import genai
from google.genai import types

import time
import random
import re

try:
    from .config import settings
    from .tool_loader import load_tools
    from .tool_specs import load_tool_specs
except Exception:
    from config import settings
    from tool_loader import load_tools
    from tool_specs import load_tool_specs

_client = genai.Client(api_key=settings.GEMINI_API_KEY)
TOOL_REGISTRY = load_tools()
_TOOL_SPECS = load_tool_specs()


_GEMINI_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(name=spec["name"], description=spec["description"], parameters=spec["parameters"])
        for spec in _TOOL_SPECS
    ]
)

# Tool dispatch is blocking network I/O (GCP SDK calls), so when Gemini asks
# for several independent tools in one turn (e.g. a full infra summary calls
# compute + SQL + GKE + logging), we run them concurrently instead of one
# after another. This is the single biggest latency win for multi-tool
# requests -- four sequential ~1s GCP calls become one ~1s batch.
_TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=6)


def _thinking_config_for(model_name: str):
    """
    Ops-report generation doesn't need deep multi-step reasoning -- it needs
    fast, correct tool selection. Turning thinking down/off is the other big
    latency win, especially on 3.x models where it's on by default.
    """
    if "gemini-3" in model_name:
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
    if "gemini-2.5" in model_name:
        return types.ThinkingConfig(thinking_budget=0)
    return None  # older models (e.g. 2.0 Flash) don't support thinking config

SYSTEM_PROMPT = """\
You are an AIOps assistant that manages a user's Google Cloud project on their behalf.
You have tools to inspect Compute Engine VMs, GKE clusters, Cloud SQL instances,
CPU utilization metrics, and recent log-based alerts, and to restart a VM.

Always use tools to get real data before answering -- never invent resource
names, statuses, or metrics.

Format your final answer like a concise ops report, similar to this shape
(omit sections that aren't relevant to the request):

Infrastructure Summary
Project: <project>

Resources:
- Compute Engine: <instance> (<status>)
- Cloud SQL: <instance> (<state>)
- GKE: <cluster> (<status>)

Alerts:
- <finding, e.g. high CPU or a warning log>

Recommendation:
- <a short, practical suggestion>

Action Executed:
- <only if the user asked you to perform a write action, e.g. restart>

Operation Status:
- <only if an action was executed>

Keep it tight -- no filler, no restating the user's question back to them.
If a tool call fails (e.g. permission denied), surface that plainly rather
than pretending the resource doesn't exist.

When a request needs more than one independent piece of data (e.g. a full
infrastructure summary needs Compute + Cloud SQL + GKE + alerts), request
ALL of those tools in the same turn rather than one at a time -- they don't
depend on each other's results, and calling them together is faster.
"""



def _dispatch(tool_name: str, tool_input: dict, credentials, project_id: str):
    tool_meta = TOOL_REGISTRY.get(tool_name)
    if not tool_meta:
        return {"error": f"Unknown tool: {tool_name}"}

    tool_func = tool_meta["func"]
    sig = signature(tool_func)
    kwargs = {}
    if "credentials" in sig.parameters:
        kwargs["credentials"] = credentials
    if "project_id" in sig.parameters:
        kwargs["project_id"] = project_id
    for key, value in tool_input.items():
        if key in sig.parameters:
            kwargs[key] = value
    return tool_func(**kwargs)


MAX_TOOL_ITERATIONS = 6


def handle_message(user_message: str, credentials, project_id: str) -> str:
    if not project_id:
        return "No GCP project selected yet -- please pick a project first."

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"[Active project: {project_id}]\n{user_message}")],
        )
    ]

    # The GenerateContentConfig may change per-model (thinking config differs),
    # so we build and try multiple models with retries and fallbacks to handle
    # transient errors, NOT_FOUND, and quota (429) responses.
    logger = __import__("logging").getLogger("aiops-agent")

    for _ in range(MAX_TOOL_ITERATIONS):
        fallbacks = [settings.GEMINI_MODEL, "gemini-2.5-flash", "gemini-flash-latest", "gemini-3.1-flash-lite"]
        # Deduplicate preserving order and remove falsy entries
        models_to_try = []
        for m in fallbacks:
            if m and m not in models_to_try:
                models_to_try.append(m)

        response = None
        last_exc = None
        for model_name in models_to_try:
            # up to 3 attempts per model with exponential backoff + jitter
            for attempt in range(3):
                try:
                    logger.info("Calling generative model: %s (attempt %d)", model_name, attempt + 1)
                    config = types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=[_GEMINI_TOOL],
                        max_output_tokens=1500,
                        thinking_config=_thinking_config_for(model_name),
                    )
                    response = _client.models.generate_content(model=model_name, contents=contents, config=config)
                    break
                except Exception as e:
                    last_exc = e
                    msg = str(e).lower()
                    # Handle quota/resource exhausted (HTTP 429) specially.
                    if "429" in msg or "resource_exhausted" in msg or "quota" in msg or "exceeded" in msg:
                        m = re.search(r"please retry in ([0-9.]+)s", str(e), flags=re.IGNORECASE)
                        retry_seconds = float(m.group(1)) if m else None
                        if retry_seconds is not None and retry_seconds <= 10:
                            logger.warning(
                                "Quota error for model %s: %s; sleeping %.1fs before retry",
                                model_name,
                                e,
                                retry_seconds,
                            )
                            time.sleep(retry_seconds)
                            continue
                        logger.warning("Quota/resource exhausted for model %s: %s; skipping to next model", model_name, e)
                        break
                    # Model not found -> try next model
                    if "not found" in msg or "not_found" in msg:
                        logger.warning("Model %s not found: %s", model_name, e)
                        break
                    # Transient/unavailable -> retry with backoff
                    if "503" in msg or "unavailable" in msg or "high demand" in msg:
                        sleep = (2 ** attempt) + random.random()
                        logger.warning("Transient error from model %s: %s; retrying in %.1fs", model_name, e, sleep)
                        time.sleep(sleep)
                        continue
                    # Other errors -> raise immediately
                    raise
            if response is not None:
                break
        if response is None:
            # Re-raise the last exception for the caller to handle/log.
            raise last_exc

        candidate = response.candidates[0]
        parts = candidate.content.parts or []
        function_calls = [p.function_call for p in parts if p.function_call is not None]

        if not function_calls:
            text = (response.text or "").strip()
            return text or "No response generated."

        # Keep the model's own turn (including its function_call parts) in history.
        contents.append(candidate.content)

        # Run every tool call in this turn concurrently -- they're independent
        # blocking GCP API calls, so this collapses N sequential round trips
        # into roughly one.
        futures = [
            _TOOL_EXECUTOR.submit(_dispatch, fc.name, dict(fc.args or {}), credentials, project_id)
            for fc in function_calls
        ]
        result_parts = [
            types.Part.from_function_response(name=fc.name, response={"result": future.result()})
            for fc, future in zip(function_calls, futures)
        ]
        contents.append(types.Content(role="user", parts=result_parts))

    return "The agent took too many steps to complete this request -- please try a more specific prompt."