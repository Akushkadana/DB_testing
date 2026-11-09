from django.utils import timezone
from rest_framework import serializers
from .models import Tour, Category, Booking, Comment


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class TourSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)

    class Meta:
        model = Tour
        fields = ["id", "title", "description", "price", "guide", "categories"]


class BookingSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Booking
        fields = ["id", "user", "tour", "date", "time"]

    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Нельзя забронировать тур на прошедшую дату.")
        return value


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Comment
        fields = ["id", "user", "tour", "text", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        was_on_tour = Booking.objects.filter(
            user=attrs["user"],
            tour=attrs["tour"],
            date__lte=timezone.localdate(),
        ).exists()
        if not was_on_tour:
            raise serializers.ValidationError(
                "Комментировать можно только туры, в которых вы были."
            )
        return attrs