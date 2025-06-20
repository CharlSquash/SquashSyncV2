# core/utils.py
import re

def parse_grade_from_string(grade_str: str):
    """
    Parses a grade string (e.g., 'Grade 8', '8', 'Gr 8') and returns an integer.
    Returns None if parsing fails.
    """
    if not grade_str:
        return None
    # Find the first number in the string
    match = re.search(r'\d+', grade_str)
    if match:
        return int(match.group(0))
    # Handle special cases like 'Grade R'
    if 'r' in grade_str.lower():
        return 0
    return None