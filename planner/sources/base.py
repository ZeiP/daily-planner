"""Abstract base class for planner data sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional


@dataclass
class CalendarEvent:
    """A single calendar event."""
    title: str
    start_time: Optional[time] = None  # None for all-day events
    end_time: Optional[time] = None
    all_day: bool = False
    location: Optional[str] = None
    description: Optional[str] = None
    calendar_name: str = ""


@dataclass
class TodoItem:
    """A single todo item."""
    description: str
    context: str = ""
    project: str = ""
    due_date: Optional[date] = None
    notes: str = ""
    priority: int = 0  # 0 = no priority


@dataclass
class PlannerData:
    """Aggregated data for a single day's planner."""
    target_date: date
    events: list[CalendarEvent] = field(default_factory=list)
    todos: list[TodoItem] = field(default_factory=list)


class DataSource(ABC):
    """Abstract base class for data sources.

    Subclass this to add new data sources (JIRA, weather, etc.).
    """

    @abstractmethod
    def fetch(self, target_date: date, data: PlannerData) -> None:
        """Fetch data for the given date and add it to PlannerData.

        Args:
            target_date: The date to fetch data for.
            data: The PlannerData object to populate (mutated in place).
        """
        ...
