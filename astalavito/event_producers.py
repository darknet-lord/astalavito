import abc
import functools

from confluent_kafka import Producer
import socket

from astalavito import settings
from astalavito import models


class AbstractEventProducer(abc.ABC):

    @abc.abstractmethod
    def produce(self, item_id: int, event: models.ParserEvent) -> None:
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class ConsoleEventProducer(AbstractEventProducer):

    def produce(self, item_id: int, event: models.ParserEvent) -> None:
        print(f"{item_id}: {event}")


class KafkaEventProducer(AbstractEventProducer):
    def __init__(self, topic: str):
        self._topic = topic

    def produce(self, item_id: int, event: models.BaseModel) -> None:
        self._produce(key=str(item_id), value=event.json())

    def __enter__(self):
        conf = settings.KAFKA_BOOTSTRAP_SERVERS | {"client.id": socket.gethostname()}
        self.producer = Producer(conf)
        self._produce = functools.partial(self.producer.produce, self._topic)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.producer.flush()