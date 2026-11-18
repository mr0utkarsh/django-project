from django.db import models


class Enquiry(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return f"{self.name} - {self.email}"


class SignupOTP(models.Model):
    email = models.EmailField(unique=True)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return f"Signup OTP for {self.email}"
