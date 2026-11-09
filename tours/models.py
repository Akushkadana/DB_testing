from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """1 к 1: у пользователя один профиль"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"Профиль {self.user}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


class Guide(models.Model):
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    """Например: конный, пеший, мото"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Tour(models.Model):
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    # 1 ко многим: один гид -> много туров
    guide = models.ForeignKey(Guide, on_delete=models.PROTECT, related_name="tours")
    # многие ко многим: тур в нескольких категориях и наоборот
    categories = models.ManyToManyField(Category, related_name="tours")

    def __str__(self):
        return self.title


class Booking(models.Model):
    # 1 ко многим: пользователь -> много бронирований
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name="bookings")
    date = models.DateField()
    time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # 1 человек = 1 тур на конкретные дату и время
            models.UniqueConstraint(
                fields=["user", "date", "time"], name="one_tour_per_user_per_slot"
            )
        ]


class Comment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name="comments")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)