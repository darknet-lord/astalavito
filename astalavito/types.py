import enum


class ScanMode(str, enum.Enum):
    FILTER = 'filter'
    SINGLE_PAGES = 'single_pages'

    def __str__(self):
        return self.value
