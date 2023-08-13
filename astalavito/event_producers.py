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


class BaseKafkaEventProducer(AbstractEventProducer):

    kafka_topic: str

    def produce(self, item_id: int, event: models.BaseModel) -> None:
        self._produce(key=str(item_id), value=event.json())

    def __enter__(self):
        conf = settings.KAFKA_BOOTSTRAP_SERVERS | {"client.id": socket.gethostname()}
        self.producer = Producer(conf)
        self._produce = functools.partial(self.producer.produce, self.kafka_topic)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.producer.flush()


class ScannerKafkaEventProducer(BaseKafkaEventProducer):
    kafka_topic = settings.KAFKA_PARSER_TOPIC


class ChangesKafkaEventProducer(BaseKafkaEventProducer):
    kafka_topic = settings.KAFKA_CHANGES_TOPIC
