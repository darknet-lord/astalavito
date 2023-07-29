import enum

import faust

from astalavito import settings
from astalavito.models import ParserEventItemData
from event_producers import KafkaEventProducer

app = faust.App('astalavito', broker=settings.FAUST_BROKER, store=settings.FAUST_ROCKSDB_CONNSTR)


class ParserEventPayload(faust.Record):
    filter_name: str
    event_datetime: str
    item_data: ParserEventItemData

    @property
    def price(self):
        return self.item_data["price"]


class ChangeType(enum.Enum, str):
    PRICE_CHANGED = 'price_changed'


class ChangeEventPayload(faust.Record):
    change_type: ChangeType
    old_price: int
    new_price: int


parser_topic = app.topic(
    settings.KAFKA_PARSER_TOPIC, value_type=ParserEventPayload, partitions=settings.KAFKA_PARSER_EVENTS_PARTITIONS)
prices = app.Table(settings.KAFKA_PRICE_TABLE, default=list, partitions=settings.KAFKA_PRICE_TABLE_PARITIONS)
changes_topic = app.topic(
    settings.KAFKA_CHANGES_TOPIC, value_type=ChangeEventPayload, partitions=settings.KAFKA_CHANGE_EVENTS_PARTITIONS)


@app.agent(changes_topic)
async def parser_event(change_event):
    print("> CHANGE EVENT: ", change_event)


@app.agent(parser_topic)
async def parser_event(parser_events):
    with KafkaEventProducer(topic=settings.KAFKA_CHANGES_TOPIC) as producer:
        async for event in parser_events:
            print(f'Event received {event}')
            item_id = event.item_data["item_id"]
            current_prices = prices[item_id]
            prev_price = next(iter(current_prices[::-1]), None)
            if event.price != prev_price:
                current_prices.append(event.price)
                prices[event.item_data["item_id"]] = current_prices
                change_event = ChangeEventPayload(
                    old_price=prev_price,
                    new_price=event.price,
                    change_type=ChangeType.PRICE_CHANGED,
                )
                producer.produce(item_id, change_event)


if __name__ == '__main__':
    app.main()
