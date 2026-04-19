import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
OLLAMA_GENERATE_URL = os.getenv("OLLAMA_GENERATE_URL", "http://localhost:11434/api/generate")
# Change 'ministral-3:8b' to match the model you're using, shown by: ollama list
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ministral-3:8b")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8080/search")

# ANSI colors for a normal dark terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"

def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"

print(
    f"{color('[Fuqaz]', GREEN)} Using {color('Ollama', CYAN)} model "
    f"{color(OLLAMA_MODEL, MAGENTA)}"
)
print(
    f"{color('[Fuqaz]', GREEN)} Using {color('SearXNG', BLUE)} endpoint "
    f"{color(SEARXNG_URL, DIM)}"
)

# Conservative chat settings for ministral-3, experiment/tweak as you please
TEXT_SETTINGS = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_predict": 512,
}

VISION_SETTINGS = {
    "temperature": 0.5,
    "top_p": 0.95,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_predict": 512,
}


def raise_for_status_with_body(response: requests.Response, context: str):
    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise RuntimeError(
            f"{context} failed with status {response.status_code}: {response.text}"
        )


def search_searxng(query: str, source_meta: dict | None = None) -> str:
    query = (query or "").strip()
    if not query:
        return "Search error: empty query."

    source_meta = source_meta or {}
    user_label = source_meta.get("user", "unknown-user")
    location_label = source_meta.get("location", "unknown-location")

    print(
        f"{color('[SearXNG]', BLUE)} "
        f"{color(user_label, CYAN)} in {color(location_label, YELLOW)} "
        f"{color('->', DIM)} {query}"
    )

    r = requests.get(
        SEARXNG_URL,
        params={
            "q": query,
            "format": "json",
        },
        timeout=15,
    )
    raise_for_status_with_body(r, "SearXNG search")

    data = r.json()
    results = data.get("results", [])[:5]

    if not results:
        return f'No search results found for query: "{query}"'

    lines = [f'Search results for: "{query}"']
    for i, item in enumerate(results, 1):
        title = (item.get("title") or "Untitled").strip()
        url = (item.get("url") or "").strip()
        snippet = (item.get("content") or "").strip()

        if len(snippet) > 300:
            snippet = snippet[:297] + "..."

        lines.append(
            f"{i}. {title}\n"
            f"URL: {url}\n"
            f"Snippet: {snippet}"
        )

    return "\n\n".join(lines)


def _build_chat_messages_from_prompt(prompt: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": prompt,
        }
    ]


def _extract_text_from_chat_response(data: dict) -> str:
    message = data.get("message", {}) or {}
    content = (message.get("content") or "").strip()

    if content:
        return content

    return f"No response came back from the local model. Raw keys: {list(data.keys())}"


def ask_local_model(prompt: str, source_meta: dict | None = None) -> str:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_searxng",
                "description": (
                    "Search the web using the local SearXNG instance. "
                    "Use this only when the user asks for current events, recent news, live information, "
                    "or something that clearly needs fresh external verification."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A concise web search query."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    messages = _build_chat_messages_from_prompt(prompt)

    first_payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "1m",
        "options": TEXT_SETTINGS,
        "tools": tools,
    }

    r = requests.post(OLLAMA_CHAT_URL, json=first_payload, timeout=120)
    raise_for_status_with_body(r, "Ollama /api/chat first call")
    first_data = r.json()

    message = first_data.get("message", {}) or {}
    tool_calls = message.get("tool_calls") or []

    if not tool_calls:
        return _extract_text_from_chat_response(first_data)

    messages.append(message)

    tool_call_count = 0
    seen_queries = set()

    for tool_call in tool_calls:
        if tool_call_count >= 1:
            break

        fn = (tool_call.get("function") or {})
        name = fn.get("name")
        arguments = fn.get("arguments") or {}

        if name != "search_searxng":
            continue

        query = (arguments.get("query") or "").strip()

        if not query:
            tool_result = "Search error: empty query."
        elif query.lower() in seen_queries:
            tool_result = f'Search skipped: query "{query}" was already used this turn.'
        else:
            seen_queries.add(query.lower())
            try:
                tool_result = search_searxng(query, source_meta=source_meta)
            except Exception as e:
                tool_result = f"Search error for query '{query}': {e}"

        messages.append(
            {
                "role": "tool",
                "tool_name": "search_searxng",
                "content": tool_result,
            }
        )
        tool_call_count += 1

    second_payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "1m",
        "options": TEXT_SETTINGS,
    }

    r = requests.post(OLLAMA_CHAT_URL, json=second_payload, timeout=120)
    raise_for_status_with_body(r, "Ollama /api/chat second call")
    second_data = r.json()

    return _extract_text_from_chat_response(second_data)


def ask_local_model_with_images(prompt: str, image_bytes_list: list[bytes]) -> str:
    encoded_images = [base64.b64encode(img).decode("utf-8") for img in image_bytes_list]

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": encoded_images,
        "stream": False,
        "keep_alive": "1m",
        "options": VISION_SETTINGS,
    }

    r = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=180)
    raise_for_status_with_body(r, "Ollama /api/generate vision call")
    data = r.json()

    response_text = data.get("response", "").strip()
    if response_text:
        return response_text

    return f"No response came back from the local vision model. Raw keys: {list(data.keys())}"