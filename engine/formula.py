"""Safe evaluation of user formulas for parameters and amounts (no eval, whitelisted AST only).

Allowed: numbers, parameter names, + - * / ** %, parentheses, unary minus, and the functions
min, max, abs, round, sqrt, exp, log, log10, sin, cos, tan, pi, e, if_(cond, a, b) plus comparisons.
"""
import ast
import math
import keyword

FUNCS = {"min": min, "max": max, "abs": abs, "round": round, "sqrt": math.sqrt, "exp": math.exp,
         "log": math.log, "log10": math.log10, "sin": math.sin, "cos": math.cos, "tan": math.tan,
         "if_": lambda c, a, b: a if c else b}
CONSTS = {"pi": math.pi, "e": math.e}
RESERVED = set(FUNCS) | set(CONSTS)
_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b}
_CMP = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


class FormulaError(ValueError):
    pass


def valid_name(name):
    return bool(name) and name.isidentifier() and not keyword.iskeyword(name) and name not in RESERVED \
        and not name.startswith("_") and len(name) <= 60


def parse(text):
    text = str(text or "").strip().replace("^", "**")
    if not text:
        raise FormulaError("The formula is empty.")
    if len(text) > 500:
        raise FormulaError("The formula is too long.")
    try:
        return ast.parse(text, mode="eval")
    except SyntaxError:
        raise FormulaError(f"Cannot read the formula '{text}'. Check brackets and operators.")


def names_in(text):
    tree = parse(text)
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in RESERVED}


def evaluate(text, variables):
    tree = parse(text)

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in CONSTS:
                return CONSTS[node.id]
            if node.id in variables:
                return float(variables[node.id])
            raise FormulaError(f"Unknown parameter '{node.id}'.")
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(b) > 100:
                raise FormulaError("Exponent too large.")
            try:
                return _BIN[type(node.op)](a, b)
            except ZeroDivisionError:
                raise FormulaError("Division by zero in the formula.")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP:
            return 1.0 if _CMP[type(node.ops[0])](ev(node.left), ev(node.comparators[0])) else 0.0
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
            try:
                return float(FUNCS[node.func.id](*[ev(a) for a in node.args]))
            except (ValueError, TypeError, OverflowError) as e:
                raise FormulaError(f"{node.func.id}(): {e}")
        raise FormulaError("Only numbers, parameter names, + - * / ^, brackets and simple functions are allowed.")

    v = ev(tree)
    if not math.isfinite(v):
        raise FormulaError("The formula gives an infinite or undefined number.")
    return v


def resolve(params, overrides=None):
    """params: list of dicts {name, value, formula}. Returns {name: value} with formulas resolved in
    dependency order. overrides: {name: value} replaces a parameter's value (and its formula)."""
    overrides = overrides or {}
    by_name = {p["name"]: p for p in params}
    out, visiting = {}, set()

    def get(name):
        if name in out:
            return out[name]
        if name in overrides:
            out[name] = float(overrides[name])
            return out[name]
        p = by_name.get(name)
        if p is None:
            raise FormulaError(f"Unknown parameter '{name}'.")
        if name in visiting:
            raise FormulaError(f"Parameter '{name}' depends on itself.")
        if p.get("formula"):
            visiting.add(name)
            deps = {d: get(d) for d in names_in(p["formula"])}
            visiting.discard(name)
            out[name] = evaluate(p["formula"], deps)
        else:
            out[name] = float(p["value"] or 0.0)
        return out[name]

    for n in by_name:
        get(n)
    return out
