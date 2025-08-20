from datetime import timedelta
import random
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import EmailVerificationCode, User


class EmailService:
    """
    Serviço responsável por gerar códigos, persistir e enviar e-mails HTML.
    """

    DEFAULT_EXPIRATION_MINUTES = 15

    @staticmethod
    def _generate_six_digit_code() -> str:
        return f"{random.randint(100000, 999999)}"

    @classmethod
    def create_and_send_code(cls, *, user: User, code_type: str) -> EmailVerificationCode:
        # invalida códigos anteriores não usados do mesmo tipo
        EmailVerificationCode.objects.filter(user=user, code_type=code_type, is_used=False).update(is_used=True)

        code = cls._generate_six_digit_code()
        expires_at = timezone.now() + timedelta(minutes=cls.DEFAULT_EXPIRATION_MINUTES)

        verification = EmailVerificationCode.objects.create(
            user=user,
            code=code,
            code_type=code_type,
            expires_at=expires_at,
        )

        # envia e-mail em HTML
        subject = (
            "Confirme seu e-mail - SmartStrategy" if code_type == "registration" else "Código para redefinir sua senha - SmartStrategy"
        )

        context = {
            "user": user,
            "code": code,
            "expires_minutes": cls.DEFAULT_EXPIRATION_MINUTES,
            "code_type": code_type,
        }

        html_message = render_to_string("accounts/emails/codigo_verificacao.html", context)
        plain_message = (
            f"Seu código de verificação é {code}. Ele expira em {cls.DEFAULT_EXPIRATION_MINUTES} minutos."
        )

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)

        # Envia e-mail simples (sem anexos/inline) para evitar mostrar arquivos na caixa de entrada
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return verification

    @staticmethod
    def verify_code(*, user: User, code: str, code_type: str, mark_used: bool = True) -> bool:
        try:
            record = EmailVerificationCode.objects.get(
                user=user, code=code, code_type=code_type, is_used=False
            )
        except EmailVerificationCode.DoesNotExist:
            return False

        if record.expires_at < timezone.now():
            return False

        if mark_used:
            record.is_used = True
            record.save(update_fields=["is_used"])
        return True


