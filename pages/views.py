import secrets
import logging
import smtplib
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import EnquiryForm, OTPForm, SignupEmailForm, SignUpForm
from .models import SignupOTP


logger = logging.getLogger(__name__)


def home(request):
    return render(request, "pages/home.html")


def enquiry(request):
    form = EnquiryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Thanks! Your enquiry has been sent.")
        return redirect("enquiry")
    return render(request, "pages/enquiry.html", {"form": form})


def signup(request):
    verified_email = request.session.get("signup_verified_email")
    if not verified_email:
        form = SignupEmailForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            email = form.cleaned_data["email"]
            otp_record, _ = SignupOTP.objects.get_or_create(
                email=email,
                defaults={"code_hash": ""},
            )
            if (
                otp_record.code_hash
                and otp_record.created_at > timezone.now() - timedelta(seconds=60)
            ):
                request.session["signup_otp_email"] = email
                messages.info(request, "A code was just sent. Please check your email.")
                return redirect("verify_signup_otp")

            otp = f"{secrets.randbelow(1_000_000):06d}"
            otp_record.code_hash = make_password(otp)
            otp_record.created_at = timezone.now()
            otp_record.attempts = 0
            otp_record.save()

            if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
                logger.warning("Signup OTP email was not sent because email credentials are not configured.")
                otp_record.delete()
                messages.error(request, "Email is not configured, so we could not send your verification code.")
                return render(request, "registration/signup.html", {"form": form})

            try:
                send_mail(
                    "Your SimpleSite verification code",
                    f"Your signup verification code is {otp}. It expires in 10 minutes.",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except (OSError, smtplib.SMTPException):
                logger.exception("Could not send signup verification email.")
                otp_record.delete()
                messages.error(request, "We could not send your verification code. Please try again.")
                return render(request, "registration/signup.html", {"form": form})

            request.session["signup_otp_email"] = email
            messages.success(request, f"We sent a verification code to {email}.")
            return redirect("verify_signup_otp")

        return render(request, "registration/signup.html", {"form": form})

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.email = verified_email
        user.save()
        SignupOTP.objects.filter(email=verified_email).delete()
        request.session.pop("signup_verified_email", None)
        request.session.pop("signup_otp_email", None)
        login(request, user)
        if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
            logger.warning("Welcome email was not sent because email credentials are not configured.")
            messages.warning(
                request,
                f"Welcome, {user.username}! Your account is ready, but email is not configured.",
            )
        else:
            try:
                send_mail(
                    "Welcome to SimpleSite",
                    f"Welcome, {user.username}! Your account has been created successfully.",
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
            except (OSError, smtplib.SMTPException):
                logger.exception("Could not send welcome email to the new user.")
                messages.warning(
                    request,
                    f"Welcome, {user.username}! Your account is ready, but we could not send the email.",
                )
            else:
                messages.success(
                    request,
                    f"Welcome, {user.username}! A welcome email has been sent to {user.email}.",
                )
        return redirect("home")
    return render(
        request,
        "registration/signup.html",
        {"form": form, "verified_email": verified_email},
    )


def verify_signup_otp(request):
    email = request.session.get("signup_otp_email")
    if not email:
        messages.info(request, "Enter your email address to start signup.")
        return redirect("signup")

    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            otp_record = SignupOTP.objects.get(email=email)
        except SignupOTP.DoesNotExist:
            messages.error(request, "Your code is no longer available. Request a new one.")
            request.session.pop("signup_otp_email", None)
            return redirect("signup")

        if otp_record.created_at <= timezone.now() - timedelta(minutes=10):
            otp_record.delete()
            request.session.pop("signup_otp_email", None)
            messages.error(request, "Your code has expired. Request a new one.")
            return redirect("signup")

        if otp_record.attempts >= 5:
            otp_record.delete()
            request.session.pop("signup_otp_email", None)
            messages.error(request, "Too many incorrect attempts. Request a new code.")
            return redirect("signup")

        if not check_password(form.cleaned_data["code"], otp_record.code_hash):
            otp_record.attempts += 1
            otp_record.save(update_fields=["attempts"])
            messages.error(request, "That code is incorrect. Please try again.")
            return render(request, "registration/verify_otp.html", {"form": form, "email": email})

        request.session["signup_verified_email"] = email
        request.session.pop("signup_otp_email", None)
        return redirect("signup")

    return render(request, "registration/verify_otp.html", {"form": form, "email": email})
