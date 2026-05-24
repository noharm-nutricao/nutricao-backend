"""Nutritional text utilities."""

import re
import unicodedata


def normalize_text(entry: str) -> str:
    """
    Normaliza texto para comparação de casos clínicos.
    Remove acentuação, converte para lowercase e remove pontuação.
    """
    if not entry:
        return ""

    # remove acentuação
    normalized = unicodedata.normalize("NFD", entry)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # lowercase
    normalized = normalized.lower()

    # remove pontuação
    normalized = re.sub(r"[:.!?,]", "", normalized)

    return normalized.strip()
