from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly

from .models import Booking, Comment, Tour
from .serializers import BookingSerializer, CommentSerializer, TourSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Список туров",
        description="Фильтр по категории: ?category=horse | hike | moto",
    ),
    retrieve=extend_schema(summary="Один тур"),
)
class TourViewSet(viewsets.ReadOnlyModelViewSet):
    """Список туров. Фильтр: ?category=horse"""
    serializer_class = TourSerializer

    def get_queryset(self):
        qs = Tour.objects.prefetch_related("categories")
        category = self.request.query_params.get("category")
        return qs.filter(categories__slug=category) if category else qs


@extend_schema_view(
    list=extend_schema(summary="Мои бронирования"),
    create=extend_schema(
        summary="Забронировать тур",
        description="Один пользователь не может иметь два тура на одну дату и время. Дата не в прошлом.",
    ),
    destroy=extend_schema(summary="Отменить бронирование"),
)
class BookingViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                     mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Бронирования текущего пользователя"""
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="Комментарии", description="Фильтр: ?tour=<id тура>"),
    create=extend_schema(
        summary="Оставить комментарий",
        description="Только к турам, в которых пользователь уже был.",
    ),
)
class CommentViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """Комментарии к турам"""
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Comment.objects.all()
        tour = self.request.query_params.get("tour")
        return qs.filter(tour_id=tour) if tour else qs