from uuid import UUID

from app.core.config import settings
from app.workers.tasks import execute_action_task, run_agent_task


def dispatch_agent_task(task_id: UUID | str) -> None:
    if settings.celery_task_always_eager:
        run_agent_task(str(task_id))
        return
    run_agent_task.delay(str(task_id))


def dispatch_execution(execution_id: UUID | str) -> None:
    if settings.celery_task_always_eager:
        execute_action_task(str(execution_id))
        return
    execute_action_task.delay(str(execution_id))
