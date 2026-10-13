from csv_parser import parse_row

def test_missing_date_does_not_crash():
    assert parse_row({'name': 'Bob', 'date': '', 'amount': '5'})['date'] is None

def test_whitespace_date_does_not_crash():
    assert parse_row({'name': 'Bob', 'date': '   ', 'amount': '5'})['date'] is None
