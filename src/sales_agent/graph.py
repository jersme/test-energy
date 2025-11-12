import time
from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.types import Command, interrupt
from pydantic import Field

from sales_agent.sourcing_team.graph import sourcing_team
from sales_agent.network_team.graph import network_team
from sales_agent.customer_expert.graph import customer_expert
from sales_agent.market_analyst.graph import market_analyst
from sales_agent.pricing_strategist.graph import pricing_strategist
from sales_agent.risk_manager.graph import risk_manager
from sales_agent.config import llm, SLEEP_TIME
from sales_agent.prompts import supervisor_prompt
from sales_agent.report_writer.graph import report_writer
from sales_agent.state import ParentState, InputState, OutputState

price_advice_loop = ['sourcing_team', 'network_team', 'risk_manager',  'market_analyst', 'customer_expert', 'pricing_strategist', 'report_writer']


def supervisor(
        state: ParentState
) -> Command[Literal['sourcing_team', 'network_team', 'risk_manager', 'market_analyst', 'customer_expert', 'pricing_strategist', 'report_writer', END]]:
    """Decide next action."""
    time.sleep(SLEEP_TIME)

    if state.get('pricing_advice_asked', False):
        return continue_pricing_loop(state)

    response = ask_llm_next_step(state)

    if response['pricing_advice_asked']:
        return start_pricing_loop()

    goto = response["next"]
    if goto == "FINISH":
        goto = END

    return Command(update={'next': goto}, goto=goto)


def ask_llm_next_step(state: ParentState):
    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal["FINISH", 'sourcing_team', 'network_team', 'risk_manager', 'market_analyst', 'customer_expert', 'pricing_strategist', 'report_writer']
        pricing_advice_asked: bool = Field(description="Indicator whether pricing advice has been asked")

    messages = [{"role": "system", "content": supervisor_prompt}, ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    print(response)
    return response


def start_pricing_loop() -> Command:
    """Start the predefined pricing advice loop."""
    goto = price_advice_loop[0]
    return Command(update={'next': goto, 'loop_step': 1, 'pricing_advice_asked': True}, goto=goto)


def continue_pricing_loop(state: ParentState) -> Command:
    """Continue to the next step in the pricing advice loop."""
    loop_step = state['loop_step']
    goto = price_advice_loop[loop_step]
    update = {'next': goto}

    if state['loop_step'] == len(price_advice_loop) - 1:
        update.update({
            'pricing_advice_asked': False,
            'loop_step': 0
        })
    else:
        update.update({'loop_step': loop_step + 1})

    return Command(update=update, goto=goto)


def human_feedback(state: ParentState):
    """Handle human feedback."""
    feedback = interrupt('Please provide feedback on the pricing advice.')
    return {'messages': [HumanMessage(feedback)]}


builder = StateGraph(ParentState, input=InputState, output=OutputState)

builder.add_node(supervisor)
builder.add_node('sourcing_team', sourcing_team())
builder.add_node('network_team', network_team())
builder.add_node('risk_manager', risk_manager())
builder.add_node('customer_expert', customer_expert())
builder.add_node('pricing_strategist', pricing_strategist())
builder.add_node('market_analyst', market_analyst())
builder.add_node('report_writer', report_writer)

builder.add_edge('__start__', 'supervisor')
builder.add_edge('network_team', 'supervisor')
builder.add_edge('sourcing_team', 'supervisor')
builder.add_edge('risk_manager', 'supervisor')

builder.add_edge('customer_expert', 'supervisor')
builder.add_edge('market_analyst', 'supervisor')
builder.add_edge('pricing_strategist', 'supervisor')

builder.add_edge('report_writer', '__end__')

memory = MemorySaver()

graph = builder.compile(checkpointer=memory)