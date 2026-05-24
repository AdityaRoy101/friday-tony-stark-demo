"""
Reusable prompt templates registered with the MCP server.
"""


def register(mcp):

    @mcp.prompt()
    def summarize(text: str) -> str:
        """Prompt to summarize a block of text."""
        return (
            "Summarize this for a spoken assistant response. Keep the core facts, "
            "remove filler, and use plain language.\n\n"
            f"{text}"
        )

    @mcp.prompt()
    def explain_code(code: str, language: str = "Python") -> str:
        """Prompt to explain a block of code."""
        return (
            f"Explain this {language} code in plain English. Start with what it does, "
            "then mention the important moving parts and any obvious risk.\n\n"
            f"```{language.lower()}\n{code}\n```"
        )

    @mcp.prompt()
    def voice_clarify(transcript: str) -> str:
        """Prompt to recover gracefully from a likely bad speech transcript."""
        return (
            "The speech transcript may be inaccurate. Respond as Friday in one "
            "short sentence: say what you caught and ask for the missing part.\n\n"
            f"Transcript: {transcript}"
        )

    @mcp.prompt()
    def brief_research(topic: str) -> str:
        """Prompt for a concise source-backed research response."""
        return (
            "Research this topic using available tools if it may be current. "
            "Give the shortest useful answer, mention uncertainty, and include "
            f"sources when available.\n\nTopic: {topic}"
        )
