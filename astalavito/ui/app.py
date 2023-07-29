import requests
from nicegui import ui

from astalavito.models import ParserEvent


def get_events():
    events = []  # TODO: get events from rocksdb
    for event in events:
        yield {
            "event": event.event.name,
            "price": event.price,
            "datetime": event.event_datetime,
            "item": event.item.title,
        }


def make_request():
    resp = requests.get("http://localhost")
    print(resp)


def run_app():
    grid = ui.aggrid({
        'columnDefs': [
            {'headerName': 'event', 'field': 'event'},
            {'headerName': 'price', 'field': 'price'},
            {'headerName': 'datetime', 'field': 'datetime'},
            {'headerName': 'item', 'field': 'item'},
        ],
        'rowData': list(get_events()),
        'rowSelection': 'multiple',
    }).style("height: 500px")

    # ui.button('Select all', on_click=lambda: grid.call_api_method('selectAll'))
    grid.call_api_method()
    ui.button('Select all', on_click=make_request)
    ui.run(port=8888)


if __name__ in {"__main__", "__mp_main__"}:
    run_app()