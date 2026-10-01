"""Walk through the rules with made-up data: python demo.py"""
from datetime import datetime

from booking import BookingEngine, Space, User

spaces = [
    Space("aud", "Main auditorium", capacity=120),
    Space("r201", "Meeting room 201", capacity=10),
]
users = [
    User("u1", "Ana (staff)", "staff"),
    User("u2", "Luis (professor)", "professor"),
    User("adm", "Marta (admin)", "admin"),
]
engine = BookingEngine(spaces, users)
now = datetime(2026, 10, 5, 8, 0)  # a Monday


def show(title, decision):
    mark = "OK " if decision.accepted else "NO "
    status = decision.status.value if decision.status else "-"
    print(f"{mark} {title:<48} status={status}")
    for r in decision.reasons:
        print(f"      - {r}")


def at(day, h1, h2):
    return datetime(2026, 10, day, h1), datetime(2026, 10, day, h2)


show("Ana books room 201, Mon 9-10", engine.request("u1", "r201", *at(5, 9, 10), attendees=4, now=now))
show("Ana books the same slot again (duplicate)", engine.request("u1", "r201", *at(5, 9, 10), attendees=4, now=now))
show("Luis wants room 201 at the same time", engine.request("u2", "r201", *at(5, 9, 10), attendees=2, now=now))
show("Luis books the auditorium for 150 people", engine.request("u2", "aud", *at(6, 9, 11), attendees=150, now=now))
show("Ana books on Saturday at 20:00", engine.request("u1", "aud", *at(10, 20, 21), now=now))
show("Ana books Tue 9-10", engine.request("u1", "r201", *at(6, 9, 10), now=now))
show("Ana books Wed 9-10", engine.request("u1", "r201", *at(7, 9, 10), now=now))
show("Ana's 4th booking this week, no reason", engine.request("u1", "r201", *at(8, 9, 10), now=now))
d = engine.request("u1", "r201", *at(8, 9, 10), justification="Board visit", now=now)
show("Ana's 4th booking, with a justification", d)
engine.review(d.booking.id, "adm", approve=True)
print(f"    Marta approves booking #{d.booking.id} -> {d.booking.status.value}")
print("\nOccupancy Monday:", engine.occupancy(datetime(2026, 10, 5).date()))
