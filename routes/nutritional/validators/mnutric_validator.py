from exception.validation_error import ValidationError
from utils import status


class MnutricValidator:
    """Validador para scores manuais APACHE II e SOFA"""

    @staticmethod
    def raise_invalid_manual_scores():
        raise ValidationError(
            "Valores inválidos para APACHE II ou SOFA",
            "errors.invalidRequest",
            status.HTTP_400_BAD_REQUEST,
        )

    @staticmethod
    def validate_required_manual_score(data, field_name, minimum):
        if not isinstance(data, dict):
            MnutricValidator.raise_invalid_manual_scores()

        if field_name not in data:
            MnutricValidator.raise_invalid_manual_scores()

        value = data[field_name]

        if value is None:
            MnutricValidator.raise_invalid_manual_scores()

        if isinstance(value, bool) or not isinstance(value, int):
            MnutricValidator.raise_invalid_manual_scores()

        if value < minimum:
            MnutricValidator.raise_invalid_manual_scores()

        return value

