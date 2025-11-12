import time
from typing import Literal, TypedDict

from langchain_community.tools import TavilySearchResults
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.constants import END
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from sales_agent.network_team.prompts import network_team_prompt
from sales_agent.config import llm, llm_with_reasoning, SLEEP_TIME, HIL_FLAG
from sales_agent.state import NetworkState

NETWORK_TEAM_RESPONSE = (
    "The capacity and network required for the address is available with the grid operator."
    "The standard delivery rate is 0.18436€/kWh. During off-peak time (21:00-07:00), delivery rate is 0.14716/kWh. The energy tax is 0.10154€/kWh."
    "The fixed grid management cost per month is 24.49, excluding surcharge of €2.00 if the customer will only purchase electricity at one delivery address."
)

tools = ['network_team_input', 'reflect_network_team_input', END]


def network_team() -> CompiledStateGraph:
    """Create graph for analyzing market trends and price levels."""
    builder = StateGraph(NetworkState)

    builder.add_node(network_team_supervisor)
    builder.add_node(network_team_input)
    builder.add_node(reflect_network_team_input)
    # builder.add_node(generate_network_report)

    builder.add_edge('__start__', "network_team_supervisor")
    builder.add_edge('network_team_input', "network_team_supervisor")
    # builder.add_edge('generate_network_report', 'network_team_supervisor')

    return builder.compile()


def network_team_supervisor(
        state: NetworkState
) -> Command[Literal[*tools]]:
    """Supervise the market analysis by routing between workers."""
    time.sleep(SLEEP_TIME)

    if state['pricing_advice_asked']:
        return continue_pricing_loop(state)

    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal[*tools]

    messages = [{"role": "system", "content": network_team_prompt}, ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]

    if goto == "FINISH":
        goto = END

    return Command(update={'next': goto}, goto=goto)


def continue_pricing_loop(state: NetworkState) -> Command:
    loop_step = state.get('network_loop_step', 0)
    goto = tools[loop_step]

    if loop_step == len(tools) - 1:
        loop_step = 0
    else:
        loop_step += 1

    return Command(update={'next': goto, 'network_loop_step': loop_step}, goto=goto)


def network_team_input(state: NetworkState):
    """Review the tool call query."""
    time.sleep(SLEEP_TIME)
    return Command(update={'network_report': NETWORK_TEAM_RESPONSE, 'messages': [AIMessage(content=NETWORK_TEAM_RESPONSE)]}, goto='network_team_supervisor')


def reflect_network_team_input(state: NetworkState) -> Command[Literal['network_team_supervisor', END]]:
    """Reflect on the results of the risk analysis."""
    time.sleep(SLEEP_TIME)
    return Command(update={'messages': [AIMessage(content='The input is correct')]}, goto=END)