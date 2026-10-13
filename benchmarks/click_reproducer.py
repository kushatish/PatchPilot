"""Independent reproducer for pallets/click#2395; run against a checkout via PYTHONPATH."""
import click
import pytest


@pytest.mark.parametrize('filename', ['foo\udce9', b'foo\xe9'])
def test_format_filename_is_safe_to_print(filename):
    result = click.format_filename(filename)
    # Display output should encode safely; literal Unicode surrogates cannot.
    result.encode('utf-8', errors='strict')
    assert '\ufffd' in result
