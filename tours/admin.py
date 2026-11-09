from django.contrib import admin
from .models import Profile, Guide, Category, Tour, Booking, Comment

for m in (Profile, Guide, Category, Tour, Booking, Comment):
    admin.site.register(m)