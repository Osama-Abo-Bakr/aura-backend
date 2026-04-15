"""
Celery tasks for async vision processing.

Week 1: task skeletons only.
Full logic (download file → call Gemini → persist result → notify) ships in Week 2.
"""

from __future__ import annotations

from app.tasks.celery_app import celery


@celery.task(
    name="vision_tasks.process_skin_analysis",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_skin_analysis(self, analysis_id: str, file_path: str, language: str = "ar") -> None:
    """
    Background task: download a skin image from storage, run Gemini Vision
    analysis, and persist the results to the analyses table.

    Args:
        analysis_id: UUID of the analyses row to update.
        file_path: Storage path of the uploaded image.
        language: Response language for the Gemini prompt.
    """
    raise NotImplementedError("process_skin_analysis will be implemented in Week 2.")


@celery.task(
    name="vision_tasks.process_report_analysis",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_report_analysis(
    self,
    analysis_id: str,
    file_path: str,
    language: str = "ar",
    report_type: str | None = None,
) -> None:
    """
    Background task: download a medical report from storage, run Gemini Vision
    analysis, and persist the results to the analyses table.

    Args:
        analysis_id: UUID of the analyses row to update.
        file_path: Storage path of the uploaded report (PDF or image).
        language: Response language for the Gemini prompt.
        report_type: Optional hint about the report category.
    """
    raise NotImplementedError("process_report_analysis will be implemented in Week 2.")
