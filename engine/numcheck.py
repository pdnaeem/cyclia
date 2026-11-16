"""One validator for every number Cyclia reads, Cyclia 1.9.0 (named numcheck: "numbers" is a standard module).

A number that reaches a calculation must be a real, finite number. What is refused:
- NaN and infinity, also when written as text ("nan", "inf") or as a number too large for a float (1e309);
- booleans: in Python (and after JSON parsing) True is 1 and False is 0, so a flag sent in place of a number would
  pass as an amount, an identifier or a year;
- text that is not a number (a decimal comma is accepted where the caller says so);
- for whole numbers (identifiers, counts, years): values with a fraction, which int() would silently cut.

The API, the storage layer, the calculation modules and every importer use these functions, so that the same rule
holds on every path. Importers that must read a whole file use Reader, which counts the values it could not use and
reports them instead of replacing them silently.
"""
import contextlib
import contextvars
import functools
import math


class NotANumber(ValueError):
    """A value that is not an acceptable number. Subclass of ValueError, so existing handlers report it."""


def _raise(err, msg):
    raise (err or NotANumber)(msg)


def parse(v, comma=False):
    """The float of v, or None when v is not a real, finite number (booleans, NaN, infinity, text, None)."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, str):
        t = v.strip().replace(" ", "").replace(" ", "")
        if not t:
            return None
        if comma and "," in t and "." not in t:
            t = t.replace(",", ".")
        try:
            x = float(t)
        except ValueError:
            return None
    else:
        # numpy scalars and Decimals convert; anything else (lists, dicts) is not a number
        if hasattr(v, "dtype") and getattr(v.dtype, "kind", "") == "b":
            return None
        try:
            x = float(v)
        except (TypeError, ValueError, OverflowError):
            return None
    return x if math.isfinite(x) else None


def finite(v, what="The value", lo=None, hi=None, lo_open=False, hi_open=False, err=None, comma=False):
    """A finite number, optionally in [lo, hi] (or open bounds). Raises err (default NotANumber) otherwise."""
    if isinstance(v, bool):
        _raise(err, f"{what} must be a number, not a yes/no value ({v}).")
    x = parse(v, comma)
    if x is None:
        if v is None or (isinstance(v, str) and not v.strip()):
            _raise(err, f"{what} is required.")
        _raise(err, f"{what} must be a finite number{'' if isinstance(v, (int, float)) else f' (not {str(v)[:40]!r})'}.")
    if lo is not None and (x <= lo if lo_open else x < lo):
        _raise(err, f"{what} must be {'above' if lo_open else 'at least'} {lo:g}.")
    if hi is not None and (x >= hi if hi_open else x > hi):
        _raise(err, f"{what} must be {'below' if hi_open else 'at most'} {hi:g}.")
    return x


def optional(v, what="The value", default=None, **kw):
    """finite(), or default for an empty value (None or blank text)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return default
    return finite(v, what, **kw)


def integer(v, what="The value", lo=None, hi=None, err=None):
    """A whole number: 3, 3.0 and "3" are accepted; 2.5, True and "x" are refused (int() would cut or accept)."""
    x = finite(v, what, lo, hi, err=err)
    if not x.is_integer():
        _raise(err, f"{what} must be a whole number (not {v}).")
    return int(x)


def year(v, what="The year", lo=None, hi=None, err=None):
    """A calendar year: a whole number."""
    return integer(v, what, lo, hi, err)


def identifier(v, what="The identifier", err=None):
    """A database identifier: a whole number of at least 1."""
    return integer(v, what, 1, None, err)


class Reader:
    """Reads numbers from a file being imported. A value that is not a finite number is replaced by the default
    given by the importer (or left out when the default is None), and counted; message() reports the count, so the
    import result says how many values could not be used."""

    def __init__(self, comma=False):
        self.comma = comma
        self.bad = 0
        self.examples = []

    def num(self, v, default=None, where="", comma=None):
        if v is None or (isinstance(v, str) and not v.strip()):
            return default
        x = parse(v, self.comma if comma is None else comma)
        if x is None:
            self.bad += 1
            if len(self.examples) < 5:
                self.examples.append(f"{where}: {str(v)[:30]!r}" if where else repr(str(v)[:30]))
            return default
        return x

    def message(self):
        if not self.bad:
            return None
        return (f"{self.bad} value(s) in the files were not finite numbers (NaN, infinite, yes/no or text) and could "
                f"not be used; amounts were read as 0 and uncertainty was left out. Examples: "
                f"{'; '.join(self.examples)}.")


_active = contextvars.ContextVar("cyclia_numcheck_reader", default=None)


@contextlib.contextmanager
def reading(comma=False):
    """While a file is imported: every read() inside counts its unusable values in the yielded Reader."""
    r = Reader(comma)
    tok = _active.set(r)
    try:
        yield r
    finally:
        _active.reset(tok)


def read(v, default=None, where="", comma=False):
    """A number read from an imported file: the value, or `default` for a blank or unusable one (counted by the active
    Reader, so the import can report it)."""
    r = _active.get()
    if r is not None:
        return r.num(v, default, where, comma or None)
    if v is None or (isinstance(v, str) and not v.strip()):
        return default
    x = parse(v, comma)
    return default if x is None else x



def counted(comma=False):
    """Decorator for an import function: numbers read with read() inside it are counted, and when some could not be
    used the result dict gets a warning and "unusable_numbers"."""
    def deco(fn):
        @functools.wraps(fn)
        def run(*a, **k):
            with reading(comma) as r:
                res = fn(*a, **k)
            if r.bad and isinstance(res, dict):
                res.setdefault("warnings", []).append(r.message())
                res["unusable_numbers"] = res.get("unusable_numbers", 0) + r.bad
            return res
        return run
    return deco
