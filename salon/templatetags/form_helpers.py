from django import template

register = template.Library()


@register.inclusion_tag('salon/field.html')
def field(field, label=None, show_label=True):
    return {
        'field': field,
        'label': label or field.label,
        'show_label': show_label,
    }
