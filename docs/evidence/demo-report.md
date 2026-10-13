# PatchPilot: CSV upload fails when a row contains an empty date

Status: **fixed**

Execution: local; elapsed: 2.165s

Tokens: 0 input, 0 output

Estimated API cost: not configured

## Evidence

### baseline_tests

1 passed, 2 failed, 0 errors (exit 1)

```text
.FF                                                                      [100%]
=================================== FAILURES ===================================
________________________ test_parse_row_with_empty_date ________________________

    def test_parse_row_with_empty_date():
        """This is the case from the reported issue: empty date should not crash."""
        row = {"name": "Bob", "amount": "50", "date": ""}
>       result = parse_row(row)
                 ^^^^^^^^^^^^^^

tests/test_csv_parser.py:15: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
csv_parser.py:20: in parse_row
    date = datetime.strptime(date_str, "%Y-%m-%d")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/_strptime.py:815: in _strptime_datetime_datetime
    tt, fraction, gmtoff_fraction = _strptime(data_string, format)
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

data_string = '', format = '%Y-%m-%d'

    def _strptime(data_string, format="%a %b %d %H:%M:%S %Y"):
        """Return a 2-tuple consisting of a time struct and an int containing
        the number of microseconds based on the input string and the
        format string."""
    
        for index, arg in enumerate([data_string, format]):
            if not isinstance(arg, str):
                msg = "strptime() argument {} must be str, not {}"
                raise TypeError(msg.format(index, type(arg)))
    
        global _TimeRE_cache, _regex_cache
        with _cache_lock:
            locale_time = _TimeRE_cache.locale_time
            if (_getlang() != locale_time.lang or
                time.tzname != locale_time.tzname or
                time.daylight != locale_time.daylight):
                _TimeRE_cache = TimeRE()
                _regex_cache.clear()
                locale_time = _TimeRE_cache.locale_time
            if len(_regex_cache) > _CACHE_MAX_SIZE:
                _regex_cache.clear()
            format_regex = _regex_cache.get(format)
            if not format_regex:
                try:
                    format_regex = _TimeRE_cache.compile(format)
                # KeyError raised when a bad format is found; can be specified as
                # \\, in which case it was a stray % but with a space after it
                except KeyError as err:
                    bad_directive = err.args[0]
                    del err
                    bad_directive = bad_directive.replace('\\s', '')
                    if not bad_directive:
                        raise ValueError("stray %% in format '%s'" % format) from None
                    bad_directive = bad_directive.replace('\\', '', 1)
                    raise ValueError("'%s' is a bad directive in format '%s'" %
                                        (bad_directive, format)) from None
                _regex_cache[format] = format_regex
        found = format_regex.match(data_string)
        if not found:
>           raise ValueError("time data %r does not match format %r" %
                             (data_string, format))
E           ValueError: time data '' does not match format '%Y-%m-%d'

/usr/local/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/_strptime.py:555: ValueError
____________________________ test_parse_rows_mixed _____________________________

    def test_parse_rows_mixed():
        rows = [
            {"name": "Alice", "amount": "10", "date": "2024-02-01"},
            {"name": "Bob", "amount": "20", "date": ""},
        ]
>       parsed = parse_rows(rows)
                 ^^^^^^^^^^^^^^^^

tests/test_csv_parser.py:25: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
csv_parser.py:27: in parse_rows
    return [parse_row(row) for row in rows]
            ^^^^^^^^^^^^^^
csv_parser.py:20: in parse_row
    date = datetime.strptime(date_str, "%Y-%m-%d")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/_strptime.py:815: in _strptime_datetime_datetime
    tt, fraction, gmtoff_fraction = _strptime(data_string, format)
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

data_string = '', format = '%Y-%m-%d'

    def _strptime(data_string, format="%a %b %d %H:%M:%S %Y"):
        """Return a 2-tuple consisting of a time struct and an int containing
        the number of microseconds based on the input string and the
        format string."""
    
        for index, arg in enumerate([data_string, format]):
            if not isinstance(arg, str):
                msg = "strptime() argument {} must be str, not {}"
                raise TypeError(msg.format(index, type(arg)))
    
        global _TimeRE_cache, _regex_cache
        with _cache_lock:
            locale_time = _TimeRE_cache.locale_time
            if (_getlang() != locale_time.lang or
                time.tzname != locale_time.tzname or
                time.daylight != locale_time.daylight):
                _TimeRE_cache = TimeRE()
                _regex_cache.clear()
                locale_time = _TimeRE_cache.locale_time
            if len(_regex_cache) > _CACHE_MAX_SIZE:
                _regex_cache.clear()
            format_regex = _regex_cache.get(format)
            if not format_regex:
                try:
                    format_regex = _TimeRE_cache.compile(format)
                # KeyError raised when a bad format is found; can be specified as
                # \\, in which case it was a stray % but with a space after it
                except KeyError as err:
                    bad_directive = err.args[0]
                    del err
                    bad_directive = bad_directive.replace('\\s', '')
                    if not bad_directive:
                        raise ValueError("stray %% in format '%s'" % format) from None
                    bad_directive = bad_directive.replace('\\', '', 1)
                    raise ValueError("'%s' is a bad directive in format '%s'" %
                                        (bad_directive, format)) from None
                _regex_cache[format] = format_regex
        found = format_regex.match(data_string)
        if not found:
>           raise ValueError("time data %r does not match format %r" %
                             (data_string, format))
E           ValueError: time data '' does not match format '%Y-%m-%d'

/usr/local/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/_strptime.py:555: ValueError
=========================== short test summary info ============================
FAILED tests/test_csv_parser.py::test_parse_row_with_empty_date - ValueError:...
FAILED tests/test_csv_parser.py::test_parse_rows_mixed - ValueError: time dat...
2 failed, 1 passed in 0.11s


```

### regression_before

0 passed, 2 failed, 0 errors (exit 1)

```text
FF                                                                       [100%]
=================================== FAILURES ===================================
_______________________ test_missing_date_does_not_crash _______________________

    def test_missing_date_does_not_crash():
>       assert parse_row({'name': 'Bob', 'date': '', 'amount': '5'})['date'] is None
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_patchpilot_regression.py:4: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
csv_parser.py:20: in parse_row
    date = datetime.strptime(date_str, "%Y-%m-%d")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/_strptime.py:815: in _strptime_datetime_datetime
    tt, fraction, gmtoff_fraction = _strptime(data_string, format)
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

data_string = '', format = '%Y-%m-%d'

    def _strptime(data_string, format="%a %b %d %H:%M:%S %Y"):
        """Return a 2-tuple consisting of a time struct and an int containing
        the number of microseconds based on the input string and the
        format string."""
    
        for index, arg in enumerate([data_string, format]):
            if not isinstance(arg, str):
                msg = "strptime() argument {} must be str, not {}"
                raise TypeError(msg.format(index, type(arg)))
    
        global _TimeRE_cache, _regex_cache
        with _cache_lock:
            locale_time = _TimeRE_cache.locale_time
            if (_getlang() != locale_time.lang or
                time.tzname != locale_time.tzname or
                time.daylight != locale_time.daylight):
                _TimeRE_cache = TimeRE()
                _regex_cache.clear()
                locale_time = _TimeRE_cache.locale_time
            if len(_regex_cache) > _CACHE_MAX_SIZE:
                _regex_cache.clear()
            format_regex = _regex_cache.get(format)
            if not format_regex:
                try:
                    format_regex = _TimeRE_cache.compile(format)
                # KeyError raised when a bad format is found; can be specified as
                # \\, in which case it was a stray % but with a space after it
                except KeyError as err:
                    bad_directive = err.args[0]
                    del err
                    bad_directive = bad_directive.replace('\\s', '')
                    if not bad_directive:
                        raise ValueError("stray %% in format '%s'" % format) from None
                    bad_directive = bad_directive.replace('\\', '', 1)
                    raise ValueError("'%s' is a bad directive in format '%s'" %
                                        (bad_directive, format)) from None
                _regex_cache[format] = format_regex
        found = format_regex.match(data_string)
        if not found:
>           raise ValueError("time data %r does not match format %r" %
                             (data_string, format))
E           ValueError: time data '' does not match format '%Y-%m-%d'

/usr/local/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/_strptime.py:555: ValueError
_____________________ test_whitespace_date_does_not_crash ______________________

    def test_whitespace_date_does_not_crash():
>       assert parse_row({'name': 'Bob', 'date': '   ', 'amount': '5'})['date'] is None
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

test_patchpilot_regression.py:7: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
csv_parser.py:20: in parse_row
    date = datetime.strptime(date_str, "%Y-%m-%d")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/_strptime.py:815: in _strptime_datetime_datetime
    tt, fraction, gmtoff_fraction = _strptime(data_string, format)
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

data_string = '   ', format = '%Y-%m-%d'

    def _strptime(data_string, format="%a %b %d %H:%M:%S %Y"):
        """Return a 2-tuple consisting of a time struct and an int containing
        the number of microseconds based on the input string and the
        format string."""
    
        for index, arg in enumerate([data_string, format]):
            if not isinstance(arg, str):
                msg = "strptime() argument {} must be str, not {}"
                raise TypeError(msg.format(index, type(arg)))
    
        global _TimeRE_cache, _regex_cache
        with _cache_lock:
            locale_time = _TimeRE_cache.locale_time
            if (_getlang() != locale_time.lang or
                time.tzname != locale_time.tzname or
                time.daylight != locale_time.daylight):
                _TimeRE_cache = TimeRE()
                _regex_cache.clear()
                locale_time = _TimeRE_cache.locale_time
            if len(_regex_cache) > _CACHE_MAX_SIZE:
                _regex_cache.clear()
            format_regex = _regex_cache.get(format)
            if not format_regex:
                try:
                    format_regex = _TimeRE_cache.compile(format)
                # KeyError raised when a bad format is found; can be specified as
                # \\, in which case it was a stray % but with a space after it
                except KeyError as err:
                    bad_directive = err.args[0]
                    del err
                    bad_directive = bad_directive.replace('\\s', '')
                    if not bad_directive:
                        raise ValueError("stray %% in format '%s'" % format) from None
                    bad_directive = bad_directive.replace('\\', '', 1)
                    raise ValueError("'%s' is a bad directive in format '%s'" %
                                        (bad_directive, format)) from None
                _regex_cache[format] = format_regex
        found = format_regex.match(data_string)
        if not found:
>           raise ValueError("time data %r does not match format %r" %
                             (data_string, format))
E           ValueError: time data '   ' does not match format '%Y-%m-%d'

/usr/local/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/_strptime.py:555: ValueError
=========================== short test summary info ============================
FAILED test_patchpilot_regression.py::test_missing_date_does_not_crash - Valu...
FAILED test_patchpilot_regression.py::test_whitespace_date_does_not_crash - V...
2 failed in 0.10s


```

### regression_after

2 passed, 0 failed, 0 errors (exit 0)

```text
..                                                                       [100%]
2 passed in 0.01s


```

### post_patch_tests

5 passed, 0 failed, 0 errors (exit 0)

```text
.....                                                                    [100%]
5 passed in 0.03s


```

## Explanation

This patch fixes the crash reported in the issue: uploading a CSV where a row's date column is blank used to raise `ValueError: time data '' does not match format '%Y-%m-%d'`. The fix checks whether the date string is empty (after trimming whitespace) before calling strptime, and sets the row's date to None in that case instead of crashing. All other rows are parsed exactly as before.

## Candidate diff

```diff
--- a/csv_parser.py
+++ b/csv_parser.py
@@ -15,9 +15,8 @@
     name = row.get("name", "").strip()
     amount = float(row.get("amount", 0) or 0)
 
-    # BUG: this blows up with ValueError when row["date"] == ""
-    date_str = row.get("date", "")
-    date = datetime.strptime(date_str, "%Y-%m-%d")
+    date_str = row.get("date", "").strip()
+    date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
 
     return {"name": name, "amount": amount, "date": date}
 

```

## Generated regression

```python
from csv_parser import parse_row

def test_missing_date_does_not_crash():
    assert parse_row({'name': 'Bob', 'date': '', 'amount': '5'})['date'] is None

def test_whitespace_date_does_not_crash():
    assert parse_row({'name': 'Bob', 'date': '   ', 'amount': '5'})['date'] is None

```

## Attempts

```json
{
  "number": 1,
  "diff": "--- a/csv_parser.py\n+++ b/csv_parser.py\n@@ -15,9 +15,8 @@\n     name = row.get(\"name\", \"\").strip()\n     amount = float(row.get(\"amount\", 0) or 0)\n \n-    # BUG: this blows up with ValueError when row[\"date\"] == \"\"\n-    date_str = row.get(\"date\", \"\")\n-    date = datetime.strptime(date_str, \"%Y-%m-%d\")\n+    date_str = row.get(\"date\", \"\").strip()\n+    date = datetime.strptime(date_str, \"%Y-%m-%d\") if date_str else None\n \n     return {\"name\": name, \"amount\": amount, \"date\": date}\n \n",
  "reasoning": "The parser called datetime.strptime on an empty string, which always raises ValueError. The fix short-circuits: if the date field is empty after stripping whitespace, the row's date is set to None instead of attempting to parse it.",
  "applied": true,
  "message": "Patch applied cleanly",
  "regression": "2 passed, 0 failed, 0 errors (exit 0)",
  "suite": "5 passed, 0 failed, 0 errors (exit 0)"
}
```

## Trace

- Loading issue and classifying it
- Inspected files: ['csv_parser.py', 'tests/test_csv_parser.py']
- Running the full baseline suite
- Generating a regression test before generating the fix
- Regression reproduced: 0 passed, 2 failed, 0 errors (exit 1)
- Generating candidate 1/3
- Regression and full suite pass; candidate is ready for review