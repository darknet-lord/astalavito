import datetime
import enum
from pydantic import BaseModel, PositiveInt


class UserStatus(enum.Enum):
    AGENCY = 1
    PRIVATE = 2


class User(BaseModel):
    user_id: PositiveInt
    user_status: UserStatus
    user_title: str
    # user_badges: list[str] = list
    items = "Item"


class ScanFilterState(enum.Enum):
    DISABLED = 0
    ENABLED = 1


class ScanFilter(BaseModel):
    name: str
    url: str
    state: ScanFilterState = ScanFilterState.ENABLED
    schedule: str = "0 0 * * *"  # TODO

    @property
    def is_active(self):
        return self.state == ScanFilterState.ENABLED

    def __str__(self):
        return f"ScanFilter {self.name}: {self.state}"


class Item(BaseModel):
    item_id: PositiveInt
    name: str
    url: str
    price: PositiveInt
    geo_address: str | None
    geo_references: str | None
    description: str | None
    page_updated_at: datetime.datetime
    price_currency: str
    price_square: PositiveInt
    profile_url: str | None
    phone: str | None
    user: User | None
    # badges:

    def __str__(self):
        return f"Item {self.name}"


class ParserEventItemData(BaseModel):
    item_id: PositiveInt
    name: str
    price: PositiveInt
    page_updated_at: datetime.datetime
    price_currency: str


class ParserEvent(BaseModel):

    filter_name: str
    event_datetime: datetime.datetime
    item_data: ParserEventItemData

    def __str__(self):
        return f"ParserEvent {self.event_datetime.isoformat()}, {self.item_data.item_id} ({self.filter_name})"
