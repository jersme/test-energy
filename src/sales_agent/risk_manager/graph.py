import time
import os
from typing import Literal, TypedDict

from langchain_community.utilities.financial_datasets import FinancialDatasetsAPIWrapper
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.constants import END
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from langchain_community.agent_toolkits.polygon.toolkit import PolygonToolkit
from langchain_community.utilities.polygon import PolygonAPIWrapper

from sales_agent.risk_manager.tools import YahooFinanceNewsTool
from sales_agent.risk_manager.prompts import risk_manager_prompt, financials_researcher_prompt, stock_researcher_prompt, risk_report_prompt
from sales_agent.config import llm, llm_with_reasoning, SLEEP_TIME, HIL_FLAG
from sales_agent.state import RiskState

REWRITE_GRAPH = False

polygon = PolygonAPIWrapper()
polygon_toolkit = PolygonToolkit.from_polygon_api_wrapper(polygon)

stocks_tool = polygon_toolkit.get_tools()

api_wrapper = FinancialDatasetsAPIWrapper(
    financial_datasets_api_key=os.environ["FINANCIAL_DATASETS_API_KEY"]
)
yahoo_tool = YahooFinanceNewsTool()

financials_search = ToolNode([yahoo_tool])
finance_datasets_search = ToolNode(stocks_tool)

tools = ['call_financials_researcher', 'call_stocks_researcher', 'credit_checker', 'generate_risk_analysis', 'reflect_risk_analysis', END]


def risk_manager() -> CompiledStateGraph:
    """Create graph for analyzing market trends and price levels."""
    builder = StateGraph(RiskState)

    builder.add_node(risk_supervisor)
    builder.add_node(call_financials_researcher)
    builder.add_node(financials_researcher)
    builder.add_node(call_stocks_researcher)
    builder.add_node(stocks_researcher)
    builder.add_node(credit_checker)
    builder.add_node(reflect_risk_analysis)
    builder.add_node(generate_risk_analysis)
    builder.add_node('financials_search', financials_search)
    builder.add_node('finance_datasets_search', finance_datasets_search)

    builder.add_edge('__start__', "risk_supervisor")
    builder.add_edge('call_financials_researcher', "financials_researcher")
    builder.add_edge('financials_search', "financials_researcher")
    builder.add_edge('call_stocks_researcher', "stocks_researcher")
    builder.add_edge('finance_datasets_search', "stocks_researcher")
    builder.add_edge('credit_checker', "risk_supervisor")
    builder.add_edge('generate_risk_analysis', 'risk_supervisor')

    return builder.compile()


def risk_supervisor(
        state: RiskState
) -> Command[Literal[*tools]]:
    """Supervise the market analysis by routing between workers."""
    time.sleep(SLEEP_TIME)

    if state['pricing_advice_asked']:
        return continue_pricing_loop(state)

    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal[*tools]

    messages = [{"role": "system", "content": risk_manager_prompt}, ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]

    if goto == "FINISH":
        goto = END

    return Command(update={'next': goto}, goto=goto)


def continue_pricing_loop(state: RiskState) -> Command:
    loop_step = state.get('risk_loop_step', 0)
    goto = tools[loop_step]

    if loop_step == len(tools) - 1:
        loop_step = 0
    else:
        loop_step += 1

    return Command(update={'next': goto, 'risk_loop_step': loop_step}, goto=goto)


def call_financials_researcher(state: RiskState):
    time.sleep(SLEEP_TIME)
    """Restrict the call to financials research only."""
    research_question = AIMessage(content=financials_researcher_prompt(state["client_name"]))
    return {"messages": [research_question]}


def financials_researcher(state: RiskState) -> Command[Literal['financials_search', 'risk_supervisor']]:
    """Perform a web search on market trends."""
    time.sleep(SLEEP_TIME)

    llm_with_tools = llm.bind_tools([yahoo_tool])
    response = llm_with_tools.invoke(state['messages'])
    if response.tool_calls:
        goto = "financials_search"
    else:
        goto = "risk_supervisor"

    return Command(
        update={"messages": [response]},
        goto=goto
    )


def call_stocks_researcher(state: RiskState):
    time.sleep(SLEEP_TIME)
    """Restrict the call to financials research only."""
    research_question = AIMessage(content=stock_researcher_prompt(state["client_name"]))
    return {"messages": [research_question]}


def stocks_researcher(state: RiskState) -> Command[Literal['finance_datasets_search', 'risk_supervisor']]:
    """Perform a web search on market trends."""
    time.sleep(SLEEP_TIME)
    llm_with_tools = llm.bind_tools(stocks_tool)
    response = llm_with_tools.invoke(state['messages'])
    if response.tool_calls:
        goto = "finance_datasets_search"
    else:
        goto = "risk_supervisor"

    return Command(
        update={"messages": [response]},
        goto=goto
    )


def credit_checker(state: RiskState) -> Command[Literal['risk_supervisor', END]]:
    """Check the credit of the customer."""
    time.sleep(SLEEP_TIME)
    return {
        'messages': [AIMessage(
            content=f'Consistently strong payment history. The credit is good',
            name='credit_checker'
        )]
        }


def generate_risk_analysis(state: RiskState) -> Command[Literal['risk_supervisor']]:
    """Generate a comprehensive risk analysis report."""
    time.sleep(SLEEP_TIME)
    research_question = AIMessage(content=risk_report_prompt)
    messages = state['messages'] + [research_question]

    response = llm_with_reasoning.invoke(messages)

    return Command(update={'risk_report': response.content, 'messages': [response]}, goto='risk_supervisor')


def reflect_risk_analysis(state: RiskState) -> Command[Literal['risk_supervisor', END]]:
    """Reflect on the results of the risk analysis."""
    time.sleep(SLEEP_TIME)
    if HIL_FLAG:
        feedback = interrupt(f'Please review the pricing strategy and provide feedback. If no feedback is needed, type "continue".')
        if 'continue' in feedback.lower():
            return Command(goto=END)
        else:
            feedback_message = HumanMessage(content=feedback)
            loop_step = 0
            return Command(update={'messages': [feedback_message], 'risk_loop_step': loop_step}, goto='risk_supervisor')

    return Command(update={'messages': [AIMessage(content='The analysis is okay')]}, goto=END)
