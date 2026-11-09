import datetime
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APITestCase
from .models import Guide, Category, Tour, Booking, Comment

User = get_user_model()
PAST = datetime.date(2024, 5, 1)
FUTURE = datetime.date(2099, 5, 1)
T10 = datetime.time(10, 0)
T12 = datetime.time(12, 0)


class BaseTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="pass12345")
        self.other = User.objects.create_user("boris", password="pass12345")
        guide = Guide.objects.create(name="Иван")
        self.horse = Category.objects.create(name="Конный", slug="horse")
        self.hike = Category.objects.create(name="Пеший", slug="hike")
        self.moto = Category.objects.create(name="Мото", slug="moto")
        self.tour1 = Tour.objects.create(title="Алтай верхом", price=100, guide=guide)
        self.tour1.categories.add(self.horse)
        self.tour2 = Tour.objects.create(title="Горы пешком", price=50, guide=guide)
        self.tour2.categories.add(self.hike, self.moto)  # M2M: несколько категорий


class RelationsTest(BaseTest):
    def test_one_to_one_profile_created(self):
        self.assertEqual(self.user.profile.user, self.user)

    def test_one_to_many_guide_tours(self):
        self.assertEqual(self.tour1.guide.tours.count(), 2)

    def test_many_to_many_categories(self):
        self.assertEqual(self.tour2.categories.count(), 2)
        self.assertIn(self.tour1, self.horse.tours.all())


class BookingTest(BaseTest):
    url = "/api/bookings/"

    def book(self, tour, date=FUTURE, time="10:00"):
        return self.client.post(self.url, {"tour": tour.id, "date": date, "time": time})

    def test_requires_auth(self):
        self.assertIn(self.book(self.tour1).status_code, (401, 403))

    def test_create_booking(self):
        self.client.force_authenticate(self.user)
        r = self.book(self.tour1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Booking.objects.count(), 1)

    def test_same_slot_second_tour_forbidden(self):
        self.client.force_authenticate(self.user)
        self.book(self.tour1)
        r = self.book(self.tour2)  # та же дата и время
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Booking.objects.count(), 1)

    def test_same_tour_same_slot_forbidden(self):
        self.client.force_authenticate(self.user)
        self.book(self.tour1)
        self.assertEqual(self.book(self.tour1).status_code, 400)

    def test_other_time_allowed(self):
        self.client.force_authenticate(self.user)
        self.book(self.tour1)
        self.assertEqual(self.book(self.tour2, time="12:00").status_code, 201)

    def test_other_user_same_slot_allowed(self):
        self.client.force_authenticate(self.user)
        self.book(self.tour1)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.book(self.tour1).status_code, 201)

    def test_db_constraint(self):
        Booking.objects.create(user=self.user, tour=self.tour1, date=FUTURE, time=T10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(user=self.user, tour=self.tour2, date=FUTURE, time=T10)

    def test_invalid_data(self):
        self.client.force_authenticate(self.user)
        for payload in ({}, {"tour": 999, "date": "2099-01-01", "time": "10:00"},
                        {"tour": self.tour1.id, "date": "not-a-date", "time": "10:00"},
                        {"tour": self.tour1.id, "date": "2099-01-01", "time": "25:99"}):
            r = self.client.post(self.url, payload)
            self.assertEqual(r.status_code, 400, payload)

    def test_user_sees_only_own_bookings(self):
        Booking.objects.create(user=self.other, tour=self.tour1, date=FUTURE, time=T10)
        self.client.force_authenticate(self.user)
        self.assertEqual(len(self.client.get(self.url).data), 0)


class CommentTest(BaseTest):
    url = "/api/comments/"

    def test_multiple_comments_on_visited_tours(self):
        Booking.objects.create(user=self.user, tour=self.tour1, date=PAST, time=T10)
        Booking.objects.create(user=self.user, tour=self.tour2, date=PAST, time=T12)
        self.client.force_authenticate(self.user)
        for tour, text in ((self.tour1, "Супер"), (self.tour1, "Ещё раз супер"),
                           (self.tour2, "Красиво")):
            r = self.client.post(self.url, {"tour": tour.id, "text": text})
            self.assertEqual(r.status_code, 201)
        self.assertEqual(Comment.objects.filter(user=self.user).count(), 3)

    def test_comment_without_visit_forbidden(self):
        self.client.force_authenticate(self.user)
        r = self.client.post(self.url, {"tour": self.tour1.id, "text": "Не был"})
        self.assertEqual(r.status_code, 400)

    def test_comment_on_future_booking_forbidden(self):
        Booking.objects.create(user=self.user, tour=self.tour1, date=FUTURE, time=T10)
        self.client.force_authenticate(self.user)
        r = self.client.post(self.url, {"tour": self.tour1.id, "text": "Рано"})
        self.assertEqual(r.status_code, 400)

    def test_comment_requires_auth(self):
        r = self.client.post(self.url, {"tour": self.tour1.id, "text": "x"})
        self.assertIn(r.status_code, (401, 403))

    def test_empty_text_invalid(self):
        Booking.objects.create(user=self.user, tour=self.tour1, date=PAST, time=T10)
        self.client.force_authenticate(self.user)
        r = self.client.post(self.url, {"tour": self.tour1.id, "text": ""})
        self.assertEqual(r.status_code, 400)


class CategoryFilterTest(BaseTest):
    def titles(self, query):
        return [t["title"] for t in self.client.get(f"/api/tours/{query}").data]

    def test_all_tours(self):
        self.assertEqual(len(self.titles("")), 2)

    def test_filter_horse(self):
        self.assertEqual(self.titles("?category=horse"), ["Алтай верхом"])

    def test_tour_in_two_categories(self):
        self.assertEqual(self.titles("?category=hike"), ["Горы пешком"])
        self.assertEqual(self.titles("?category=moto"), ["Горы пешком"])

    def test_unknown_category_empty(self):
        self.assertEqual(self.titles("?category=boat"), [])


class BookingValidationTest(BaseTest):
    """Проверка всех полей при отправке POST /api/bookings/"""
    url = "/api/bookings/"

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def post(self, **data):
        return self.client.post(self.url, data)

    def test_missing_tour(self):
        self.assertEqual(self.post(date="2099-01-01", time="10:00").status_code, 400)

    def test_missing_date(self):
        self.assertEqual(self.post(tour=self.tour1.id, time="10:00").status_code, 400)

    def test_missing_time(self):
        self.assertEqual(self.post(tour=self.tour1.id, date="2099-01-01").status_code, 400)

    def test_nonexistent_tour(self):
        self.assertEqual(self.post(tour=9999, date="2099-01-01", time="10:00").status_code, 400)

    def test_tour_not_a_number(self):
        self.assertEqual(self.post(tour="abc", date="2099-01-01", time="10:00").status_code, 400)

    def test_bad_date_format(self):
        self.assertEqual(self.post(tour=self.tour1.id, date="01.01.2099", time="10:00").status_code, 400)

    def test_past_date_forbidden(self):
        self.assertEqual(self.post(tour=self.tour1.id, date="2020-01-01", time="10:00").status_code, 400)

    def test_bad_time(self):
        self.assertEqual(self.post(tour=self.tour1.id, date="2099-01-01", time="99:99").status_code, 400)

    def test_user_cannot_be_spoofed(self):
        r = self.post(tour=self.tour1.id, date="2099-01-01", time="10:00", user=self.other.id)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Booking.objects.get().user, self.user)

    def test_response_fields(self):
        r = self.post(tour=self.tour1.id, date="2099-01-01", time="10:00")
        self.assertEqual(set(r.data), {"id", "tour", "date", "time"})


class BookingDeleteListTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.mine = Booking.objects.create(user=self.user, tour=self.tour1, date=FUTURE, time=T10)
        self.foreign = Booking.objects.create(user=self.other, tour=self.tour1, date=FUTURE, time=T10)

    def test_list_requires_auth(self):
        self.assertIn(self.client.get("/api/bookings/").status_code, (401, 403))

    def test_delete_own(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.delete(f"/api/bookings/{self.mine.id}/").status_code, 204)
        self.assertFalse(Booking.objects.filter(id=self.mine.id).exists())

    def test_delete_foreign_forbidden(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.delete(f"/api/bookings/{self.foreign.id}/").status_code, 404)
        self.assertTrue(Booking.objects.filter(id=self.foreign.id).exists())

    def test_delete_requires_auth(self):
        self.assertIn(self.client.delete(f"/api/bookings/{self.mine.id}/").status_code, (401, 403))

    def test_slot_free_after_delete(self):
        self.client.force_authenticate(self.user)
        self.client.delete(f"/api/bookings/{self.mine.id}/")
        r = self.client.post("/api/bookings/", {"tour": self.tour2.id, "date": FUTURE, "time": "10:00"})
        self.assertEqual(r.status_code, 201)


class CommentValidationTest(BaseTest):
    url = "/api/comments/"

    def setUp(self):
        super().setUp()
        Booking.objects.create(user=self.user, tour=self.tour1, date=PAST, time=T10)
        self.client.force_authenticate(self.user)

    def test_missing_tour(self):
        self.assertEqual(self.client.post(self.url, {"text": "x"}).status_code, 400)

    def test_missing_text(self):
        self.assertEqual(self.client.post(self.url, {"tour": self.tour1.id}).status_code, 400)

    def test_nonexistent_tour(self):
        self.assertEqual(self.client.post(self.url, {"tour": 9999, "text": "x"}).status_code, 400)

    def test_visit_to_other_tour_does_not_count(self):
        r = self.client.post(self.url, {"tour": self.tour2.id, "text": "не был"})
        self.assertEqual(r.status_code, 400)

    def test_other_user_cannot_comment_on_my_visit(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(self.url, {"tour": self.tour1.id, "text": "x"}).status_code, 400)

    def test_comment_saved_for_current_user(self):
        self.client.post(self.url, {"tour": self.tour1.id, "text": "Класс", "user": self.other.id})
        self.assertEqual(Comment.objects.get().user, self.user)

    def test_list_is_public_and_filtered_by_tour(self):
        Comment.objects.create(user=self.user, tour=self.tour1, text="a")
        Comment.objects.create(user=self.user, tour=self.tour2, text="b")
        self.client.force_authenticate(None)
        r = self.client.get(f"{self.url}?tour={self.tour1.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([c["text"] for c in r.data], ["a"])


class MethodNotAllowedTest(BaseTest):
    """Через API нельзя менять то, что не предусмотрено"""

    def test_tours_read_only(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post("/api/tours/", {"title": "x", "price": 1}).status_code, 405)
        self.assertEqual(self.client.delete(f"/api/tours/{self.tour1.id}/").status_code, 405)

    def test_booking_cannot_be_edited(self):
        b = Booking.objects.create(user=self.user, tour=self.tour1, date=FUTURE, time=T10)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.patch(f"/api/bookings/{b.id}/", {"time": "11:00"}).status_code, 405)
        self.assertEqual(self.client.put(f"/api/bookings/{b.id}/", {}).status_code, 405)

    def test_comment_cannot_be_deleted_via_api(self):
        Booking.objects.create(user=self.user, tour=self.tour1, date=PAST, time=T10)
        c = Comment.objects.create(user=self.user, tour=self.tour1, text="x")
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.delete(f"/api/comments/{c.id}/").status_code, 405)