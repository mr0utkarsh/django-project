import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from .models import Enquiry, SignupOTP


class WebsiteTests(TestCase):
    def test_enquiry_is_saved(self):
        response = self.client.post(
            reverse("enquiry"),
            {
                "name": "Asha",
                "email": "asha@example.com",
                "phone": "1234567890",
                "message": "Please contact me.",
            },
        )

        self.assertRedirects(response, reverse("enquiry"))
        self.assertEqual(Enquiry.objects.count(), 1)
        self.assertEqual(Enquiry.objects.get().email, "asha@example.com")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="hello@example.com",
    )
    def test_signup_requires_email_otp_before_creating_user(self):
        response = self.client.post(
            reverse("signup"),
            {"email": "asha@example.com"},
        )

        self.assertRedirects(response, reverse("verify_signup_otp"))
        self.assertFalse(User.objects.filter(username="asha").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["asha@example.com"])
        otp = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        self.assertNotEqual(SignupOTP.objects.get().code_hash, otp)

        response = self.client.post(reverse("verify_signup_otp"), {"code": otp})
        self.assertRedirects(response, reverse("signup"))
        self.assertFalse(User.objects.filter(email="asha@example.com").exists())

        response = self.client.post(
            reverse("signup"),
            {
                "username": "asha",
                "password1": "StrongPass!234",
                "password2": "StrongPass!234",
            },
            follow=True,
        )

        self.assertContains(response, "Welcome, asha!")
        self.assertTrue(User.objects.filter(username="asha", email="asha@example.com").exists())
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(SignupOTP.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, ["asha@example.com"])
        self.assertIn("Welcome, asha!", mail.outbox[1].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_invalid_otp_does_not_create_user(self):
        self.client.post(reverse("signup"), {"email": "asha@example.com"})
        response = self.client.post(reverse("verify_signup_otp"), {"code": "000000"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "incorrect")
        self.assertFalse(User.objects.filter(email="asha@example.com").exists())
        self.assertEqual(SignupOTP.objects.get().attempts, 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_expired_otp_cannot_verify(self):
        self.client.post(reverse("signup"), {"email": "asha@example.com"})
        otp_record = SignupOTP.objects.get()
        SignupOTP.objects.filter(pk=otp_record.pk).update(
            created_at=timezone.now() - timedelta(minutes=11)
        )

        response = self.client.post(reverse("verify_signup_otp"), {"code": "123456"})

        self.assertRedirects(response, reverse("signup"))
        self.assertFalse(SignupOTP.objects.filter(email="asha@example.com").exists())
        self.assertFalse(User.objects.filter(email="asha@example.com").exists())
