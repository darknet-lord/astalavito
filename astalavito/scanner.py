import abc
import argparse
import functools
import logging
import re
import typing
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from astalavito import models
from astalavito import settings
import multiprocessing as mp

from confluent_kafka import Producer
import socket

LOGGER = logging.getLogger(__name__)


class ScannerException(Exception):
    pass


class ItemParser:

    @classmethod
    def parse_square_price(cls, price_string: str) -> int | None:
        result = re.findall(r"\d+", price_string)
        return int("".join(result)) if result else None

    @classmethod
    def parse_updated_date(cls, date_string: str) -> datetime | None:
        value, unit_string, *_ = date_string.split(" ")
        value = int(value)
        unit = unit_string[0]
        now = datetime.now()
        result = {
            "ч": now - timedelta(hours=value),
            "д": now - timedelta(days=value),
            "н": now - timedelta(weeks=value),
            "м": now - timedelta(days=value * 30),
        }.get(unit) or None
        if not result:
            LOGGER.warning("Unexpected delta: %s", date_string)
        return result

    def find(self, current_element: WebElement | None, value: str) -> WebElement | None:
        if not current_element:
            return None
        try:
            result = current_element.find_element(by=By.XPATH, value=value)
        except NoSuchElementException:
            return None
        else:
            return result

    def find_many(self, current_element: WebElement | None, value: str) -> list[WebElement]:
        if not current_element:
            return []
        try:
            result = current_element.find_elements(by=By.XPATH, value=value)
        except NoSuchElementException:
            return []
        else:
            return result

    def get_text(self, element: WebElement, default_retval: typing.Any = None) -> typing.Any:
        return element.text if element else default_retval

    def elements_to_items(self, elements: list[WebElement]) -> typing.Generator[models.Item, None, None]:
        find = self.find
        find_many = self.find_many
        get_text = self.get_text

        for elm in elements:
            item_id = elm.get_attribute("data-item-id")  # prop
            title_elem = find(elm, ".//div[starts-with(@class, 'iva-item-titleStep')]")
            name = title_elem.text  # prop
            url_elem = find(title_elem, ".//a")
            url = url_elem.get_property("href")  # prop

            price_elem = find(elm, ".//span[starts-with(@class, 'price-root')]")

            price_currency = "RUB"
            price = None
            metas = find_many(price_elem, ".//meta")
            for meta in metas:
                itemprop = meta.get_attribute("itemprop")
                content = meta.get_attribute("content")
                if itemprop == "priceCurrency":
                    price_currency = content
                elif itemprop == "price":
                    price = int(content)

            price_square = get_text(find(price_elem, ".//span[starts-with(@class, 'price-noaccent')]"))
            if price_square:
                price_square = self.parse_square_price(price_square)

            badges_elem = find(elm, ".//div[starts-with(@class, 'iva-item-badgeBarStep')]")
            badge_elems = find_many(badges_elem, ".//span[starts-with(@class, 'SnippetBadge-title-')]")
            badges = [get_text(b) for b in badge_elems]

            geo_root_elem = find(elm, ".//div[starts-with(@class, 'geo-root-')]")
            geo_address = get_text(find(geo_root_elem, ".//div[starts-with(@class, 'geo-address-')]"))

            # TODO: check if multiple references.
            geo_refs = get_text(find(geo_root_elem, ".//div[starts-with(@class, 'geo-georeferences')]"))

            descr = get_text(find(elm, ".//div[starts-with(@class, 'iva-item-descriptionStep-')]"))
            updated_date = get_text(find(elm, ".//div[starts-with(@class, 'date-text-')]"))
            if updated_date:
                updated_date = self.parse_updated_date(updated_date)

            user_root_elem = find(elm, ".//div[starts-with(@class, 'iva-item-userInfoStep-')]")
            user_url_elem = find(user_root_elem, ".//div[starts-with(@class, 'style-link-')]")
            if user_url_elem:
                profile_url = user_url_elem.get_attribute("href")
                user_title = user_url_elem.text  # prop
            else:
                profile_url = None
                user_title = None

            # TODO: process user badges.
            user_badges = find_many(badges_elem, ".//span[starts-with(@class, 'SnippetBadge-title-')]")

            # TODO: process image.
            # img_elem = item.find_elem(By.XPATH, ".//img[starts-with(@class, 'photo-slider-image-')]")
            # image_src = img_elem.get_attribute("src")

            item = models.Item(
                item_id=item_id,
                name=name,
                url=url,
                price=price,
                price_square=price_square,
                profile_url=profile_url,
                geo_address=geo_address,
                geo_references=geo_refs,
                # badges=badges,
                # user_title=user_title,
                # user_badges=[b.text for b in user_badges],
                price_currency=price_currency,
                description=descr,
                page_updated_at=updated_date,
                # phone="123",  # TODO
                user=None,
            )
            yield item


class AbstractEventProducer(abc.ABC):

    @abc.abstractmethod
    def produce(self, item_id: int, event: models.Event) -> None:
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class ConsoleEventProducer(AbstractEventProducer):

    def produce(self, item_id: int, event: models.Event) -> None:
        print(f"{item_id}: {event}")


class KafkaEventProducer(AbstractEventProducer):

    def produce(self, item_id: int, event: models.Event) -> None:
        self._produce(key=str(item_id), value=event.json())

    def __enter__(self):
        conf = settings.KAFKA_BOOTSTRAP_SERVERS | {"client.id": socket.gethostname()}
        self.producer = Producer(conf)
        topic = settings.KAFKA_TOPIC
        self._produce = functools.partial(self.producer.produce, topic)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.producer.flush()


class Scanner:

    def __init__(self, filter_name: str, filter_url: str, producer_manager: type[AbstractEventProducer]):
        self.filter_name = filter_name
        self.filter_url = filter_url
        self.item_parser = ItemParser()
        self.producer_manager = producer_manager

    def find_items(self):
        driver = webdriver.Chrome()
        driver.get(self.filter_url)
        pagination_elems_xpath = "//span[starts-with(@class,'pagination-item')]"
        spans = driver.find_elements(By.XPATH, pagination_elems_xpath)[1:-1]
        page_count = int(spans[-1].text)
        LOGGER.debug("got %d pages for %s", page_count, self.filter_name)

        elements = driver.find_elements(By.XPATH, "//div[@data-marker='item']")
        items = self.item_parser.elements_to_items(elements)

        for item in items:
            event = models.Event(
                filter_name=self.filter_name,
                event_datetime=datetime.now(),
                item_data=models.EventItemData(**item.dict()),
            )
            yield item.item_id, event
        driver.close()

    def run(self):
        with self.producer_manager() as producer:
            for item_id, event in self.find_items():
                producer.produce(item_id=item_id, event=event)


def get_active_scan_filters():
    # TODO: Move to tests
    if settings.TESTING:
        class TestScanFilter:
            url = "http://localhost/astalavito/kaluga1.html"
            name = "test scan filter"
            filter_id = 1
        return [TestScanFilter()]
    else:
        filters = (models.ScanFilter(**filter_data) for filter_data in settings.FILTERS.values())
        return (f for f in filters if f.is_active)


def parse_args():
    parser = argparse.ArgumentParser("astalavito")
    parser.add_argument("-pm", "--producer-manager", choices=['kafka', 'console'], default='kafka')
    return parser.parse_args()


def main():
    mp.set_start_method("spawn")

    active_filters = get_active_scan_filters()

    args = parse_args()
    producer_manager = {
        "kafka": KafkaEventProducer,
        "console": ConsoleEventProducer,
    }[args.producer_manager]

    scan_procs = []
    for scan_filter in active_filters:
        scanner = Scanner(
            filter_name=scan_filter.name,
            filter_url=scan_filter.url,
            producer_manager=producer_manager,
        )
        scanner_proc = mp.Process(target=scanner.run)
        scan_procs.append(scanner_proc)

    for proc in scan_procs:
        proc.start()

    for proc in scan_procs:
        proc.join()


if __name__ == "__main__":
    main()
