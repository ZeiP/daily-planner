"""PDF generator for the daily planner."""

import logging
from datetime import date, time, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_LEFT

from planner.sources.base import CalendarEvent, PlannerData, TodoItem

logger = logging.getLogger(__name__)

# ── Layout Constants ──────────────────────────────────────────────────────────
# All dimensions easily tweakable for layout iteration.

PAGE_WIDTH, PAGE_HEIGHT = A4  # 210mm x 297mm
MARGIN_LEFT = 15 * mm
MARGIN_RIGHT = 15 * mm
MARGIN_TOP = 15 * mm
MARGIN_BOTTOM = 12 * mm

CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

# Column split: schedule on left, todos on right
SCHEDULE_WIDTH_RATIO = 0.58
TODO_WIDTH_RATIO = 0.42
COLUMN_GAP = 5 * mm

SCHEDULE_WIDTH = CONTENT_WIDTH * SCHEDULE_WIDTH_RATIO - COLUMN_GAP / 2
TODO_WIDTH = CONTENT_WIDTH * TODO_WIDTH_RATIO - COLUMN_GAP / 2
TODO_X = MARGIN_LEFT + SCHEDULE_WIDTH + COLUMN_GAP

# Section heights (approximate)
HEADER_HEIGHT = 12 * mm
READINESS_HEIGHT = 22 * mm
BILLABLE_HEIGHT = 12 * mm
REFLECTION_HEIGHT = 42 * mm
FOOTER_HEIGHT = 5 * mm

# Colors
COLOR_HEADER_BG = colors.HexColor("#1a1a2e")
COLOR_HEADER_TEXT = colors.white
COLOR_HOUR_LINE = colors.HexColor("#d0d0d0")
COLOR_HOUR_TEXT = colors.HexColor("#555555")
COLOR_EVENT_BG = colors.HexColor("#e8f0fe")
COLOR_EVENT_BORDER = colors.HexColor("#4285f4")
COLOR_EVENT_TEXT = colors.HexColor("#1a1a2e")
COLOR_ALL_DAY_BG = colors.HexColor("#fce8e6")
COLOR_ALL_DAY_BORDER = colors.HexColor("#ea4335")
COLOR_TODO_CHECKBOX = colors.HexColor("#666666")
COLOR_TODO_TEXT = colors.HexColor("#1a1a2e")
COLOR_TODO_CONTEXT = colors.HexColor("#888888")
COLOR_TODO_PROJECT = colors.HexColor("#aaaaaa")
COLOR_SECTION_HEADER = colors.HexColor("#1a1a2e")
COLOR_DIVIDER = colors.HexColor("#cccccc")
COLOR_LABEL = colors.HexColor("#555555")
COLOR_FIELD_LINE = colors.HexColor("#bbbbbb")
COLOR_STAR = colors.HexColor("#e0e0e0")

# Calendar-specific colors (cycle through for multiple calendars)
CALENDAR_COLORS = [
    (colors.HexColor("#e8f0fe"), colors.HexColor("#4285f4")),  # Blue
    (colors.HexColor("#e6f4ea"), colors.HexColor("#34a853")),  # Green
    (colors.HexColor("#fef7e0"), colors.HexColor("#fbbc04")),  # Yellow
    (colors.HexColor("#fce8e6"), colors.HexColor("#ea4335")),  # Red
    (colors.HexColor("#f3e8fd"), colors.HexColor("#a142f4")),  # Purple
]

# Font sizes
FONT_SIZE_TITLE = 16
FONT_SIZE_DATE = 11
FONT_SIZE_SECTION = 11
FONT_SIZE_HOUR = 8
FONT_SIZE_EVENT = 8
FONT_SIZE_TODO = 8.5
FONT_SIZE_CONTEXT = 8
FONT_SIZE_LABEL = 8
FONT_SIZE_FOOTER = 6


class PlannerPDFGenerator:
    """Generates a daily planner PDF from PlannerData."""

    def __init__(self, day_start_hour: int = 8, day_end_hour: int = 21):
        self.day_start_hour = day_start_hour
        self.day_end_hour = day_end_hour
        self._calendar_color_map: dict[str, int] = {}

    def generate(self, data: PlannerData, output_path: str | Path) -> Path:
        """Generate a planner PDF and return the output path."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        c = canvas.Canvas(str(output_path), pagesize=A4)
        c.setTitle(f"Daily Planner - {data.target_date.isoformat()}")

        # Draw sections top-to-bottom, each returns the Y position below it
        header_bottom = self._draw_header(c, data.target_date)
        readiness_bottom = self._draw_readiness(c, header_bottom)
        schedule_top = readiness_bottom - 5 * mm

        # Reserve space at bottom for reflection + billable + footer
        # Add extra padding (8mm) so content doesn't overlap section dividers
        reflection_top = MARGIN_BOTTOM + FOOTER_HEIGHT + REFLECTION_HEIGHT
        billable_top = reflection_top + BILLABLE_HEIGHT + 4 * mm

        # Draw schedule and tasks in the middle area
        self._draw_schedule(c, data, schedule_top, billable_top)
        self._draw_todos(c, data, schedule_top, billable_top)

        # Draw bottom sections
        self._draw_billable_hours(c, billable_top)
        self._draw_reflection(c, reflection_top)
        self._draw_footer(c, data.target_date)

        c.save()
        logger.info("Generated planner PDF: %s", output_path)
        return output_path

    def _get_calendar_color(self, calendar_name: str) -> tuple:
        """Get consistent colors for a calendar name."""
        if calendar_name not in self._calendar_color_map:
            idx = len(self._calendar_color_map) % len(CALENDAR_COLORS)
            self._calendar_color_map[calendar_name] = idx
        return CALENDAR_COLORS[self._calendar_color_map[calendar_name]]

    # ── Header ────────────────────────────────────────────────────────────────

    def _draw_header(self, c: canvas.Canvas, target_date: date) -> float:
        """Draw the date header. Returns the Y position below the header."""
        header_y = PAGE_HEIGHT - MARGIN_TOP - HEADER_HEIGHT

        # Background
        c.setFillColor(COLOR_HEADER_BG)
        c.roundRect(
            MARGIN_LEFT, header_y,
            CONTENT_WIDTH, HEADER_HEIGHT,
            radius=3 * mm, fill=1, stroke=0
        )

        # Date text — vertically centered in the header
        date_str = target_date.strftime("%A, %-d %B %Y")
        c.setFillColor(COLOR_HEADER_TEXT)
        c.setFont("Helvetica-Bold", FONT_SIZE_TITLE)
        text_y = header_y + (HEADER_HEIGHT - FONT_SIZE_TITLE) / 2
        c.drawString(MARGIN_LEFT + 6 * mm, text_y, date_str)

        return header_y

    # ── Readiness Section ─────────────────────────────────────────────────────

    def _draw_readiness(self, c: canvas.Canvas, header_bottom: float) -> float:
        """Draw the readiness/morning reflection section."""
        section_y = header_bottom - 7 * mm

        # Section title
        c.setFillColor(COLOR_SECTION_HEADER)
        c.setFont("Helvetica-Bold", FONT_SIZE_SECTION)
        c.drawString(MARGIN_LEFT, section_y, "Readiness")

        y = section_y - 6 * mm

        # Oura scores: two small labeled boxes side by side
        box_width = 22 * mm
        box_height = 5 * mm
        label_font_size = 7

        # Readiness score
        c.setFillColor(COLOR_LABEL)
        c.setFont("Helvetica", label_font_size)
        c.drawString(MARGIN_LEFT, y + 1 * mm, "Readiness:")
        c.setStrokeColor(COLOR_FIELD_LINE)
        c.setLineWidth(0.4)
        c.rect(MARGIN_LEFT + 18 * mm, y - 1 * mm, box_width, box_height, fill=0, stroke=1)

        # Sleep score
        c.setFillColor(COLOR_LABEL)
        c.drawString(MARGIN_LEFT + 48 * mm, y + 1 * mm, "Sleep:")
        c.setStrokeColor(COLOR_FIELD_LINE)
        c.rect(MARGIN_LEFT + 60 * mm, y - 1 * mm, box_width, box_height, fill=0, stroke=1)

        y -= 8 * mm

        # "How are you feeling? Why?" with a line for writing
        c.setFillColor(COLOR_LABEL)
        c.setFont("Helvetica-Oblique", label_font_size)
        c.drawString(MARGIN_LEFT, y, "How are you feeling? Why?")

        y -= 4 * mm
        # Writing line
        c.setStrokeColor(COLOR_FIELD_LINE)
        c.setLineWidth(0.3)
        c.line(MARGIN_LEFT, y, MARGIN_LEFT + CONTENT_WIDTH, y)

        return y

    # ── Schedule (Left Column) ────────────────────────────────────────────────

    def _draw_schedule(self, c: canvas.Canvas, data: PlannerData,
                       top_y: float, bottom_limit: float) -> float:
        """Draw the time-slot schedule with events in the left column."""
        section_y = top_y

        # Section title
        c.setFillColor(COLOR_SECTION_HEADER)
        c.setFont("Helvetica-Bold", FONT_SIZE_SECTION)
        c.drawString(MARGIN_LEFT, section_y, "Schedule")

        # All-day events banner
        all_day_events = [e for e in data.events if e.all_day]
        timed_events = [e for e in data.events if not e.all_day]

        y = section_y - 5 * mm

        if all_day_events:
            y = self._draw_all_day_events(c, all_day_events, y)
            y -= 3 * mm

        # Time slots
        num_hours = self.day_end_hour - self.day_start_hour
        available_height = y - bottom_limit
        slot_height = min(available_height / num_hours, 12 * mm)

        for hour_idx in range(num_hours):
            hour = self.day_start_hour + hour_idx
            slot_y = y - (hour_idx * slot_height)

            # Hour label
            c.setFillColor(COLOR_HOUR_TEXT)
            c.setFont("Helvetica", FONT_SIZE_HOUR)
            hour_label = f"{hour:02d}:00"
            c.drawString(MARGIN_LEFT, slot_y - 3 * mm, hour_label)

            # Hour line
            line_x = MARGIN_LEFT + 12 * mm
            c.setStrokeColor(COLOR_HOUR_LINE)
            c.setLineWidth(0.3)
            c.line(line_x, slot_y, MARGIN_LEFT + SCHEDULE_WIDTH, slot_y)

        # Draw events on slots
        for event in timed_events:
            if event.start_time is None:
                continue
            self._draw_timed_event(c, event, y, slot_height)

        return y - (num_hours * slot_height)

    def _draw_all_day_events(self, c: canvas.Canvas, events: list[CalendarEvent], y: float) -> float:
        """Draw all-day event banners. Returns new Y position."""
        for event in events:
            bg_color, border_color = self._get_calendar_color(event.calendar_name)
            banner_height = 5 * mm

            # Background with left border accent
            c.setFillColor(bg_color)
            c.rect(MARGIN_LEFT, y - banner_height, SCHEDULE_WIDTH, banner_height, fill=1, stroke=0)
            c.setFillColor(border_color)
            c.rect(MARGIN_LEFT, y - banner_height, 1.5 * mm, banner_height, fill=1, stroke=0)

            # Text
            c.setFillColor(COLOR_EVENT_TEXT)
            c.setFont("Helvetica-Bold", FONT_SIZE_EVENT)
            label = event.title
            if event.location:
                label += f"  📍 {event.location}"
            c.drawString(MARGIN_LEFT + 4 * mm, y - banner_height + 1.5 * mm, label)

            y -= banner_height + 1 * mm

        return y

    def _draw_timed_event(
        self, c: canvas.Canvas, event: CalendarEvent, schedule_top_y: float, slot_height: float
    ) -> None:
        """Draw a single timed event on the schedule."""
        if event.start_time is None:
            return

        start_hour = event.start_time.hour + event.start_time.minute / 60.0
        end_hour = start_hour + 1  # Default 1 hour
        if event.end_time:
            end_hour = event.end_time.hour + event.end_time.minute / 60.0

        # Clamp to visible range
        start_hour = max(start_hour, self.day_start_hour)
        end_hour = min(end_hour, self.day_end_hour)
        if start_hour >= end_hour:
            return

        # Calculate positions
        event_x = MARGIN_LEFT + 12 * mm + 1 * mm
        event_width = SCHEDULE_WIDTH - 12 * mm - 2 * mm
        top = schedule_top_y - (start_hour - self.day_start_hour) * slot_height
        bottom = schedule_top_y - (end_hour - self.day_start_hour) * slot_height
        event_height = top - bottom

        bg_color, border_color = self._get_calendar_color(event.calendar_name)

        # Background
        c.setFillColor(bg_color)
        c.rect(event_x, bottom, event_width, event_height, fill=1, stroke=0)

        # Left accent border
        c.setFillColor(border_color)
        c.rect(event_x, bottom, 1.2 * mm, event_height, fill=1, stroke=0)

        # Event text
        c.setFillColor(COLOR_EVENT_TEXT)
        text_x = event_x + 3 * mm
        text_y = top - 3 * mm

        # Time range
        c.setFont("Helvetica", FONT_SIZE_EVENT - 1)
        time_str = event.start_time.strftime("%H:%M")
        if event.end_time:
            time_str += f"–{event.end_time.strftime('%H:%M')}"
        c.drawString(text_x, text_y, time_str)

        # Title
        c.setFont("Helvetica-Bold", FONT_SIZE_EVENT)
        c.drawString(text_x, text_y - 3.2 * mm, event.title[:40])

        # Location (if room)
        if event.location and event_height > 12 * mm:
            c.setFont("Helvetica", FONT_SIZE_EVENT - 1)
            c.setFillColor(COLOR_TODO_CONTEXT)
            c.drawString(text_x, text_y - 6.5 * mm, f"📍 {event.location[:35]}")

    # ── Todos (Right Column) ──────────────────────────────────────────────────

    def _draw_todos(self, c: canvas.Canvas, data: PlannerData,
                    top_y: float, bottom_limit: float) -> None:
        """Draw the todo list in the right column."""
        section_y = top_y

        # Section title
        c.setFillColor(COLOR_SECTION_HEADER)
        c.setFont("Helvetica-Bold", FONT_SIZE_SECTION)
        c.drawString(TODO_X, section_y, "Tasks")

        # Vertical divider between columns
        divider_x = TODO_X - COLUMN_GAP / 2
        c.setStrokeColor(COLOR_DIVIDER)
        c.setLineWidth(0.5)
        c.line(divider_x, section_y + 3 * mm, divider_x, bottom_limit + 6 * mm)

        y = section_y - 6 * mm

        if not data.todos:
            c.setFillColor(COLOR_TODO_CONTEXT)
            c.setFont("Helvetica-Oblique", FONT_SIZE_TODO)
            c.drawString(TODO_X, y, "No tasks due")
            return

        # Group todos by context
        contexts: dict[str, list[TodoItem]] = {}
        for todo in data.todos:
            ctx = todo.context or "No Context"
            contexts.setdefault(ctx, []).append(todo)

        for ctx_name, todos in sorted(contexts.items()):
            if y < bottom_limit + 5 * mm:
                break

            # Context header
            c.setFillColor(COLOR_TODO_CONTEXT)
            c.setFont("Helvetica-Bold", FONT_SIZE_CONTEXT)
            c.drawString(TODO_X, y, f"@ {ctx_name}")
            y -= 4.5 * mm

            for todo in todos:
                if y < bottom_limit + 5 * mm:
                    break

                # Checkbox
                checkbox_size = 2.8 * mm
                c.setStrokeColor(COLOR_TODO_CHECKBOX)
                c.setLineWidth(0.5)
                c.rect(TODO_X, y - checkbox_size + 0.8 * mm, checkbox_size, checkbox_size, fill=0, stroke=1)

                # Todo description
                c.setFillColor(COLOR_TODO_TEXT)
                c.setFont("Helvetica", FONT_SIZE_TODO)
                # Truncate description to fit column
                max_chars = int(TODO_WIDTH / (FONT_SIZE_TODO * 0.4))
                desc = todo.description[:max_chars]
                c.drawString(TODO_X + checkbox_size + 2 * mm, y, desc)

                # Project and due date on the same row
                detail_parts = []
                if todo.project:
                    detail_parts.append(f"▸ {todo.project}")
                if todo.due_date:
                    if todo.due_date < data.target_date:
                        detail_parts.append(f"⚠ {todo.due_date.strftime('%d.%m.%Y')}")
                    else:
                        detail_parts.append("Due: Today")

                if detail_parts:
                    y -= 3.2 * mm
                    detail_str = "  ·  ".join(detail_parts)
                    if todo.due_date and todo.due_date < data.target_date:
                        c.setFillColor(colors.HexColor("#cc0000"))
                    else:
                        c.setFillColor(COLOR_TODO_PROJECT)
                    c.setFont("Helvetica-Oblique", FONT_SIZE_TODO - 1)
                    c.drawString(TODO_X + checkbox_size + 2 * mm, y, detail_str)

                y -= 4.5 * mm

            y -= 2 * mm  # Gap between contexts

    # ── Billable Hours ────────────────────────────────────────────────────────

    def _draw_billable_hours(self, c: canvas.Canvas, top_y: float) -> None:
        """Draw the billable hours tracking section."""
        section_y = top_y

        # Horizontal divider above
        c.setStrokeColor(COLOR_DIVIDER)
        c.setLineWidth(0.5)
        c.line(MARGIN_LEFT, section_y + 6 * mm, MARGIN_LEFT + CONTENT_WIDTH, section_y + 6 * mm)

        # Section title
        c.setFillColor(COLOR_SECTION_HEADER)
        c.setFont("Helvetica-Bold", FONT_SIZE_SECTION)
        c.drawString(MARGIN_LEFT, section_y, "Billable Hours")

        y = section_y - 5 * mm

        # Writing lines for billable hours
        c.setStrokeColor(COLOR_FIELD_LINE)
        c.setLineWidth(0.3)
        for i in range(2):
            line_y = y - (i * 5 * mm)
            c.line(MARGIN_LEFT, line_y, MARGIN_LEFT + CONTENT_WIDTH, line_y)

    # ── Reflection Section ────────────────────────────────────────────────────

    def _draw_reflection(self, c: canvas.Canvas, top_y: float) -> None:
        """Draw the end-of-day reflection section."""
        section_y = top_y

        # Horizontal divider above
        c.setStrokeColor(COLOR_DIVIDER)
        c.setLineWidth(0.5)
        c.line(MARGIN_LEFT, section_y + 6 * mm, MARGIN_LEFT + CONTENT_WIDTH, section_y + 6 * mm)

        # Section title
        c.setFillColor(COLOR_SECTION_HEADER)
        c.setFont("Helvetica-Bold", FONT_SIZE_SECTION)
        c.drawString(MARGIN_LEFT, section_y, "Reflection")

        y = section_y - 6 * mm

        # 1. "What was best in the day?" with a writing line
        c.setFillColor(COLOR_LABEL)
        c.setFont("Helvetica-Oblique", FONT_SIZE_LABEL)
        c.drawString(MARGIN_LEFT, y, "What was best in the day?")
        c.setStrokeColor(COLOR_FIELD_LINE)
        c.setLineWidth(0.3)
        c.line(MARGIN_LEFT + 42 * mm, y - 0.5 * mm, MARGIN_LEFT + CONTENT_WIDTH, y - 0.5 * mm)

        y -= 7 * mm

        # 2. Day rating: 1-5 stars
        c.setFillColor(COLOR_LABEL)
        c.setFont("Helvetica", FONT_SIZE_LABEL)
        c.drawString(MARGIN_LEFT, y, "Day rating:")
        star_x = MARGIN_LEFT + 22 * mm
        star_size = 4 * mm
        c.setFillColor(COLOR_STAR)
        c.setFont("Helvetica", 12)
        for i in range(5):
            c.drawString(star_x + i * (star_size + 2 * mm), y - 1 * mm, "☆")

        y -= 7 * mm

        # 3. "What did I learn today?" with a writing line
        c.setFillColor(COLOR_LABEL)
        c.setFont("Helvetica-Oblique", FONT_SIZE_LABEL)
        c.drawString(MARGIN_LEFT, y, "What did I learn today?")
        c.setStrokeColor(COLOR_FIELD_LINE)
        c.setLineWidth(0.3)
        c.line(MARGIN_LEFT + 40 * mm, y - 0.5 * mm, MARGIN_LEFT + CONTENT_WIDTH, y - 0.5 * mm)

        y -= 7 * mm

        # 4. Free reflection area with writing lines
        c.setFillColor(COLOR_LABEL)
        c.setFont("Helvetica-Oblique", FONT_SIZE_LABEL)
        c.drawString(MARGIN_LEFT, y, "Notes:")
        y -= 4 * mm

        c.setStrokeColor(COLOR_FIELD_LINE)
        c.setLineWidth(0.3)
        remaining = y - (MARGIN_BOTTOM + FOOTER_HEIGHT)
        num_lines = max(int(remaining / (4.5 * mm)), 1)
        for i in range(num_lines):
            line_y = y - (i * 4.5 * mm)
            c.line(MARGIN_LEFT, line_y, MARGIN_LEFT + CONTENT_WIDTH, line_y)

    # ── Footer ────────────────────────────────────────────────────────────────

    def _draw_footer(self, c: canvas.Canvas, target_date: date) -> None:
        """Draw the footer with generation timestamp."""
        from datetime import datetime
        c.setFillColor(COLOR_TODO_CONTEXT)
        c.setFont("Helvetica", FONT_SIZE_FOOTER)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.drawString(MARGIN_LEFT, MARGIN_BOTTOM - 3 * mm, f"Generated: {timestamp}")
        c.drawRightString(
            PAGE_WIDTH - MARGIN_RIGHT, MARGIN_BOTTOM - 3 * mm,
            "Daily Planner"
        )
