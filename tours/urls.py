from rest_framework.routers import DefaultRouter
from .views import TourViewSet, BookingViewSet, CommentViewSet

router = DefaultRouter()
router.register("tours", TourViewSet, basename="tour")
router.register("bookings", BookingViewSet, basename="booking")
router.register("comments", CommentViewSet, basename="comment")
urlpatterns = router.urls