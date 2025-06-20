# planning/templatetags/planning_extras.py
from django import template

register = template.Library()

@register.filter(name='get_item') # Explicitly name the filter for clarity in template
def get_item(dictionary, key):
    """
    Allows accessing dictionary items with a variable key in templates.
    Returns None if the dictionary is None or the key is not found.
    """
    if hasattr(dictionary, 'get'): # Check if it's a dictionary-like object
        return dictionary.get(key) # .get() on a dict returns None if key is not found
    return None # Return None if the first argument isn't a dictionary
