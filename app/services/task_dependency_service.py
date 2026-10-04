"""Task Dependency Resolution and Graph Engine (Phase 36).

Enforces:
- Prerequisite validation before task execution
- State transitions to/from BLOCKED state
- Automatic unblocking when prerequisites reach COMPLETED or VERIFIED
- Dependency engine does NOT infer clinical meaning or treatments.
"""

from __future__ import annotations

from typing import List, Optional
from app.repositories.task_repository import TaskRepository
from app.schemas.task import (
    TaskDependency,
    TaskDependencyStatus,
    TaskRecord,
    TaskStatus,
)
from app.schemas.task_history import TaskHistoryAction


class TaskDependencyService:
    """Manages prerequisite dependency evaluation, blocking, and cascade unblocking."""

    def __init__(self, task_repo: TaskRepository) -> None:
        self.task_repo = task_repo

    def evaluate_initial_dependencies(self, task: TaskRecord) -> TaskRecord:
        """Evaluate dependencies at task creation.
        
        If any prerequisite task is not completed, mark status as BLOCKED.
        """
        if not task.dependencies:
            return task

        all_satisfied = True
        updated_deps: List[TaskDependency] = []

        for dep in task.dependencies:
            prereq = self.task_repo.get_by_id(dep.depends_on_task_id)
            if prereq and prereq.status in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}:
                updated_deps.append(dep.model_copy(update={"status": TaskDependencyStatus.COMPLETED}))
            else:
                updated_deps.append(dep.model_copy(update={"status": TaskDependencyStatus.WAITING}))
                all_satisfied = False

        if not all_satisfied:
            task = task.model_copy(
                update={
                    "dependencies": updated_deps,
                    "status": TaskStatus.BLOCKED,
                }
            )
        else:
            task = task.model_copy(update={"dependencies": updated_deps})

        return task

    def check_prerequisites_met(self, task: TaskRecord) -> bool:
        """Check if all prerequisite dependencies for task have been fulfilled."""
        if not task.dependencies:
            return True

        for dep in task.dependencies:
            prereq = self.task_repo.get_by_id(dep.depends_on_task_id)
            if not prereq or prereq.status not in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}:
                return False
        return True

    def resolve_completed_prerequisite(self, completed_task_id: str, actor_id: str, actor_role: str) -> List[TaskRecord]:
        """Cascade unblock any dependent tasks once completed_task_id finishes."""
        dependents = self.task_repo.list_dependents(completed_task_id)
        unblocked_tasks: List[TaskRecord] = []

        for dep_task in dependents:
            updated_deps: List[TaskDependency] = []
            all_satisfied = True

            for dep in dep_task.dependencies:
                if dep.depends_on_task_id == completed_task_id:
                    updated_deps.append(dep.model_copy(update={"status": TaskDependencyStatus.COMPLETED}))
                else:
                    prereq = self.task_repo.get_by_id(dep.depends_on_task_id)
                    if prereq and prereq.status in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}:
                        updated_deps.append(dep.model_copy(update={"status": TaskDependencyStatus.COMPLETED}))
                    else:
                        updated_deps.append(dep)
                        all_satisfied = False

            if all_satisfied and dep_task.status == TaskStatus.BLOCKED:
                new_status = TaskStatus.ASSIGNED if dep_task.assignee_id else TaskStatus.CREATED
                unblocked = dep_task.model_copy(
                    update={
                        "dependencies": updated_deps,
                        "status": new_status,
                    }
                )
                saved = self.task_repo.save(unblocked)
                self.task_repo.add_history(
                    task_id=saved.id,
                    action=TaskHistoryAction.TASK_UNBLOCKED,
                    from_status=TaskStatus.BLOCKED.value,
                    to_status=new_status.value,
                    actor_id=actor_id,
                    actor_role=actor_role,
                    reason=f"Prerequisite task {completed_task_id} completed.",
                )
                unblocked_tasks.append(saved)
            else:
                # Update dependency statuses only
                dep_task = dep_task.model_copy(update={"dependencies": updated_deps})
                self.task_repo.save(dep_task)

        return unblocked_tasks
