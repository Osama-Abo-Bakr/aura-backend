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
    Analyze a skin image using Gemini Vision (gemini-2.5-flash).

    Args:
        image_bytes: Raw image data (JPEG / PNG / WEBP / HEIC).
        mime_type: e.g. 'image/jpeg'.
        language: 'ar' or 'en' — determines response language.
        notes: Optional user context (e.g. duration, prior treatments).

    Returns:
        Parsed findings dict with keys: concern, severity, description,
        natural_remedies, skincare_routine, see_doctor, doctor_reason, disclaimer.
    """
    import json
    import re

    import google.generativeai as genai

    from app.core.config import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(VISION_MODEL)

    lang = "Arabic" if language == "ar" else "English"
    notes_section = f"\n\nUser notes: {notes}" if notes else ""

    prompt = f"""
Analyze this skin image carefully. Respond in {lang}.{notes_section}

Return a JSON object with exactly these fields:
{{
  "concern": "brief name of identified concern",
  "severity": "mild | moderate | severe",
  "description": "plain language explanation (2-3 sentences)",
  "natural_remedies": ["remedy 1", "remedy 2"],
  "skincare_routine": ["step 1", "step 2"],
  "see_doctor": true or false,
  "doctor_reason": "reason if see_doctor is true, else null",
  "disclaimer": "This analysis is for informational purposes only and is not a medical diagnosis. Please consult a dermatologist for professional advice."
}}

If you cannot clearly identify the concern or it appears serious,
set see_doctor to true. Never guess at serious conditions.
Only return the JSON object, no markdown fences.
""".strip()

    image_part = {"mime_type": mime_type, "data": image_bytes}
    response = await model.generate_content_async([prompt, image_part])
    text = response.text.strip()
    # Strip markdown fences if the model adds them despite instructions.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


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
    import json
    import re

    import google.generativeai as genai

    from app.core.config import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(VISION_MODEL)
    lang = "Arabic" if language == "ar" else "English"

    prompt = f"""
    You are a medical report interpreter. Extract and explain this medical report
    in plain {lang} that a non-medical person can understand.

    Return ONLY a JSON object with exactly these fields:
    {{
      "summary": "2-3 sentence plain language summary of the overall report",
      "findings": [
        {{
          "name": "test or measurement name",
          "value": "the result value",
          "unit": "unit of measurement or empty string",
          "normal_range": "the normal reference range or empty string",
          "status": "normal | low | high | abnormal"
        }}
      ],
      "abnormal_flags": ["list of finding names that are outside normal range"],
      "next_steps": ["recommended action 1", "recommended action 2"],
      "disclaimer": "This explanation is for informational purposes only and does not constitute medical advice. Please consult your doctor to discuss these results."
    }}

    If the file does not appear to be a medical report, return findings as empty array
    and note this in the summary. Never fabricate specific test values.
    Only return the JSON object, no markdown fences.
    """

    file_part = {"mime_type": mime_type, "data": file_bytes}
    response = await model.generate_content_async([prompt, file_part])
    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


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
