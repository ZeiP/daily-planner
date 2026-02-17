"""CalDAV data source for fetching events from Davical."""

import logging
from datetime import date, datetime, time, timedelta

import caldav
from dateutil import tz, rrule
from datetime import date, datetime, time, timedelta

from planner.config import CalDavConfig
from planner.sources.base import CalendarEvent, DataSource, PlannerData

logger = logging.getLogger(__name__)


class CalDavSource(DataSource):
    """Fetch calendar events from a CalDAV server (Davical)."""

    def __init__(self, config: CalDavConfig, timezone: str = "Europe/Helsinki"):
        self.config = config
        self.tz = tz.gettz(timezone)

    def fetch(self, target_date: date, data: PlannerData) -> None:
        """Fetch events for the target date from all configured calendars."""
        logger.info("Connecting to CalDAV server at %s", self.config.url)

        client = caldav.DAVClient(
            url=self.config.url,
            username=self.config.username,
            password=self.config.password,
        )

        calendars_to_check = []
        
        # 1. Handle explicit URLs in configuration
        explicit_urls = [c for c in self.config.calendars if c.startswith("http")]
        filter_names = [c for c in self.config.calendars if not c.startswith("http")]

        for url in explicit_urls:
            try:
                cal = client.calendar(url=url)
                logger.debug("Added explicit calendar URL: %s", url)
                calendars_to_check.append(cal)
            except Exception as e:
                logger.error("Failed to add calendar by URL %s: %s", url, e)

        # 2. Discover calendars if needed
        # If no specific calendars configured (empty list), OR if we have name filters
        should_discover = (not self.config.calendars) or (len(filter_names) > 0)

        if should_discover:
            try:
                principal = client.principal()
                discovered = principal.calendars()
                logger.info("Discovered %d calendars via principal", len(discovered))

                for cal in discovered:
                    cal_name = cal.name or "Unknown"
                    
                    # If specific name filters exist, check them
                    if filter_names and cal_name not in filter_names:
                        logger.debug("Skipping calendar: %s", cal_name)
                        continue
                    
                    calendars_to_check.append(cal)
            except Exception as e:
                logger.error("Failed to discover calendars: %s", e)
                # If we have explicit URLs, we might still proceed, so don't return yet?
                # But if discovery was the only thing, we are done.

        if not calendars_to_check:
            logger.warning("No calendars found to process.")
            return

        logger.info("Processing %d calendars", len(calendars_to_check))

        for cal in calendars_to_check:
            # specialized name handling
            try:
                cal_name = cal.name or str(cal.url)
            except:
                cal_name = "Unknown"

            logger.info("Fetching events from calendar: %s", cal_name)
            self._fetch_calendar_events(cal, cal_name, target_date, data)

    def _fetch_calendar_events(
        self, cal: caldav.Calendar, cal_name: str, target_date: date, data: PlannerData
    ) -> None:
        """Fetch events from a single calendar for the target date."""
        start = datetime.combine(target_date, time.min).replace(tzinfo=self.tz)
        end = datetime.combine(target_date + timedelta(days=1), time.min).replace(tzinfo=self.tz)

        try:
            results = cal.date_search(start=start, end=end, expand=True)
        except Exception as e:
            logger.warning("Failed to search with expand=True for %s: %s. Retrying with expand=False", cal_name, e)
            try:
                results = cal.date_search(start=start, end=end, expand=False)
            except Exception as e2:
                logger.error("Failed to search calendar %s: %s", cal_name, e2)
                return

        for event_obj in results:
            try:
                self._parse_event(event_obj, cal_name, target_date, data)
            except Exception as e:
                logger.warning("Failed to parse event from %s: %s", cal_name, e)

    def _parse_event(
        self, event_obj: caldav.Event, cal_name: str, target_date: date, data: PlannerData
    ) -> None:
        """Parse a single CalDAV event into a CalendarEvent."""
        ical = event_obj.icalendar_instance
        for component in ical.walk():
            if component.name != "VEVENT":
                continue

            summary = str(component.get("SUMMARY", "Untitled"))
            dtstart = component.get("DTSTART")
            dtend = component.get("DTEND")
            location = str(component.get("LOCATION", "")) or None
            description = str(component.get("DESCRIPTION", "")) or None

            if dtstart is None:
                continue

            dtstart_val = dtstart.dt
            dtend_val = dtend.dt if dtend else None

            # Calculate start/end of target day for filtering
            target_start = datetime.combine(target_date, time.min).replace(tzinfo=self.tz)
            target_end = datetime.combine(target_date + timedelta(days=1), time.min).replace(tzinfo=self.tz)

            # --- FILTERING LOGIC ---
            # Check if event actually occurs on target_date
            
            is_recurring = component.get("RRULE") is not None
            
            if not is_recurring:
                # 1. Non-recurring: Start date must match target date (or overlap)
                # Handle single date event vs multi-day
                
                # Normalize dtstart to our timezone for comparison
                check_dt = dtstart_val
                if isinstance(check_dt, datetime):
                     if check_dt.tzinfo:
                         check_dt = check_dt.astimezone(self.tz)
                     else:
                         check_dt = check_dt.replace(tzinfo=self.tz) # Assume local if naive
                     check_date = check_dt.date()
                else:
                     check_date = check_dt # It's a date object
                
                # Note: This checks if STARTS on target date.
                # If event started yesterday and ends tomorrow, it should show!
                # But our Planner usually shows "Schedule" as things starting today?
                # Does existing code handle spanning?
                # "Summary (Start Time - End Time)"
                # If it started yesterday, Start Time is yesterday.
                # Let's stick to "Starts on target_date" for now to reduce noise, unless strict overlap is needed.
                # Davical usually returns only overlapping.
                # If user sees "many other dates", likely "starts on other dates".
                
                if check_date != target_date:
                    logger.debug("Skipping non-matching date event: %s (%s)", summary, check_date)
                    continue

            else:
                # 2. Recurring: Check if recursion happens today
                try:
                    rrule_prop = component.get("RRULE")
                    if rrule_prop:
                        # rrule_prop is vRecur or list. Usually vRecur.
                        # handle list case if needed (multiple RRULEs supported?)
                        if isinstance(rrule_prop, list):
                            rr_ical = rrule_prop[0].to_ical().decode('utf-8')
                        else:
                            rr_ical = rrule_prop.to_ical().decode('utf-8')
                        
                        logger.debug("Checking recurrence for '%s'. RRULE: %s Start: %s", summary, rr_ical, dtstart_val)

                        # Prepare start date (timezone aware/naive handling)
                        start_dt_rr = dtstart_val
                        if isinstance(start_dt_rr, datetime):
                            if not start_dt_rr.tzinfo:
                                start_dt_rr = start_dt_rr.replace(tzinfo=self.tz)
                            else:
                                start_dt_rr = start_dt_rr.astimezone(self.tz)
                        else:
                            # If all-day event, convert to datetime at midnight for rrule calculation
                            start_dt_rr = datetime.combine(start_dt_rr, time.min).replace(tzinfo=self.tz)

                        # Create rrule
                        rule = rrule.rrulestr(rr_ical, dtstart=start_dt_rr)
                        
                        # Check for occurrence today
                        # We use local timezone boundaries
                        instances = list(rule.between(target_start, target_end, inc=True))
                        
                        if instances:
                            logger.debug(" - Found occurrence: %s", instances[0])
                        else:
                            logger.debug(" - No occurrence on target date. Skipping.")
                            continue
                        
                        # Use the specific instance time (e.g. DST adjustments)
                        instance_dt = instances[0]
                        
                        # Update dtstart_val / dtend_val to this instance
                        # Preserve original duration
                        if isinstance(dtstart_val, datetime):
                            orig_start = dtstart_val if dtstart_val.tzinfo else dtstart_val.replace(tzinfo=self.tz)
                            duration = (dtend_val - orig_start) if dtend_val else timedelta(0)
                            
                            dtstart_val = instance_dt
                            if dtend_val:
                                dtend_val = instance_dt + duration
                        else:
                            # All-day event instance is datetime from rrule, convert back to date if needed?
                            # But wait, rrule for DATE start yields DATETIME usually (at midnight).
                            # If original was date, our code below handles date check.
                            pass

                except Exception as e:
                    logger.warning("Failed to check recurrence for %s: %s", summary, e)
                    # Use fallback strategy: if check fails, KEEP it? Or SKIP it?
                    # User complained about "many other dates". Skip is safer for cleanup.
                    # But keeping avoids missing critical info.
                    # Let's keep it but log.



            # Check if all-day event (date vs datetime)
            if isinstance(dtstart_val, date) and not isinstance(dtstart_val, datetime):
                event = CalendarEvent(
                    title=summary,
                    all_day=True,
                    location=location,
                    description=description,
                    calendar_name=cal_name,
                )
            else:
                # Convert to local timezone
                if hasattr(dtstart_val, 'tzinfo') and dtstart_val.tzinfo:
                    dtstart_val = dtstart_val.astimezone(self.tz)
                if dtend_val and hasattr(dtend_val, 'tzinfo') and dtend_val.tzinfo:
                    dtend_val = dtend_val.astimezone(self.tz)

                event = CalendarEvent(
                    title=summary,
                    start_time=dtstart_val.time() if isinstance(dtstart_val, datetime) else None,
                    end_time=dtend_val.time() if isinstance(dtend_val, datetime) else None,
                    all_day=False,
                    location=location,
                    description=description,
                    calendar_name=cal_name,
                )

            data.events.append(event)
            logger.debug("Added event: %s (%s)", summary, cal_name)
