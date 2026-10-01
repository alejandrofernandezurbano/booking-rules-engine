import unittest
from datetime import datetime

from booking import BookingEngine, BookingError, Space, Status, User

NOW = datetime(2026, 10, 5, 8, 0)  # Monday


def slot(day, h1, h2):
    return datetime(2026, 10, day, h1), datetime(2026, 10, day, h2)


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.e = BookingEngine(
            [Space("r1", "Room 1", capacity=5)],
            [User("a", "A", "staff"), User("b", "B", "staff"), User("p", "P", "professor"), User("adm", "M", "admin")],
        )

    def req(self, user, day, h1, h2, **kw):
        return self.e.request(user, "r1", *slot(day, h1, h2), now=NOW, **kw)

    def test_simple_booking_is_confirmed(self):
        d = self.req("a", 5, 9, 10)
        self.assertTrue(d.accepted)
        self.assertEqual(d.status, Status.CONFIRMED)

    def test_duplicate_is_rejected(self):
        self.req("a", 5, 9, 10)
        d = self.req("a", 5, 9, 10)
        self.assertFalse(d.accepted)
        self.assertIn("duplicate", " ".join(d.reasons))

    def test_overlap_with_other_user_is_rejected(self):
        self.req("a", 5, 9, 11)
        self.assertFalse(self.req("b", 5, 10, 12).accepted)

    def test_back_to_back_is_allowed(self):
        self.req("a", 5, 9, 10)
        self.assertTrue(self.req("b", 5, 10, 11).accepted)

    def test_capacity_hours_weekend_and_past_report_all_reasons(self):
        d = self.e.request("a", "r1", datetime(2026, 10, 3, 20), datetime(2026, 10, 3, 21), attendees=9, now=NOW)
        self.assertFalse(d.accepted)
        self.assertGreaterEqual(len(d.reasons), 4)

    def test_weekly_limit_requires_justification_then_approval(self):
        for day in (5, 6, 7):
            self.assertTrue(self.req("a", day, 9, 10).accepted)
        self.assertFalse(self.req("a", 8, 9, 10).accepted)
        d = self.req("a", 8, 9, 10, justification="Audit visit")
        self.assertEqual(d.status, Status.PENDING_APPROVAL)
        self.e.review(d.booking.id, "adm", approve=True)
        self.assertEqual(d.booking.status, Status.CONFIRMED)

    def test_limit_depends_on_role(self):
        for day in (5, 6, 7, 8):
            self.assertEqual(self.req("p", day, 9, 10).status, Status.CONFIRMED)

    def test_cancelled_booking_frees_the_slot_and_the_quota(self):
        d = self.req("a", 5, 9, 10)
        self.e.cancel(d.booking.id, "a")
        self.assertTrue(self.req("b", 5, 9, 10).accepted)
        self.assertEqual(self.e.weekly_count("a", datetime(2026, 10, 5).date()), 0)

    def test_only_admin_reviews_and_only_owner_cancels(self):
        for day in (5, 6, 7):
            self.req("a", day, 9, 10)
        d = self.req("a", 8, 9, 10, justification="x")
        with self.assertRaises(BookingError):
            self.e.review(d.booking.id, "b", approve=True)
        with self.assertRaises(BookingError):
            self.e.cancel(d.booking.id, "b")

    def test_occupancy(self):
        self.req("a", 5, 9, 12)
        self.assertAlmostEqual(self.e.occupancy(datetime(2026, 10, 5).date())["r1"], 3 / 12, places=3)


if __name__ == "__main__":
    unittest.main()
