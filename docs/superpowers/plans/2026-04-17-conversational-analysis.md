# Conversational Analysis Follow-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable seamless follow-up conversations after skin/report analysis by enhancing memory_injection to fetch the latest analysis from the current conversation and populate last_analysis in LangGraph state.

**Architecture:** Add a `get_conversation_analysis()` function to `app/services/memory.py` that queries the messages and analyses tables for the latest analysis in a conversation. Update the `memory_injection` node in `app/graph/nodes.py` to call this function and populate `last_analysis`/`last_analysis_type` in state when a previous analysis exists. The existing `ANALYSIS_FOLLOWUP_TEMPLATE` in `chat_responder` already handles the rest.

**Tech Stack:** Python, LangGraph, Supabase, pytest

---

### Task 1: Add `get_conversation_analysis` to memory service

**Files:**
- Modify: `app/services/memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Write failing test for `get_conversation_analysis` with a conversation that has an analysis**

Add to `tests/test_memory.py`:

```python
from app.services.memory import get_conversation_analysis


@pytest.mark.asyncio
async def test_get_conversation_analysis_with_analysis(mock_supabase):
    """Test fetching analysis from a conversation that has one."""
    # Mock messages query: find message with analysis_id
    msg_query = MagicMock()
    msg_query.select.return_value = msg_query
    msg_query.eq.return_value = msg_query
    msg_query.is_.return_value = msg_query
    msg_query.order.return_value = msg_query
    msg_query.limit.return_value = msg_query
    msg_query.execute.return_value = MagicMock(
        data=[{"analysis_id": "analysis-789"}]
    )

    # Mock analyses query: fetch the analysis record
    analysis_query = MagicMock()
    analysis_query.select.return_value = analysis_query
    analysis_query.eq.return_value = analysis_query
    analysis_query.execute.return_value = MagicMock(
        data=[{
            "analysis_type": "skin",
            "result": {"concern": "mild acne", "severity": "mild"},
        }]
    )

    # Route table calls: first call = messages, second call = analyses
    mock_supabase.table.side_effect = [
        msg_query,  # messages table query
        analysis_query,  # analyses table query
    ]

    result, analysis_type = await get_conversation_analysis("conv-456")
    assert result == {"concern": "mild acne", "severity": "mild"}
    assert analysis_type == "skin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/test_memory.py::test_get_conversation_analysis_with_analysis -v`

Expected: FAIL with `ImportError: cannot import name 'get_conversation_analysis' from 'app.services.memory'`

- [ ] **Step 3: Implement `get_conversation_analysis`**

Add to `app/services/memory.py` after the `build_cycle_context` function:

```python
async def get_conversation_analysis(conversation_id: str) -> tuple[dict | None, str | None]:
    """Fetch the latest analysis from a conversation.

    Queries the messages table for the latest message with an analysis_id,
    then fetches the full analysis record from the analyses table.

    Returns:
        (result_dict, analysis_type) if found, (None, None) otherwise.
    """
    # Find the latest message with an analysis_id in this conversation
    msgs_resp = (
        supabase_admin.table("messages")
        .select("analysis_id")
        .eq("conversation_id", conversation_id)
        .is_("analysis_id", "not_null")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not msgs_resp.data:
        return None, None

    analysis_id = msgs_resp.data[0]["analysis_id"]

    # Fetch the analysis record
    analysis_resp = (
        supabase_admin.table("analyses")
        .select("analysis_type, result")
        .eq("id", analysis_id)
        .execute()
    )

    if not analysis_resp.data:
        return None, None

    analysis = analysis_resp.data[0]
    result = analysis.get("result", {})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = {}

    return result, analysis.get("analysis_type")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/test_memory.py::test_get_conversation_analysis_with_analysis -v`

Expected: PASS

- [ ] **Step 5: Write test for `get_conversation_analysis` with no analysis**

Add to `tests/test_memory.py`:

```python
@pytest.mark.asyncio
async def test_get_conversation_analysis_no_analysis(mock_supabase):
    """Test fetching analysis from a conversation that has none."""
    msg_query = MagicMock()
    msg_query.select.return_value = msg_query
    msg_query.eq.return_value = msg_query
    msg_query.is_.return_value = msg_query
    msg_query.order.return_value = msg_query
    msg_query.limit.return_value = msg_query
    msg_query.execute.return_value = MagicMock(data=[])

    mock_supabase.table.return_value = msg_query

    result, analysis_type = await get_conversation_analysis("conv-no-analysis")
    assert result is None
    assert analysis_type is None
```

- [ ] **Step 6: Run the new test**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/test_memory.py::test_get_conversation_analysis_no_analysis -v`

Expected: PASS

- [ ] **Step 7: Write test for `get_conversation_analysis` with JSON string result**

Add to `tests/test_memory.py`:

```python
@pytest.mark.asyncio
async def test_get_conversation_analysis_with_json_string_result(mock_supabase):
    """Test that JSON string result is parsed correctly."""
    msg_query = MagicMock()
    msg_query.select.return_value = msg_query
    msg_query.eq.return_value = msg_query
    msg_query.is_.return_value = msg_query
    msg_query.order.return_value = msg_query
    msg_query.limit.return_value = msg_query
    msg_query.execute.return_value = MagicMock(
        data=[{"analysis_id": "analysis-999"}]
    )

    analysis_query = MagicMock()
    analysis_query.select.return_value = analysis_query
    analysis_query.eq.return_value = analysis_query
    analysis_query.execute.return_value = MagicMock(
        data=[{
            "analysis_type": "report",
            "result": '{"summary": "Blood test results", "abnormal_flags": ["cholesterol"]}',
        }]
    )

    mock_supabase.table.side_effect = [msg_query, analysis_query]

    result, analysis_type = await get_conversation_analysis("conv-789")
    assert result == {"summary": "Blood test results", "abnormal_flags": ["cholesterol"]}
    assert analysis_type == "report"
```

- [ ] **Step 8: Run the new test**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/test_memory.py::test_get_conversation_analysis_with_json_string_result -v`

Expected: PASS

- [ ] **Step 9: Commit**

```bash
cd /Users/osamaabobakr/Aura-app/aura-backend
git add app/services/memory.py tests/test_memory.py
git commit -m "feat: add get_conversation_analysis to memory service

Fetches the latest analysis from a conversation's messages and
parses the result (handling both dict and JSON string formats).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Update `memory_injection` node to inject conversation analysis

**Files:**
- Modify: `app/graph/nodes.py` (lines 24, 33-38)
- Test: `tests/test_graph.py`

- [ ] **Step 1: Write failing test for `memory_injection` with conversation analysis**

Add to `tests/test_graph.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from app.graph.nodes import memory_injection


class TestMemoryInjection:
    @pytest.mark.asyncio
    async def test_injects_conversation_analysis(self):
        """memory_injection populates last_analysis from the conversation."""
        state = {
            "user_id": "user-123",
            "conversation_id": "conv-456",
            "language": "en",
            "current_message": "Tell me more about this",
            "current_file": None,
            "messages": [],
            "last_analysis": None,
            "last_analysis_type": None,
            "summary_context": "",
            "cycle_context": "",
            "response_chunks": [],
            "analysis_meta": None,
            "error": None,
        }

        mock_analysis = {"concern": "mild acne", "severity": "mild"}

        with patch("app.graph.nodes.build_summary_context", new_callable=lambda: lambda *a, **kw: _async_return("Skin analysis: mild acne")), \
             patch("app.graph.nodes.build_cycle_context", return_value="Cycle: follicular phase"), \
             patch("app.graph.nodes.get_conversation_analysis", new_callable=lambda: lambda *a, **kw: _async_return((mock_analysis, "skin"))):
            # We need async mocks, so use patch.object style
            pass

    @pytest.mark.asyncio
    async def test_injects_analysis_when_present(self):
        """memory_injection populates last_analysis when conversation has an analysis."""
        state = {
            "user_id": "user-123",
            "conversation_id": "conv-456",
            "language": "en",
            "current_message": "Tell me more about this",
            "current_file": None,
            "messages": [],
            "last_analysis": None,
            "last_analysis_type": None,
            "summary_context": "",
            "cycle_context": "",
            "response_chunks": [],
            "analysis_meta": None,
            "error": None,
        }

        mock_analysis = {"concern": "mild acne", "severity": "mild"}

        async def mock_summary(user_id):
            return "Skin analysis: mild acne"

        def mock_cycle(user_id):
            return "Cycle: follicular phase"

        async def mock_conv_analysis(conv_id):
            return (mock_analysis, "skin")

        with patch("app.graph.nodes.build_summary_context", side_effect=mock_summary), \
             patch("app.graph.nodes.build_cycle_context", side_effect=mock_cycle), \
             patch("app.graph.nodes.get_conversation_analysis", side_effect=mock_conv_analysis):
            result = await memory_injection(state)

        assert result["last_analysis"] == mock_analysis
        assert result["last_analysis_type"] == "skin"

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_analysis(self):
        """memory_injection does not overwrite last_analysis if state already has one."""
        existing_analysis = {"concern": "eczema", "severity": "moderate"}
        state = {
            "user_id": "user-123",
            "conversation_id": "conv-456",
            "language": "en",
            "current_message": "Tell me more",
            "current_file": None,
            "messages": [],
            "last_analysis": existing_analysis,
            "last_analysis_type": "skin",
            "summary_context": "",
            "cycle_context": "",
            "response_chunks": [],
            "analysis_meta": None,
            "error": None,
        }

        async def mock_summary(user_id):
            return ""

        def mock_cycle(user_id):
            return ""

        async def mock_conv_analysis(conv_id):
            return ({"concern": "different"}, "report")

        with patch("app.graph.nodes.build_summary_context", side_effect=mock_summary), \
             patch("app.graph.nodes.build_cycle_context", side_effect=mock_cycle), \
             patch("app.graph.nodes.get_conversation_analysis", side_effect=mock_conv_analysis):
            result = await memory_injection(state)

        # Should NOT contain last_analysis because state already has one
        assert "last_analysis" not in result
        assert "last_analysis_type" not in result

    @pytest.mark.asyncio
    async def test_no_analysis_in_conversation(self):
        """memory_injection works fine when conversation has no analysis."""
        state = {
            "user_id": "user-123",
            "conversation_id": "conv-no-analysis",
            "language": "en",
            "current_message": "Hello",
            "current_file": None,
            "messages": [],
            "last_analysis": None,
            "last_analysis_type": None,
            "summary_context": "",
            "cycle_context": "",
            "response_chunks": [],
            "analysis_meta": None,
            "error": None,
        }

        async def mock_summary(user_id):
            return "No past analyses"

        def mock_cycle(user_id):
            return ""

        async def mock_conv_analysis(conv_id):
            return (None, None)

        with patch("app.graph.nodes.build_summary_context", side_effect=mock_summary), \
             patch("app.graph.nodes.build_cycle_context", side_effect=mock_cycle), \
             patch("app.graph.nodes.get_conversation_analysis", side_effect=mock_conv_analysis):
            result = await memory_injection(state)

        assert "last_analysis" not in result
        assert "last_analysis_type" not in result
        assert result["summary_context"] == "No past analyses"
        assert result["cycle_context"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/test_graph.py::TestMemoryInjection -v`

Expected: FAIL — `get_conversation_analysis` is not imported in `nodes.py` yet, and `memory_injection` doesn't call it

- [ ] **Step 3: Update `memory_injection` in `app/graph/nodes.py`**

Update the import line on line 24:

```python
from app.services.memory import build_summary_context, build_cycle_context, get_conversation_analysis
```

Update the `memory_injection` function (lines 33-38) to:

```python
async def memory_injection(state: ConversationState) -> dict:
    """Inject ambient context from the user's past analyses, conversations, cycle data,
    and any analysis from the current conversation."""
    user_id = state["user_id"]
    conversation_id = state["conversation_id"]

    summary = await build_summary_context(user_id=user_id)
    cycle = build_cycle_context(user_id=user_id)

    result = {"summary_context": summary, "cycle_context": cycle}

    # Inject analysis from current conversation (enables follow-up questions)
    if not state.get("last_analysis"):
        analysis, analysis_type = await get_conversation_analysis(conversation_id)
        if analysis:
            result["last_analysis"] = analysis
            result["last_analysis_type"] = analysis_type

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/test_graph.py::TestMemoryInjection -v`

Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/ -v`

Expected: All tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
cd /Users/osamaabobakr/Aura-app/aura-backend
git add app/graph/nodes.py tests/test_graph.py
git commit -m "feat: update memory_injection to fetch conversation analysis

The memory_injection node now queries the current conversation's latest
analysis and populates last_analysis/last_analysis_type in state, enabling
follow-up questions about skin and report analysis results.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Add `is_` method to conftest mock and verify end-to-end

**Files:**
- Modify: `tests/conftest.py` (add `is_` method to mock chain)
- Test: `tests/test_memory.py`, `tests/test_graph.py`

The `get_conversation_analysis` function uses `.is_("analysis_id", "not_null")` which is a Supabase client method. We need to add `is_` to the mock chain in `conftest.py` so that tests using the mock supabase client can call this method.

- [ ] **Step 1: Add `is_` to the mock chain in conftest.py**

In `tests/conftest.py`, add `is_` to the reset mock chain in the `_reset_mock_supabase` fixture (after line with `.delete.return_value`):

```python
_mock_supabase_client.is_.return_value = _mock_supabase_client
```

The full fixture should look like:

```python
@pytest.fixture(autouse=True)
def _reset_mock_supabase():
    """Reset the mock supabase client between tests so state doesn't leak."""
    _mock_supabase_client.reset_mock()
    # Re-chain the builder pattern after reset
    _mock_supabase_client.table.return_value = _mock_supabase_client
    _mock_supabase_client.select.return_value = _mock_supabase_client
    _mock_supabase_client.insert.return_value = _mock_supabase_client
    _mock_supabase_client.update.return_value = _mock_supabase_client
    _mock_supabase_client.delete.return_value = _mock_supabase_client
    _mock_supabase_client.eq.return_value = _mock_supabase_client
    _mock_supabase_client.is_.return_value = _mock_supabase_client
    _mock_supabase_client.maybe_single.return_value = _mock_supabase_client
    _mock_supabase_client.order.return_value = _mock_supabase_client
    _mock_supabase_client.upsert.return_value = _mock_supabase_client
    yield
```

- [ ] **Step 2: Run the full test suite**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd /Users/osamaabobakr/Aura-app/aura-backend
git add tests/conftest.py
git commit -m "test: add is_ method to supabase mock chain

Required for get_conversation_analysis tests that use .is_('not_null').

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Update import in `test_memory.py` and verify all tests pass

**Files:**
- Test: `tests/test_memory.py` (update import line)

The `test_memory.py` file currently imports only `build_summary_context` from `app.services.memory`. After Task 1 adds `get_conversation_analysis`, we need to ensure the import is updated.

- [ ] **Step 1: Update the import line in test_memory.py**

Change line 3 of `tests/test_memory.py` from:

```python
from app.services.memory import build_summary_context
```

to:

```python
from app.services.memory import build_summary_context, get_conversation_analysis
```

- [ ] **Step 2: Run all memory tests**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/test_memory.py -v`

Expected: All 5 tests PASS (2 existing + 3 new)

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/osamaabobakr/Aura-app/aura-backend && python -m pytest tests/ -v`

Expected: All 113+ tests PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/osamaabobakr/Aura-app/aura-backend
git add tests/test_memory.py
git commit -m "test: update import for get_conversation_analysis in memory tests

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Verification

1. `python -m pytest tests/ -v` — all tests pass
2. `python -c "import ast; ast.parse(open('app/services/memory.py').read()); ast.parse(open('app/graph/nodes.py').read()); print('OK')"` — syntax check
3. Manual test: Start the server, upload a skin image, then send a follow-up message like "tell me more about this" — verify the AI references the analysis results