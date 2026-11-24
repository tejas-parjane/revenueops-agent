from app.workers.celery_app import celery_app


@celery_app.task(name="agent.run_task")
def run_agent_task(task_id: str) -> None:
    from app.services.agent import run_task_sync

    run_task_sync(str(task_id))


@celery_app.task(name="execution.run_action")
def execute_action_task(execution_id: str) -> None:
    from app.services.execution import execute_action_sync

    execute_action_sync(str(execution_id))
