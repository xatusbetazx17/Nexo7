"""Hypothetical intent and explicit toy calculations, independent of model weights."""
import math
import re
import unicodedata


def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))


def hypothetical(text):
    text = folded(text)
    return bool(re.search(r'\b(imagin(?:e|ary|ation|a|ar|ario|aria|acion|ate|emos)|hypothetical|hipotetic[oa]|suppose|supongamos|what (?:would|could) happen if|what if|que pasaria si|pretend)\b', text))


def explicit_lookup(text):
    return bool(re.search(r'\b(search (?:online|the (?:web|internet))|look (?:it |this )?up|verify online|busca(?:r)? en (?:internet|la web)|verifica en internet)\b', folded(text)))


INSTRUCTIONS = """You are Nexo, a helpful assistant discussing an imagined scenario, not reporting an actual event.
Understand obvious typos. State your interpretation if a word has multiple meanings.
Explain a plausible outcome briefly. Separate what the user gave, assumptions, and unknowns.
For impossible cartoon premises, describe the fictional outcome and distinguish real-world physics.
Do not claim to predict injuries, collision damage or a repair bill from an incomplete story.
For numerical results ask for missing quantities, or label any invented quantities as toy assumptions.
The optional What-if calculator can calculate projectile motion and a cost subtotal from explicit inputs.
Never claim a numerical answer was checked by a tool unless a tool result is supplied.
Do not browse, invent sources, execute actions or expose secrets. Give a useful answer, not internal reasoning.
Use everyday language, about 100 words unless more detail is requested."""


def value(body, key, low, high):
    x = body.get(key)
    if type(x) not in (int, float) or not low <= x <= high or not math.isfinite(x):
        raise ValueError(f'{key} must be a finite number between {low} and {high}')
    return float(x)


def calculate(body):
    """No impact/injury model or market pricing. Output assumptions with every result."""
    if not isinstance(body, dict):
        raise ValueError('Scenario input must be a JSON object')
    kind = body.get('kind')
    if kind == 'flight':
        speed = value(body, 'speed_m_s', 0, 1000)
        angle = value(body, 'angle_degrees', -90, 90)
        height = value(body, 'height_m', 0, 10000)
        theta = math.radians(angle)
        vx, vy = speed * math.cos(theta), speed * math.sin(theta)
        gravity = 9.81
        root = math.sqrt(vy*vy + 2*gravity*height)
        # Stable form for downward initial velocity at low starting heights.
        seconds = 2*height/(root-vy) if vy < 0 else (vy+root)/gravity
        result = {'flight_seconds': round(seconds, 4), 'horizontal_distance_m': round(vx*seconds, 4),
                  'maximum_height_m': round(height + max(0, vy)**2/(2*gravity), 4)}
        assumptions = ['Initial launch speed is supplied; it is NOT inferred from truck speed or a collision.',
                       'Point object; constant gravity 9.81 m/s²; no air drag; landing ground at height zero.',
                       'Does not predict injuries, vehicle damage or what an actual collision would do.']
        formulas = ['vx = v cos(angle); vy = v sin(angle)', 'height + vy*t - 9.81*t²/2 = 0; distance = vx*t']
    elif kind == 'cost':
        from decimal import Decimal, localcontext, ROUND_HALF_UP
        for key in ('area_m2', 'rate_per_m2', 'labor_hours', 'hourly_rate', 'materials'):
            value(body, key, 0, 1_000_000)
        with localcontext() as context:
            context.prec = 40
            d = lambda key: Decimal(str(body[key]))
            paint = d('area_m2') * d('rate_per_m2')
            labor = d('labor_hours') * d('hourly_rate')
            amount = lambda x: str(x.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
            result = {'paint': amount(paint), 'labor': amount(labor), 'materials': amount(d('materials')),
                      'subtotal': amount(paint + labor + d('materials'))}
        assumptions = ['All rates and quantities come from your inputs, in one currency.',
                       'This subtotal is not a market quote. Taxes, damage assessment and unlisted work are excluded.',
                       'Use a paint rate excluding the labor/material costs entered separately to avoid double counting.']
        formulas = ['subtotal = area × paint rate + labor hours × hourly rate + materials']
    else:
        raise ValueError('Choose flight or cost')
    return {'kind': kind, 'inputs': body, 'result': result, 'assumptions': assumptions, 'formulas': formulas,
            'model_calls': 0, 'network_requests': 0}
