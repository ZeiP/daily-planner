"""Tracks GTD data source for fetching todos."""

import logging
from datetime import date
from xml.etree import ElementTree

import requests

from planner.config import TracksConfig
from planner.sources.base import DataSource, PlannerData, TodoItem

logger = logging.getLogger(__name__)


class TracksSource(DataSource):
    """Fetch active todos from a Tracks GTD instance."""

    def __init__(self, config: TracksConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = (config.username, config.password)
        self.session.headers.update({
            "Accept": "application/xml",
            "Content-Type": "application/xml",
        })
        # Tracks base URL (strip trailing slash)
        self.base_url = config.url.rstrip("/")

    def fetch(self, target_date: date, data: PlannerData) -> None:
        """Fetch active todos from Tracks and add them to PlannerData."""
        logger.info("Fetching todos from Tracks at %s", self.base_url)

        # Fetch contexts and projects for name lookups
        contexts = self._fetch_contexts()
        projects = self._fetch_projects()

        # Fetch active todos
        todos = self._fetch_todos(contexts, projects)

        # Only show todos that have a deadline and are due today or overdue
        relevant_todos = [
            t for t in todos 
            if t.due_date and t.due_date <= target_date
        ]
        relevant_todos.sort(key=lambda t: t.due_date, reverse=True)

        logger.debug(
            "Todos: %d total, %d active today. target_date=%s. Due dates (desc): %s",
            len(todos), len(relevant_todos), target_date,
            [(t.description[:30], str(t.due_date)) for t in relevant_todos[:10]]
        )

        data.todos.extend(relevant_todos)


        logger.info("Added %d/%d todos from Tracks (filtered by deadline <= %s)", len(data.todos), len(todos), target_date)

    def _fetch_contexts(self) -> dict[int, str]:
        """Fetch all contexts, returning a id->name mapping."""
        try:
            resp = self.session.get(f"{self.base_url}/contexts.xml", timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch contexts: %s", e)
            return {}

        contexts = {}
        root = ElementTree.fromstring(resp.content)
        for ctx in root.findall(".//context"):
            ctx_id = ctx.findtext("id")
            ctx_name = ctx.findtext("name")
            if ctx_id and ctx_name:
                contexts[int(ctx_id)] = ctx_name

        logger.debug("Found %d contexts", len(contexts))
        return contexts

    def _fetch_projects(self) -> dict[int, str]:
        """Fetch all projects, returning a id->name mapping."""
        try:
            resp = self.session.get(f"{self.base_url}/projects.xml", timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to fetch projects: %s", e)
            return {}

        projects = {}
        root = ElementTree.fromstring(resp.content)
        for proj in root.findall(".//project"):
            proj_id = proj.findtext("id")
            proj_name = proj.findtext("name")
            if proj_id and proj_name:
                projects[int(proj_id)] = proj_name

        logger.debug("Found %d projects", len(projects))
        return projects

    def _fetch_todos(self, contexts: dict[int, str], projects: dict[int, str]) -> list[TodoItem]:
        """Fetch active (not completed) todos."""
        try:
            resp = self.session.get(f"{self.base_url}/todos.xml?limit_to_active_todos=1", timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch todos: %s", e)
            return []

        todos = []
        root = ElementTree.fromstring(resp.content)

        for todo_el in root.findall(".//todo"):
            description = todo_el.findtext("description", "").strip()
            if not description:
                continue

            # Resolve context and project names
            context_id = todo_el.findtext("context-id", "")
            project_id = todo_el.findtext("project-id", "")
            context_name = contexts.get(int(context_id), "") if context_id else ""
            project_name = projects.get(int(project_id), "") if project_id else ""

            # Parse due date
            due_str = todo_el.findtext("due", "")
            due_date = None
            if due_str:
                try:
                    # Handle both "2026-02-15" and "2026-02-15T00:00:00+02:00" formats
                    due_date = date.fromisoformat(due_str.split("T")[0])
                except ValueError:
                    logger.warning("Could not parse due date: %r", due_str)

            # Parse notes
            notes = todo_el.findtext("notes", "").strip()

            todos.append(TodoItem(
                description=description,
                context=context_name,
                project=project_name,
                due_date=due_date,
                notes=notes,
            ))

        logger.debug("Parsed %d active todos", len(todos))
        return todos
