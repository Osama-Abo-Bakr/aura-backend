"""
Celery tasks for async vision processing.

Week 3: full implementations — download file → call Gemini → persist result.
"""

from __future__ import annotations

import asyncio

from app.db.supabase import supabase_admin
from app.tasks.celery_app import celery as celery_app


@celery_app.task(bind=True, max_retries=3, name="tasks.process_skin_analysis")
def process_skin_analysis(
    self,
    analysis_id: str,
    file_path: str,
    language: str,
    user_id: str,
) -> dict:
    """Process skin analysis asynchronously."""
    try:
        from app.services.gemini import analyze_skin
        from app.services.storage import download_file

        # Download file
        file_bytes, content_type = asyncio.run(download_file(file_path))

        # Run Gemini analysis
        result = asyncio.run(analyze_skin(file_bytes, content_type, language))

        # Update analyses table with result (schema: result, analysis_type)
        supabase_admin.table("analyses").update(
            {
                "result": result,
                "status": "completed",
            }
        ).eq("id", analysis_id).execute()

        # Record quota interaction (schema: interaction_type, no model_used/result_json)
        supabase_admin.table("ai_interactions").insert(
            {
                "user_id": user_id,
                "interaction_type": "skin",
            }
        ).execute()

        return {"status": "completed", "analysis_id": analysis_id}

    except Exception as exc:
        # Update status to failed
        supabase_admin.table("analyses").update({"status": "failed"}).eq(
            "id", analysis_id
        ).execute()
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(bind=True, max_retries=3, name="tasks.process_report_analysis")
def process_report_analysis(
    self,
    analysis_id: str,
    file_path: str,
    language: str,
    user_id: str,
) -> dict:
    """Process medical report analysis asynchronously."""
    try:
        from app.services.gemini import explain_medical_report
        from app.services.storage import download_file

        file_bytes, content_type = asyncio.run(download_file(file_path))

        result = asyncio.run(explain_medical_report(file_bytes, content_type, language))

        supabase_admin.table("analyses").update(
            {
                "result": result,
                "status": "completed",
            }
        ).eq("id", analysis_id).execute()

        supabase_admin.table("ai_interactions").insert(
            {
                "user_id": user_id,
                "interaction_type": "report",
            }
        ).execute()

        return {"status": "completed", "analysis_id": analysis_id}

    except Exception as exc:
        supabase_admin.table("analyses").update({"status": "failed"}).eq(
            "id", analysis_id
        ).execute()
        raise self.retry(exc=exc, countdown=10)
