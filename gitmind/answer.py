"""
Answer assembler — Week 3.

Takes retrieved context (structural results / episode chunks / decision arc)
and generates a final natural-language answer via GPT-4o mini.

TODO (Week 3):
  [ ] Implement assemble_context() to build the LLM prompt from retrieved results
  [ ] Implement generate_answer() to call the OpenAI API
  [ ] Implement format_answer() to produce the rich CLI output
  [ ] Track token usage and log it
"""

from __future__ import annotations
from gitmind.models import QueryResult


async def answer(query: str, repo_path: str) -> QueryResult:
    """
    Full pipeline: route query → retrieve context → generate answer.

    This is the top-level function called by the CLI `ask` command.

    TODO (Week 3): implement this.
    """
    raise NotImplementedError("Week 3")
