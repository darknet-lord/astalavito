import abc
import argparse
import logging
import typing
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By

from astalavito import models
from astalavito import settings
import multiprocessing as mp

from astalavito.event_producers import AbstractEventProducer, ScannerKafkaEventProducer, ConsoleEventProducer
from astalavito.parsers import ItemParser, AbstractParser, SinglePageParser
from astalavito.types import ScanMode

LOGGER = logging.getLogger(__name__)


class ScannerException(Exception):
    pass


class AbstractScanner(abc.ABC):

    def __init__(self, parser: AbstractParser, event_producer: AbstractEventProducer) -> None:
        self.parser = parser
        self.event_producer = event_producer

    @abc.abstractmethod
    def scan(self) -> typing.Generator[tuple[int, models.ParserEvent], None, None]:
        raise NotImplementedError

    def run(self) -> None:
        producer = self.event_producer
        for item_id, event in self.scan():
            producer.produce(item_id=item_id, event=event)


class SinglePageScanner(AbstractScanner):
    def __init__(self, page_urls: list[str], event_producer: AbstractEventProducer):
        super().__init__(parser=SinglePageParser(), event_producer=event_producer)
        self.page_urls = page_urls

    def scan(self) -> typing.Generator[tuple[int, models.ParserEvent], None, None]:
        driver = webdriver.Chrome()
        root_xpath = "//div[starts-with(@class,'style-item-view-content-left') or starts-with(@class,'style-item-view-content-right')]"
        for page_url in self.page_urls:
            driver.get(page_url)
            for item in self.parser.parse(driver.find_elements(By.XPATH, root_xpath)):
                event = models.ParserEvent(
                    event_datetime=datetime.now(),
                    item_data=models.ParserEventItemData(**item.dict()),
                )
                yield item.item_id, event

        driver.close()


class FilterScanner(AbstractScanner):

    def __init__(self, filter_name: str, filter_url: str, event_producer: AbstractEventProducer):
        super().__init__(parser=ItemParser(), event_producer=event_producer)
        self.filter_name = filter_name
        self.filter_url = filter_url

    def scan(self) -> typing.Generator[tuple[int, models.ParserEvent], None, None]:
        driver = webdriver.Chrome()
        driver.get(self.filter_url)
        pagination_elems_xpath = "//span[starts-with(@class,'pagination-item')]"
        spans = driver.find_elements(By.XPATH, pagination_elems_xpath)[1:-1]
        page_count = int(spans[-1].text)
        LOGGER.debug("got %d pages for %s", page_count, self.filter_name)

        elements = driver.find_elements(By.XPATH, "//div[@data-marker='item']")
        items = self.parser.parse(root=elements)

        for item in items:
            event = models.ParserEvent(
                event_datetime=datetime.now(),
                item_data=models.ParserEventItemData(**item.dict()),
            )
            yield item.item_id, event
        driver.close()


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
    parser.add_argument("-sm", '--scan-modes', action='append', choices=[str(m) for m in list(ScanMode)], default=[])
    return parser.parse_args()


def create_filter_processes(producer: AbstractEventProducer) -> typing.Generator[mp.Process, None, None]:
    active_filters = get_active_scan_filters()
    for scan_filter in active_filters:
        filter_scanner = FilterScanner(
            filter_name=scan_filter.name,
            filter_url=scan_filter.url,
            event_producer=producer,
        )
        yield mp.Process(target=filter_scanner.run)


def create_single_page_process(producer: AbstractEventProducer) -> mp.Process:
    single_page_scanner = SinglePageScanner(page_urls=settings.SINGLE_PAGE_URLS, event_producer=producer)
    return mp.Process(target=single_page_scanner.run)


def main():
    args = parse_args()
    producer_manager = {
        "kafka": ScannerKafkaEventProducer,
        "console": ConsoleEventProducer,
    }[args.producer_manager]

    scan_procs = []
    mp.set_start_method("spawn")
    with producer_manager() as producer:
        for scan_mode in args.scan_modes:
            match ScanMode(scan_mode):
                case ScanMode.FILTER:
                    scan_procs + list(create_filter_processes(producer=producer))
                case ScanMode.SINGLE_PAGES:
                    scan_procs.append(create_single_page_process(producer=producer))

    for proc in scan_procs:
        proc.start()

    for proc in scan_procs:
        proc.join()


if __name__ == "__main__":
    main()
