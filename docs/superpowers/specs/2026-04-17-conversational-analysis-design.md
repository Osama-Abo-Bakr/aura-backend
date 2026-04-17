# Conversational Analysis Follow-Up Design

> **Goal:** Enable seamless follow-up conversations after skin/report analysis, so users can ask questions about their results naturally in the same chat.

> **Architecture:** Enhance the existing `memory_injection` LangGraph node to fetch the latest analysis from the current conversation and populate `last_analysis`/`last_analysis_type` in state. The existing `ANALYSIS_FOLLOWUP_TEMPLATE` in `chat_responder` already injects analysis context into the system prompt — it just never fires on follow-up messages because those fields are empty.

> **Tech Stack:** LangGraph, Supabase (messages + analyses tables), Gemini

---

## Problem

When a user sends a follow-up message after a skin or report analysis, the system starts a fresh LangGraph invocation. The `last_analysis` field in `ConversationState` is empty because it was only populated during the analysis node — which ran on the *previous* message. The `ANALYSIS_FOLLOWUP_TEMPLATE` exists but is never triggered because `last_analysis` is `None` on follow-up messages.

Result: the AI has no idea the user just received an analysis, and cannot answer follow-up questions about it.

## Solution

Modify the `memory_injection` node to also fetch the latest analysis from the current conversation. If found, populate `last_analysis` and `last_analysis_type` in the state. The downstream `chat_responder` already has `ANALYSIS_FOLLOWUP_TEMPLATE` to use this context — no other changes needed.

### Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Follow-up style | Seamless continuation | AI naturally references analysis results; user can ask anything |
| Multi-analysis context | Latest only | Simplest; new analysis replaces old context in conversation |
| Scope | Analysis follow-up only | No prompt changes; just make existing infrastructure work |
| Approach | Memory injection enhancement | Minimal change; reuses existing `ANALYSIS_FOLLOWUP_TEMPLATE` and `last_analysis` state field |

### Flow

```
Message 1 (with skin image):
  START → memory_injection (no analysis in conv yet) → router → skin_analyzer
        → sets last_analysis → response_formatter → END
  ✅ Analysis result returned to user

Message 2 (follow-up: "tell me more about this"):
  START → memory_injection (fetches analysis from conv)
        → sets last_analysis → router → chat_responder
        → uses ANALYSIS_FOLLOWUP_TEMPLATE → response_formatter → END
  ✅ AI references the skin analysis naturally

Message 3 (another follow-up: "what natural remedies?"):
  START → memory_injection (fetches same analysis)
        → sets last_analysis → router → chat_responder → END
  ✅ AI still has analysis context
```

### Edge Case: Current Message IS an Analysis

When the user uploads an image, `memory_injection` runs first but the analysis hasn't been written to the DB yet — so `get_conversation_analysis` returns `None`. This is correct. The `skin_analyzer`/`report_analyzer` node then sets `last_analysis` directly in the state. On the *next* follow-up message, `memory_injection` will find the analysis in the DB.

The `not state.get("last_analysis")` guard in `memory_injection` prevents overwriting an analysis set by a previous node in the same invocation (shouldn't happen, but defensive).

---

## Changes

### 1. `app/services/memory.py` — Add `get_conversation_analysis`

New async function that fetches the latest analysis from a conversation:

1. Query `messages` table for the latest message with a non-null `analysis_id` in the given conversation
2. If found, fetch the full analysis record from the `analyses` table
3. Parse the `result` field (JSON string or dict) and return `(result_dict, analysis_type)`
4. Return `(None, None)` if no analysis exists in the conversation

### 2. `app/graph/nodes.py` — Update `memory_injection`

Add a call to `get_conversation_analysis(conversation_id)` after the existing `build_summary_context` and `build_cycle_context` calls. If an analysis is found and `state["last_analysis"]` is not already set, populate `last_analysis` and `last_analysis_type` in the returned state dict.

### No Other Changes

- **`app/graph/prompts.py`** — `ANALYSIS_FOLLOWUP_TEMPLATE` already exists and handles analysis context injection
- **`app/graph/state.py`** — `last_analysis` and `last_analysis_type` fields already exist in `ConversationState`
- **`app/graph/graph.py`** — Graph topology unchanged
- **`app/api/v1/chat.py`** — Endpoint unchanged; initial state construction unchanged
- **No new endpoints, models, or DB schema changes**

---

## Testing

- Unit test: `get_conversation_analysis` returns correct analysis when conversation has one, `None` when conversation has none
- Unit test: `memory_injection` populates `last_analysis` when conversation has an analysis
- Unit test: `memory_injection` does not overwrite `last_analysis` if state already has one
- Integration test: Follow-up message after skin analysis includes analysis context in AI response
- Integration test: Follow-up message after report analysis includes analysis context
- Existing tests continue to pass