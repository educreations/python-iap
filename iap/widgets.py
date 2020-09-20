from django.forms.widgets import NullBooleanSelect


class IAPNullBooleanSelect(NullBooleanSelect):
    """
    A Select Widget intended to be used with NullBooleanField.
    """

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        return {
            "0": False,
            "1": True,
            "2": True,
            True: True,
            "True": True,
            "true": True,
            "3": False,
            "False": False,
            "false": False,
            False: False,
        }.get(value)
