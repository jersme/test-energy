from typing import TypedDict, Annotated

import operator

from langgraph.graph import add_messages


class InputState(TypedDict):
    client_name: str
    client_address: str
    electricity_volume: str
    contract_duration: str
    messages: Annotated[list, add_messages]


class OutputState(TypedDict):
    messages: Annotated[list, add_messages]
    market_price: float
    customer_product_application: str
    customer_price_aggressiveness: float
    customer_wtp_value: float
    customer_report: str
    market_report: str
    risk_report: str
    sourcing_report: str
    network_report: str
    pricing_report: str
    negotiation_report: str


class SharedState(TypedDict):
    next: str
    messages: Annotated[list, add_messages]
    pricing_advice_asked: bool


class CustomerState(SharedState):
    customer_loop_step: int
    market_price: float
    customer_product_application: str
    customer_price_aggressiveness: float
    customer_wtp_value: float
    client_name: str
    customer_report: str


class MarketState(SharedState):
    market_loop_step: int
    client_name: str
    market_report: str


class RiskState(SharedState):
    risk_loop_step: int
    client_name: str
    risk_report: str


class SourceState(SharedState):
    source_loop_step: int
    client_address: str
    electricity_volume: str
    sourcing_report: str


class NetworkState(SharedState):
    network_loop_step: int
    client_address: str
    network_report: str


class StrategyState(SharedState):
    strategy_loop_step: int
    contract_duration: str
    electricity_volume: str
    pricing_report: str
    negotiation_report: str


class ParentState(InputState, OutputState):
    next: str
    pricing_advice_asked: bool
    loop_step: int
