"""Evaluate a deliberately tiny numeric-expression subset, never Python exec/eval."""
import ast
import math
import operator
import re


def number(value):
    if type(value) not in (int,float,bool) or abs(value)>1e12 or not math.isfinite(value):
        raise ValueError('Only finite bounded scalar numbers are supported')
    return value


def specifications(tests):
    if not isinstance(tests,list) or len(tests)>5:raise ValueError('Use up to five function test cases')
    for t in tests:
        if not isinstance(t,dict) or set(t)!={'function','args','expected'} or not isinstance(t['function'],str) or not re.fullmatch(r'[A-Za-z_]\w{0,50}',t['function']):raise ValueError('Each test needs function, args and expected')
        if not isinstance(t['args'],list) or len(t['args'])>4:raise ValueError('Tests support up to four scalar arguments')
        for value in [*t['args'],t['expected']]:number(value)
    return tests


def check(content,tests):
    specifications(tests)
    tree=ast.parse(content)
    if len(list(ast.walk(tree)))>200:raise ValueError('Function test syntax budget exceeded')
    functions={}
    for node in tree.body:
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):continue
        if not isinstance(node,ast.FunctionDef) or node.decorator_list:raise ValueError('Only undecorated pure functions and docstrings are testable')
        functions[node.name]=node
    def expression(node,env):
        if isinstance(node,ast.Constant):return number(node.value)
        if isinstance(node,ast.Name) and node.id in env:return env[node.id]
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd,ast.Not)):
            v=expression(node.operand,env);return number(-v if isinstance(node.op,ast.USub) else not v if isinstance(node.op,ast.Not) else v)
        if isinstance(node,ast.BinOp):
            a,b=expression(node.left,env),expression(node.right,env)
            ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod}
            if isinstance(node.op,ast.Pow):
                if abs(b)>12:raise ValueError('Exponent exceeds test limit')
                return number(a**b)
            if type(node.op) in ops:return number(ops[type(node.op)](a,b))
        if isinstance(node,ast.IfExp):return expression(node.body if expression(node.test,env) else node.orelse,env)
        if isinstance(node,ast.Compare):
            ops={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge}
            left=expression(node.left,env)
            for op,rightnode in zip(node.ops,node.comparators):
                if type(op) not in ops:raise ValueError('Unsupported comparison')
                right=expression(rightnode,env)
                if not ops[type(op)](left,right):return False
                left=right
            return True
        raise ValueError('Unsupported expression: no calls, loops, imports, attributes or side effects')
    results=[]
    for t in tests:
        f=functions.get(t['function'])
        if f is None:raise ValueError('Test function not found')
        args=f.args
        if args.defaults or args.kwonlyargs or args.vararg or args.kwarg or args.posonlyargs:raise ValueError('Only simple positional parameters are supported')
        if len(args.args)!=len(t['args']):raise ValueError('Test argument count mismatch')
        body=[n for n in f.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))]
        if len(body)!=1 or not isinstance(body[0],ast.Return):raise ValueError('Only a single-return numeric function is supported')
        actual=expression(body[0].value,dict(zip([a.arg for a in args.args],t['args'])))
        results.append({'check':t['function']+'('+str(t['args'])+')','passed':math.isclose(actual,t['expected'],rel_tol=1e-9,abs_tol=1e-12),'actual':actual,'expected':t['expected']})
    return results
