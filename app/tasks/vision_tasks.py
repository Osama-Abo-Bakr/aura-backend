"""Celery tasks for background processing.

Analysis tasks have been moved to the LangGraph conversation graph
and are now processed inline via SSE streaming.
"""

# Celery app is configured in celery_app.py
# Future background tasks (emails, batch processing) can be added here.
