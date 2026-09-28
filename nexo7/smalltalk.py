"""Exact, bounded social replies; no factual knowledge or model reasoning is simulated."""
import re
from .answer_guidance import normalized


def reply(message, language='auto'):
    text = re.sub(r'[^\w\s]', ' ', normalized(message))
    text = ' '.join(text.split())
    spanish = {'hola', 'buenos dias', 'buenas tardes', 'buenas noches', 'como estas',
               'hola como estas', 'que tal', 'hola que tal'}
    english = {'hi', 'hello', 'hey', 'how are you', 'hello how are you', 'hi how are you',
               'good morning', 'good afternoon', 'good evening'}
    if text not in spanish | english:
        return None  # Never swallow a task appended to a greeting.
    target = ('es' if text in spanish else 'en') if language == 'auto' else language.split('-')[0]
    if target == 'es':
        return '¡Hola! Estoy aquí, listo para ayudarte. ¿Cómo estás tú?'
    if target == 'en':
        return "Hello! I'm here and ready to help. How are you?"
    return None
