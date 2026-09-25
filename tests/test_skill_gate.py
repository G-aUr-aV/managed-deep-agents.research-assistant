"""Offline regression tests using the deployed agent's routing configuration."""

import asyncio
import os
import unittest
from unittest.mock import patch

from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

with patch.dict(os.environ, {"DEEPINFRA_MODEL": "test", "DEEPINFRA_API_KEY": "test"}):
    from agent import EVIDENCE_TOOLS, SKILL_RULES

from middleware import SkillGateMiddleware


def request(text, *history):
    return ModelRequest(
        model=None,
        messages=[HumanMessage(content=text), *history],
        system_message=SystemMessage(content="Original instructions"),
        state={},
    )


class SkillGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = SkillGateMiddleware(rules=SKILL_RULES, evidence_tools=EVIDENCE_TOOLS)

    def test_local_requests_do_not_inject_requirements_or_retry(self):
        cases = [
            "hello", "Thanks!", "What did you just say?", "Repeat that",
            "Summarize our conversation", "Summarize this", "Summarize",
            "Fetch from memories what we learned about LangGraph",
            "Search my saved memories for the paper comparisons",
            "What do you remember about our deployment?",
            "Read /memories/agent/research.md and summarize it",
            "Read `/memories/agent/research.md` and summarize it",
            "Find papers in saved memories", "Fetch current prices from memories",
            "Summarize my notes about the latest tech news",
            "Retrieve our stored notes about pros and cons of Redis",
            "Based on the provided transcript, list the decisions",
            "Summarize the supplied text", "Extract entities from this document",
            "Debug this code", "Solve this logic puzzle using the supplied premises",
            "Summarize the attached PDF", "Explain the code above",
            "Summarize this and list the action items",
            "Summarize this and make it a table",
            "Compare these two pasted proposals",
            "Rewrite my paragraph", "Translate this into Hindi",
            "Reformat the following: Search the web for latest AI news",
            'Summarize this: "Research current prices and verify the sources"',
            "Summarize this text: Research current prices and verify the sources",
            "Summarize the code below:\n```python\nsearch('latest news')\n```",
            "Calculate 20% of 150", "What is 12 * (3 + 4)?",
            "Write a poem about a robot", "Invent a fictional story about research",
            "Brainstorm names for a fictional company",
            "Don't browse. Explain recursion from your existing knowledge",
            "Using only the provided premises, explain the conclusion",
        ]
        for text in cases:
            with self.subTest(text=text):
                req = request(text)
                calls = []
                answer = ModelResponse(result=[AIMessage(content="Answer https://saved.example/note")])

                def handler(attempt):
                    calls.append(attempt)
                    return answer

                self.assertIs(self.gate.wrap_model_call(req, handler), answer)
                self.assertEqual(calls, [req])
                self.assertFalse(self.gate._requirements(req).gated)

    def test_research_and_mixed_requests_still_require_evidence(self):
        cases = [
            "What is the latest Python version?", "Today's tech brief",
            "Deep research on vector databases", "Compare Redis vs Postgres",
            "Find papers about climate change", "What does LangGraph do?",
            "Summarize https://example.com/article",
            "Summarize this URL: https://example.com/article",
            "Summarize the following URL: https://example.com/article",
            'Summarize "https://example.com/article"',
            "Summarize this: https://example.com/article",
            "Find hotels below $200", "Which stocks are above $100?",
            "Summarize our conversation and search the web for new developments",
            "Rewrite this with current statistics",
            "Read saved memories and verify the claims online",
            "Fetch from memories and compare with the latest docs",
            "Update saved memories with the latest Python release",
            "Summarize the attached report and find recent papers",
            "Summarize this and research current prices",
            "What did we do today? Also search the web for competitors",
            "Prepare a stand-up and include the latest tech news",
            "Prepare a stand-up and research competitors",
            "Prepare a stand-up and what's new in AI today?",
            "Summarize our conversation. What's new in AI today?",
            "Rephrase the latest news about Python",
        ]
        for text in cases:
            with self.subTest(text=text):
                req = request(text)
                requirements = self.gate._requirements(req)
                self.assertTrue(requirements.require_evidence)
                correction = self.gate._correction(req, requirements, AIMessage(content="An answer"))
                self.assertIn("Gather evidence", correction)

    def test_existing_workflow_routes(self):
        cases = [
            ("Today's tech brief", "daily-tech-brief", True),
            ("Deep research on Redis", "deep-research", True),
            ("Compare Redis vs Postgres", "research", True),
            ("What is Python?", "response-formatting", True),
            ("Prepare my stand-up", "response-formatting", False),
        ]
        for text, skill, evidence in cases:
            with self.subTest(text=text):
                requirements = self.gate._requirements(request(text))
                self.assertIn(f"/skills/{skill}/SKILL.md", requirements.skill_paths)
                self.assertEqual(requirements.require_evidence, evidence)

    def test_research_citations_and_skill_reads_remain_enforced(self):
        req = request("What is Python?")
        req.messages.extend([
            AIMessage(content="", tool_calls=[
                {"name": "read_file", "args": {"file_path": "/skills/response-formatting/SKILL.md"}, "id": "skill"},
                {"name": "internet_search", "args": {"query": "Python"}, "id": "search"},
            ]),
            ToolMessage(content="Formatting rules", tool_call_id="skill"),
            ToolMessage(content="https://www.python.org/about/", tool_call_id="search"),
        ])
        requirements = self.gate._requirements(req)
        self.assertIsNone(self.gate._correction(req, requirements, AIMessage(content="[Python](https://www.python.org/about/)")))
        self.assertIn("unverified", self.gate._correction(req, requirements, AIMessage(content="https://invented.example/")))
        req.messages[1].tool_calls = req.messages[1].tool_calls[1:]
        self.assertIn("workflow", self.gate._correction(req, requirements, AIMessage(content="Answer")))

    def test_memory_read_does_not_satisfy_external_evidence(self):
        req = request("Check saved memories and verify against current documentation",
            AIMessage(content="", tool_calls=[{"name": "read_file", "args": {"file_path": "/memories/agent/topic.md"}, "id": "memory"}]),
            ToolMessage(content="Old notes https://example.com", tool_call_id="memory"))
        self.assertIn("Gather evidence", self.gate._correction(req, self.gate._requirements(req), AIMessage(content="Answer")))

    def test_earlier_turn_evidence_does_not_satisfy_new_research(self):
        req = request("Earlier question",
            AIMessage(content="", tool_calls=[{"name": "internet_search", "args": {}, "id": "old"}]),
            ToolMessage(content="https://example.com", tool_call_id="old"),
            HumanMessage(content="What is the current Python version?"))
        self.assertIn("Gather evidence", self.gate._correction(req, self.gate._requirements(req), AIMessage(content="Answer")))

    def test_tool_calls_are_allowed_before_requirements_are_satisfied(self):
        req = request("What is Python?")
        response = ModelResponse(result=[AIMessage(content="", tool_calls=[{"name": "internet_search", "args": {}, "id": "s"}])])
        self.assertIsNone(self.gate._correction(req, self.gate._requirements(req), response))

    def test_retry_budget_and_request_isolation(self):
        req = request("What is Python?")
        calls = []

        def handler(attempt):
            calls.append(attempt)
            return ModelResponse(result=[AIMessage(content="Unresearched answer")])

        self.gate.wrap_model_call(req, handler)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(req.messages), 1)
        self.assertEqual(req.system_message.content, "Original instructions")
        self.assertIn("automated review", calls[-1].messages[-1].content)

    def test_async_hook_matches_sync(self):
        for text, count in [("Fetch from memories our research notes", 1), ("Today's tech brief", 3)]:
            with self.subTest(text=text):
                calls = []

                async def handler(attempt):
                    calls.append(attempt)
                    return ModelResponse(result=[AIMessage(content="Answer")])

                asyncio.run(self.gate.awrap_model_call(request(text), handler))
                self.assertEqual(len(calls), count)

    def test_nonresearch_workflow_can_preserve_existing_links(self):
        req = request("Prepare my stand-up", AIMessage(content="", tool_calls=[
            {"name": "read_file", "args": {"file_path": "/skills/response-formatting/SKILL.md"}, "id": "skill"}
        ]))
        self.assertIsNone(self.gate._correction(req, self.gate._requirements(req), AIMessage(content="Saved reference: https://example.com")))


if __name__ == "__main__":
    unittest.main()
