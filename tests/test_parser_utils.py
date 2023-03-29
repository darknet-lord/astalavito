import datetime

import pytest

from astalavito.scanner import Item, ItemParser


CURRENT_DATETIME = datetime.datetime.now()


@pytest.mark.parametrize("price_string, x_price", [
    ("95 960 ₽ за м²", 95960),
])
def test_can_parse_square_price(price_string, x_price):
    assert ItemParser.parse_square_price(price_string) == x_price


@pytest.mark.parametrize("date_string, delta", [
    ("1 день назад", datetime.timedelta(days=1)),
    ("2 дня назад",  datetime.timedelta(days=2)),
    ("5 дней назад", datetime.timedelta(days=5)),
    ("5 недель назад", datetime.timedelta(weeks=5)),
    ("1 неделю назад", datetime.timedelta(weeks=1)),
    ("7 неделей назад", datetime.timedelta(weeks=7)),
    ("1 час назад", datetime.timedelta(hours=1)),
    ("2 часа назад", datetime.timedelta(hours=2)),
    ("5 часов назад", datetime.timedelta(hours=5)),
    ("1 месяц назад", datetime.timedelta(days=30)),
])
def test_can_parse_updated_date(date_string, delta):
    x_datetime = (CURRENT_DATETIME - delta).replace(microsecond=0)
    result = ItemParser.parse_updated_date(date_string).replace(microsecond=0)
    assert result == x_datetime
