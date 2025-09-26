# scheduling/templatetags/scheduling_extras.py
from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Allows accessing dictionary items with a variable key in templates.
    """
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None

@register.filter(name='map_attribute')
def map_attribute(list_of_objects, attribute_name):
    """
    Takes a list of objects and returns a list of a specific attribute from each object.
    Example: my_list|map_attribute:'coach.id' -> returns a list of coach IDs.
    """
    if not hasattr(list_of_objects, '__iter__'):
        return []
    
    attrs = attribute_name.split('.')
    
    result = []
    for item in list_of_objects:
        value = item
        try:
            for attr in attrs:
                if isinstance(value, dict):
                    value = value.get(attr)
                else:
                    value = getattr(value, attr)
            result.append(value)
        except (AttributeError, TypeError):
            continue
            
    return result