"""
Custom password validators for Lite Hosting Panel.
"""
from django.core.exceptions import ValidationError


class PasswordComplexityValidator:
    """
    Enforces password complexity:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character from: !@#$%^&*()_+-=[]{}|;:,.<>?
    """

    SPECIAL_CHARS = set('!@#$%^&*()_+-=[]{}|;:,.<>?')

    def validate(self, password, user=None):
        errors = []

        if len(password) < 12:
            errors.append(
                ValidationError(
                    'Password must be at least 12 characters long.',
                    code='password_too_short',
                )
            )

        if not any(c.isupper() for c in password):
            errors.append(
                ValidationError(
                    'Password must contain at least one uppercase letter.',
                    code='password_no_upper',
                )
            )

        if not any(c.islower() for c in password):
            errors.append(
                ValidationError(
                    'Password must contain at least one lowercase letter.',
                    code='password_no_lower',
                )
            )

        if not any(c.isdigit() for c in password):
            errors.append(
                ValidationError(
                    'Password must contain at least one digit.',
                    code='password_no_digit',
                )
            )

        if not any(c in self.SPECIAL_CHARS for c in password):
            errors.append(
                ValidationError(
                    'Password must contain at least one special character '
                    '(!@#$%^&*()_+-=[]{}|;:,.<>?).',
                    code='password_no_special',
                )
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            'Your password must be at least 12 characters long and contain: '
            'an uppercase letter, a lowercase letter, a digit, and a special '
            'character (!@#$%^&*()_+-=[]{}|;:,.<>?).'
        )
