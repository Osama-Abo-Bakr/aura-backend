"""
Gemini AI service layer.

Week 1: constants, system prompt, and function signatures only.
Full implementations ship in Week 2 when streaming + vision are wired up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------

FLASH_MODEL = "gemini-2.0-flash"
VISION_MODEL = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

HEALTH_SYSTEM_PROMPT = """
You are Aura, a compassionate and knowledgeable AI health companion designed specifically
for women in the MENA (Middle East and North Africa) region.

Your core responsibilities:
• Provide evidence-based health information tailored to women's wellness needs.
• Offer support for topics including menstrual health, hormonal balance, nutrition,
  mental well-being, skin health, and chronic condition management.
• Respect cultural sensitivities relevant to the MENA region.
• Encourage users to consult qualified healthcare professionals for diagnosis or treatment.

Mandatory disclaimer (include in every response that touches medical topics):
"هذه المعلومات للتثقيف الصحي فقط وليست بديلاً عن استشارة طبية متخصصة."
(English: "This information is for health education only and is not a substitute for
professional medical advice.")

Language rule:
Detect the language of the user's message and respond in the same language (Arabic or
English). If the language cannot be determined, default to Arabic.

Tone: warm, empathetic, non-judgmental, and professional.
""".strip()

# ---------------------------------------------------------------------------
# Function stubs — implemented in Week 2
# ---------------------------------------------------------------------------


async def stream_chat_response(
    conversation_history: list[dict],
    new_message: str,
    language: str = "ar",
) -> AsyncIterator[str]:
    """
    Stream a conversational response from Gemini Flash.

    Args:
        conversation_history: List of prior messages in the format
            [{"role": "user"|"model", "parts": [{"text": "..."}]}].
        new_message: The latest user message.
        language: 'ar' or 'en' — hints the model to respond in the right language.

    Yields:
        Text chunks as they arrive from the Gemini streaming API.
    """
    raise NotImplementedError("stream_chat_response will be implemented in Week 2.")
    # Required to make the function an async generator at the type level.
    yield  # type: ignore[misc]


async def analyze_skin(
    image_bytes: bytes,
    mime_type: str,
    language: str = "ar",
    notes: str | None = None,
) -> dict:
    """
    Analyze a skin image using Gemini Vision.

    Args:
        image_bytes: Raw image data (JPEG / PNG / WEBP).
        mime_type: e.g. 'image/jpeg'.
        language: Response language.
        notes: Optional context from the user (e.g. duration, prior treatments).

    Returns:
        Parsed findings dict matching the SkinAnalysisResponse schema.
    """
    raise NotImplementedError("analyze_skin will be implemented in Week 2.")


async def explain_medical_report(
    file_bytes: bytes,
    mime_type: str,
    language: str = "ar",
    report_type: str | None = None,
    notes: str | None = None,
) -> dict:
    """
    Parse and explain a medical report (blood test, hormone panel, etc.).

    Args:
        file_bytes: Raw file bytes (PDF or image).
        mime_type: MIME type of the file.
        language: Response language.
        report_type: Optional hint (e.g. 'blood_test', 'thyroid_panel').
        notes: Optional user-provided context.

    Returns:
        Parsed result dict matching the ReportAnalysisResponse schema.
    """
    raise NotImplementedError("explain_medical_report will be implemented in Week 2.")


async def generate_wellness_plan(
    user_profile: dict,
    health_logs: list[dict],
    language: str = "ar",
) -> dict:
    """
    Generate a personalised wellness plan based on the user's profile and recent logs.

    Args:
        user_profile: Profile data (age, conditions, goals, etc.).
        health_logs: Recent HealthLog entries.
        language: Response language.

    Returns:
        Parsed plan dict matching the WellnessPlanResponse schema.
    """
    raise NotImplementedError("generate_wellness_plan will be implemented in Week 2.")
