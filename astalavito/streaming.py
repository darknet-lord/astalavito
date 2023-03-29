import faust

from astalavito import settings
from astalavito.models import EventItemData

app = faust.App('astalavito', broker=settings.FAUST_BROKER, store=settings.FAUST_ROCKSDB_CONNSTR)


class EventPayload(faust.Record):
    filter_name: str
    event_datetime: str
    item_data: EventItemData

    @property
    def price(self):
        return self.item_data["price"]


topic = app.topic(settings.KAFKA_TOPIC, value_type=EventPayload, partitions=settings.KAFKA_EVENTS_PARTITIONS)
prices = app.Table(settings.KAFKA_PRICE_TABLE, default=list, partitions=settings.KAFKA_PRICE_TABLE_PARITIONS)


async def notify(event):
    print(f" >> Event processed: {event}", event)


@app.agent(topic)
async def event(events):
    async for event in events:
        print(f'Event received {event}')
        item_id = event.item_data["item_id"]
        current_prices = prices[item_id]
        if event.price != next(iter(current_prices[::-1]), None):
            current_prices.append(event.price)
            prices[event.item_data["item_id"]] = current_prices
            await notify(event)


if __name__ == '__main__':
    app.main()
