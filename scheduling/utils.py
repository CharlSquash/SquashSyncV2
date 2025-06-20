# scheduling/utils.py
import calendar
from datetime import date

def get_month_start_end(year, month):
    """Returns the first and last day of a given month and year."""
    _, num_days = calendar.monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, num_days)
    return start_date, end_date