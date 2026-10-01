"""Business-rules engine for booking shared spaces (rooms, auditoriums, labs).

Every rule is a small function that returns a list of problems. The engine
runs all of them, so the user sees every reason at once instead of fixing
one error at a time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from itertools import count


class Status(str, Enum):
    CONFIRMED = "confirmed"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


ACTIVE = (Status.CONFIRMED, Status.PENDING_APPROVAL)


@dataclass(frozen=True)
class Space:
    id: str
    name: str
    capacity: int
    opens: time = time(7, 0)
    closes: time = time(19, 0)
    weekdays_only: bool = True


@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: str  # e.g. "staff", "professor", "admin"


@dataclass
class Booking:
    id: int
    space_id: str
    user_id: str
    start: datetime
    end: datetime
    attendees: int
    status: Status
    justification: str = ""
    reviewed_by: str | None = None


@dataclass
class Policy:
    """Weekly limits per role. Roles not listed fall back to `default_weekly_limit`."""
    weekly_limit_by_role: dict[str, int] = field(default_factory=lambda: {"staff": 3, "professor": 8})
    default_weekly_limit: int = 3
    unlimited_roles: tuple[str, ...] = ("admin",)
    min_minutes: int = 30
    max_hours: int = 8
    max_days_ahead: int = 60


@dataclass
class Decision:
    accepted: bool
    status: Status | None
    reasons: list[str]
    booking: Booking | None = None


class BookingError(Exception):
    pass


def week_bounds(day: date) -> tuple[datetime, datetime]:
    monday = day - timedelta(days=day.weekday())
    start = datetime.combine(monday, time.min)
    return start, start + timedelta(days=7)


class BookingEngine:
    def __init__(self, spaces: list[Space], users: list[User], policy: Policy | None = None):
        self.spaces = {s.id: s for s in spaces}
        self.users = {u.id: u for u in users}
        self.policy = policy or Policy()
        self.bookings: list[Booking] = []
        self._ids = count(1)

    # ---------------- rules ----------------

    def _rule_times(self, space: Space, start: datetime, end: datetime, now: datetime) -> list[str]:
        problems = []
        if end <= start:
            return ["The end time must be after the start time."]
        if start.date() != end.date():
            problems.append("A booking must start and end on the same day.")
        if start < now:
            problems.append("You cannot book in the past.")
        if (start.date() - now.date()).days > self.policy.max_days_ahead:
            problems.append(f"Bookings open at most {self.policy.max_days_ahead} days ahead.")
        minutes = (end - start).total_seconds() / 60
        if minutes < self.policy.min_minutes:
            problems.append(f"Minimum duration is {self.policy.min_minutes} minutes.")
        if minutes > self.policy.max_hours * 60:
            problems.append(f"Maximum duration is {self.policy.max_hours} hours.")
        if space.weekdays_only and start.weekday() >= 5:
            problems.append(f"{space.name} can only be booked Monday to Friday.")
        if start.time() < space.opens or end.time() > space.closes:
            problems.append(f"{space.name} is open from {space.opens:%H:%M} to {space.closes:%H:%M}.")
        return problems

    def _rule_capacity(self, space: Space, attendees: int) -> list[str]:
        if attendees < 1:
            return ["There must be at least one attendee."]
        if attendees > space.capacity:
            return [f"{space.name} holds {space.capacity} people; you asked for {attendees}."]
        return []

    def _rule_overlap(self, space: Space, user: User, start: datetime, end: datetime) -> list[str]:
        problems = []
        for b in self.bookings:
            if b.status not in ACTIVE or not (b.start < end and start < b.end):
                continue
            if b.space_id == space.id:
                if b.user_id == user.id:
                    problems.append("You already have this space booked at that time (duplicate).")
                else:
                    problems.append(f"{space.name} is already booked from {b.start:%H:%M} to {b.end:%H:%M}.")
            elif b.user_id == user.id:
                problems.append(f"You already have another space booked from {b.start:%H:%M} to {b.end:%H:%M}.")
        return problems

    def weekly_count(self, user_id: str, day: date) -> int:
        start, end = week_bounds(day)
        return sum(1 for b in self.bookings
                   if b.user_id == user_id and b.status in ACTIVE and start <= b.start < end)

    def weekly_limit(self, user: User) -> int | None:
        if user.role in self.policy.unlimited_roles:
            return None
        return self.policy.weekly_limit_by_role.get(user.role, self.policy.default_weekly_limit)

    # ---------------- actions ----------------

    def request(self, user_id: str, space_id: str, start: datetime, end: datetime,
                attendees: int = 1, justification: str = "", now: datetime | None = None) -> Decision:
        now = now or datetime.now()
        user = self.users.get(user_id)
        space = self.spaces.get(space_id)
        if user is None or space is None:
            return Decision(False, None, ["Unknown user or space."])

        reasons = (self._rule_times(space, start, end, now)
                   + self._rule_capacity(space, attendees)
                   + self._rule_overlap(space, user, start, end))
        if reasons:
            return Decision(False, None, reasons)

        status = Status.CONFIRMED
        limit = self.weekly_limit(user)
        if limit is not None and self.weekly_count(user.id, start.date()) >= limit:
            if not justification.strip():
                return Decision(False, None, [
                    f"Your weekly limit is {limit} bookings. Add a justification to ask an administrator for approval."])
            status = Status.PENDING_APPROVAL

        booking = Booking(next(self._ids), space.id, user.id, start, end, attendees, status, justification.strip())
        self.bookings.append(booking)
        note = ["Waiting for administrator approval."] if status is Status.PENDING_APPROVAL else []
        return Decision(True, status, note, booking)

    def _get(self, booking_id: int) -> Booking:
        for b in self.bookings:
            if b.id == booking_id:
                return b
        raise BookingError(f"Booking {booking_id} does not exist.")

    def review(self, booking_id: int, admin_id: str, approve: bool) -> Booking:
        admin = self.users.get(admin_id)
        if admin is None or admin.role not in self.policy.unlimited_roles:
            raise BookingError("Only an administrator can review bookings.")
        b = self._get(booking_id)
        if b.status is not Status.PENDING_APPROVAL:
            raise BookingError("Only pending bookings can be reviewed.")
        b.status = Status.CONFIRMED if approve else Status.REJECTED
        b.reviewed_by = admin.id
        return b

    def cancel(self, booking_id: int, user_id: str) -> Booking:
        b = self._get(booking_id)
        user = self.users.get(user_id)
        if user is None or (b.user_id != user_id and user.role not in self.policy.unlimited_roles):
            raise BookingError("You can only cancel your own bookings.")
        b.status = Status.CANCELLED
        return b

    def occupancy(self, day: date) -> dict[str, float]:
        """Share of opening hours each space is booked on a given day (0-1), for a dashboard."""
        result = {}
        for s in self.spaces.values():
            open_min = (datetime.combine(day, s.closes) - datetime.combine(day, s.opens)).total_seconds() / 60
            used = sum((b.end - b.start).total_seconds() / 60 for b in self.bookings
                       if b.space_id == s.id and b.status is Status.CONFIRMED and b.start.date() == day)
            result[s.id] = round(used / open_min, 3) if open_min else 0.0
        return result
