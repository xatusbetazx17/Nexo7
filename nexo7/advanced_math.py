"""Bounded Decimal tools; no eval, model generation, network or symbolic execution."""
from decimal import Decimal, InvalidOperation, localcontext


def number(value):
    if type(value) not in (str, int, float) or len(str(value)) > 100:
        raise ValueError('Use numeric values or decimal strings of at most 100 characters')
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid decimal number') from None
    if not n.is_finite() or n.copy_abs() > Decimal('1e50') or not -50 <= n.as_tuple().exponent <= 50:
        raise ValueError('Number outside supported range')
    return n


def solve(request):
    if not isinstance(request, dict):
        raise ValueError('/math expects a JSON object')
    with localcontext() as ctx:
        ctx.prec = 50
        operation = request.get('operation')
        if operation == 'linear':
            matrix, vector = request.get('matrix'), request.get('vector')
            if not isinstance(matrix, list) or not 1 <= len(matrix) <= 8 or not isinstance(vector, list) or len(vector) != len(matrix):
                raise ValueError('Use a square matrix and vector with 1–8 rows')
            n = len(matrix)
            if any(not isinstance(row, list) or len(row) != n for row in matrix):
                raise ValueError('Matrix must be square')
            a = [[number(x) for x in row] for row in matrix]; b = [number(x) for x in vector]
            work = [row[:] + [v] for row, v in zip(a, b)]
            for column in range(n):
                pivot = max(range(column, n), key=lambda i: abs(work[i][column]))
                if not work[pivot][column]:
                    raise ValueError('Singular system: a unique solution could not be established')
                work[column], work[pivot] = work[pivot], work[column]
                scale = work[column][column]
                work[column] = [v / scale for v in work[column]]
                for row in range(n):
                    if row != column:
                        scale = work[row][column]
                        work[row] = [x-scale*y for x, y in zip(work[row], work[column])]
            solution = [row[-1] for row in work]
            residual = max(abs(sum(x*y for x,y in zip(row, solution))-v) for row,v in zip(a,b))
            result = {'solution': list(map(str, solution)), 'maximum_absolute_residual': str(residual),
                      'check': 'Substituted into original equations; small residual alone does not prove accuracy for an ill-conditioned system.'}
        elif operation == 'quadratic':
            a, b, c = [number(request.get(k)) for k in ('a', 'b', 'c')]
            if not a:
                raise ValueError('Quadratic coefficient a must be nonzero')
            discriminant = b*b-4*a*c
            if discriminant < 0:
                result = {'roots': [{'real': str(-b/(2*a)), 'imaginary': str(sign*(-discriminant).sqrt()/(2*abs(a)))} for sign in (1,-1)]}
            else:
                # Stable form avoids cancellation when b and sqrt(discriminant) nearly match.
                q = -(b + (discriminant.sqrt() if b >= 0 else -discriminant.sqrt()))/2
                roots = [q/a, c/q] if q else [Decimal(0), Decimal(0)]
                result = {'roots': list(map(str, roots)), 'maximum_absolute_residual': str(max(abs(a*x*x+b*x+c) for x in roots))}
        elif operation == 'statistics':
            values = request.get('values')
            if not isinstance(values, list) or not 1 <= len(values) <= 500:
                raise ValueError('Use 1–500 values')
            values = [number(v) for v in values]
            mean = sum(values)/len(values)
            variance = sum((x-mean)**2 for x in values)/len(values)
            result = {'count': len(values), 'sum': str(sum(values)), 'mean': str(mean),
                      'population_variance': str(variance), 'population_standard_deviation': str(variance.sqrt())}
        else:
            raise ValueError('Supported operations: linear, quadratic, statistics')
        return {'operation': operation, 'precision_digits': 50, 'result': result,
                'limitations': 'Rounded Decimal arithmetic, not a general symbolic proof or numerical-stability guarantee.'}
