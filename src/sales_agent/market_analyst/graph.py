import time
from typing import Literal, TypedDict

from langchain_community.tools import TavilySearchResults
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.constants import END
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from sales_agent.market_analyst.prompts import market_supervisor_prompt, market_researcher_prompt, market_analyst_prompt
from sales_agent.config import llm, llm_with_reasoning, SLEEP_TIME, HIL_FLAG
from sales_agent.state import MarketState


tavily_tool = TavilySearchResults(max_results=5)

market_web_search = ToolNode([tavily_tool])


def market_analyst() -> CompiledStateGraph:
    """Create graph for analyzing market trends and price levels."""
    builder = StateGraph(MarketState)

    builder.add_node(market_supervisor)
    builder.add_node(call_market_researcher)
    builder.add_node(market_researcher)
    builder.add_node(reflect_market_analysis)
    builder.add_node(generate_market_analysis)
    builder.add_node('market_web_search', market_web_search)

    builder.add_edge('__start__', "market_supervisor")
    builder.add_edge('call_market_researcher', "market_researcher")
    builder.add_edge('market_web_search', "market_researcher")
    builder.add_edge('generate_market_analysis', 'market_supervisor')

    return builder.compile()


tools = ['call_market_researcher', 'generate_market_analysis', 'reflect_market_analysis', END]


def market_supervisor(
        state: MarketState
) -> Command[Literal[*tools]]:
    """Supervise the market analysis by routing between workers."""
    time.sleep(SLEEP_TIME)

    if state['pricing_advice_asked']:
        return continue_pricing_loop(state)

    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal[*tools]

    messages = [{"role": "system", "content": market_supervisor_prompt}, ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]

    if goto == "FINISH":
        goto = END

    return Command(update={'next': goto}, goto=goto)


def continue_pricing_loop(state: MarketState) -> Command:
    loop_step = state.get('market_loop_step', 0)
    goto = tools[loop_step]

    if loop_step == len(tools) - 1:
        loop_step = 0
    else:
        loop_step += 1

    return Command(update={'next': goto, 'market_loop_step': loop_step}, goto=goto)


def call_market_researcher(state: MarketState):
    time.sleep(SLEEP_TIME)
    """Restrict the call to market research only."""
    research_question = AIMessage(content=market_researcher_prompt(state["client_name"]))
    return {"messages": [research_question]}


def market_researcher(state: MarketState) -> Command[Literal['market_web_search', 'market_supervisor']]:
    """Perform a web search on market trends."""
    time.sleep(SLEEP_TIME)
    llm_with_tools = llm.bind_tools([tavily_tool])
    response = llm_with_tools.invoke(state['messages'])
    if response.tool_calls:
        goto = "market_web_search"
    else:
        goto = "market_supervisor"

    return Command(
        update={"messages": [response]},
        goto=goto
    )


def generate_market_analysis(state: MarketState) -> Command[Literal['market_supervisor']]:
    """Generate a comprehensive market analysis report."""
    time.sleep(SLEEP_TIME)
    research_question = AIMessage(content=market_analyst_prompt)
    messages = state['messages'] + [research_question]

    response = llm_with_reasoning.invoke(messages)
    MARKET_REPORT = response.content

    return Command(update={'market_report': response.content, 'messages': [response]}, goto='market_supervisor')


def reflect_market_analysis(state: MarketState) -> Command[Literal['market_supervisor', END]]:
    """Reflect on the results of the market analysis."""
    time.sleep(SLEEP_TIME)

    if HIL_FLAG:
        feedback = interrupt(f'Please review the market analysis and provide feedback. If no feedback is needed, type "continue".')
        if 'continue' in feedback.lower():
            return Command(goto=END)
        else:
            feedback_message = HumanMessage(content=feedback)
            loop_step = 0
            return Command(update={'messages': [feedback_message], 'market_loop_step': loop_step}, goto='market_supervisor')

    return Command(update={'messages': [AIMessage(content='The analysis is okay')]}, goto=END)