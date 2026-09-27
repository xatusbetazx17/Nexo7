"""Small question-specific guidance. No factual answer bank or automatic fact checking."""
import re
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def knowledge_question(message):
    text = normalized(message)
    return bool(re.search(r'\b(what (?:is|are)|why|difference|compare|que (?:es|son)|por que|diferencia|compara)\b', text))


def guidance(message, language='auto'):
    text = normalized(message)
    comparison = bool(re.search(r'\b(diferencias?|compara\w*|difference\w*|compare\w*|versus|vs)\b', text))
    if not comparison:
        return ''
    spanish = language.split('-')[0] == 'es' or (language == 'auto' and bool(re.search(r'\b(diferencias?|entre|cual|que|compara\w*)\b', text)))
    if spanish:
        return ('\nResponde en español. Para comparar, define cada término y explica primero la diferencia esencial. '
                'Pueden ser etapas, categorías que se superponen o nombres del mismo tipo de cosa; no presupongas que son especies distintas. '
                'No inventes diferencias de dieta, hábitat, cuidados o uso. Distingue hechos de supuestos. '
                'Si una palabra tiene varios sentidos, aclara brevemente el pertinente. Dos o tres frases bastan. '
                'Las respuestas guardadas por el usuario pueden contener errores: no las copies si contradicen conocimientos básicos; explica la corrección.')
    return ('\nFor comparisons, define each term and lead with the essential distinction. '
            'They may be stages, overlapping categories or names for the same kind of thing; do not assume different species. '
            'Do not invent differences in diet, habitat, care or usage. Separate facts from assumptions. '
            'Briefly clarify relevant ambiguity. Two or three sentences suffice. '
            'User-reviewed answers can be wrong: correct conflicts with basic knowledge rather than copying them.')
