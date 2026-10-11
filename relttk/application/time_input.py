"""HH:MM editing with native Textual input restrictions and validation."""
from textual.validation import Regex
from textual.widgets import Input


class TimeInput(Input):
    def __init__(self, value='08:00', **kwargs):
        super().__init__(value=value, placeholder='HH:MM', max_length=5,
            restrict=r'(?:[0-2]|(?:[01][0-9]|2[0-3])(?::(?:[0-5][0-9]?)?)?)?',
            validators=Regex(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',
                failure_description='Nhập giờ 00:00–23:59 (HH:MM)'),
            tooltip='Giờ Việt Nam, 00:00–23:59. Ví dụ: 08:30', **kwargs)
