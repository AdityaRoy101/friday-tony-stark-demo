"""
Utility tools — text processing, formatting, calculations, etc.
"""

import json
import ast
import operator
import re


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_math_node(node):
    if isinstance(node, ast.Expression):
        return _eval_math_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _eval_math_node(node.left)
        right = _eval_math_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise ValueError("Exponent is too large.")
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_eval_math_node(node.operand))
    raise ValueError("Only basic arithmetic is supported.")


def register(mcp):

    @mcp.tool()
    def format_json(data: str) -> str:
        """Pretty-print a JSON string."""
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"

    @mcp.tool()
    def word_count(text: str) -> dict:
        """Count words, characters, and lines in a block of text."""
        lines = text.splitlines()
        words = text.split()
        return {
            "characters": len(text),
            "words": len(words),
            "lines": len(lines),
        }

    @mcp.tool()
    def calculate(expression: str) -> str:
        """
        Safely calculate a basic arithmetic expression.
        Supports +, -, *, /, //, %, powers, and parentheses.
        """
        try:
            tree = ast.parse(expression, mode="eval")
            result = _eval_math_node(tree)
            return f"{expression} = {result}"
        except Exception as exc:
            return f"I couldn't calculate that: {exc}"

    @mcp.tool()
    def compact_text(text: str, max_words: int = 60) -> str:
        """Condense text to a simple first-pass extract for short spoken responses."""
        words = text.split()
        if max_words < 5:
            max_words = 5
        if len(words) <= max_words:
            return text.strip()
        return " ".join(words[:max_words]).strip() + "..."

    @mcp.tool()
    def list_capabilities() -> dict:
        """Return the current Friday capability map for self-description."""
        return {
            "voice": ["real-time conversation", "clarification on bad transcripts", "interruptions enabled"],
            "web": ["world news", "finance news", "web search", "URL fetch", "safe URL opening"],
            "local": ["current time", "system info", "system snapshot"],
            "utilities": ["calculator", "JSON formatting", "word count", "text compaction"],
            "memory": ["remember explicit facts", "recall visible memory", "forget memory by key"],
            "safety": ["confirm destructive actions", "do not store secrets"],
        }

    @mcp.tool()
    def route_intent(user_text: str) -> dict:
        """
        Classify a user request into Friday's capability routes.
        Use this when the request is ambiguous or might require a tool.
        """
        text = user_text.lower()
        routes = []
        if re.search(r"\b(news|headline|world|brief me|catch me up|what did i miss)\b", text):
            routes.append("world_news")
        if re.search(r"\b(finance|market|stock|economy|nasdaq|dow|s&p|nifty|sensex)\b", text):
            routes.append("finance_news")
        if re.search(r"\b(search|look up|latest|current|today|who is|what is happening)\b", text):
            routes.append("web_search")
        if re.search(r"\b(remember|save this|keep note)\b", text):
            routes.append("memory_write")
        if re.search(r"\b(what do you remember|recall|forget)\b", text):
            routes.append("memory_read_or_delete")
        if re.search(r"\b(time|date|computer|system|disk|cpu|machine)\b", text):
            routes.append("local_system")
        if re.search(r"\b(calculate|plus|minus|times|divided|percent|%|\d+\s*[-+*/])\b", text):
            routes.append("calculator")
        if re.search(r"\b(delete|remove files|send email|buy|purchase|payment|password|api key|token)\b", text):
            routes.append("confirm_before_action")
        if not routes:
            routes.append("llm_conversation")
        return {
            "routes": routes,
            "recommended_primary_route": routes[0],
            "requires_confirmation": "confirm_before_action" in routes,
        }
