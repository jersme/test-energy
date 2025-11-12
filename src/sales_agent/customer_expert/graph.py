import time
from typing import Literal, TypedDict

from langchain_community.tools import TavilySearchResults
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from sales_agent.customer_expert.prompts import customer_supervisor_prompt, company_profiler_prompt, customer_analyst_prompt
from sales_agent.config import llm, llm_with_reasoning, SLEEP_TIME, HIL_FLAG
from sales_agent.state import CustomerState

tavily_tool = TavilySearchResults(max_results=5)

company_web_search = ToolNode([tavily_tool])

tools = ['call_company_profiler', 'crm_analyst', 'consumption_analyst', 'generate_customer_analysis', 'reflect_customer_analysis', END]


def customer_expert() -> CompiledStateGraph:
    """Create graph for analyzing customer needs and behavior."""
    builder = StateGraph(CustomerState)

    builder.add_node(customer_supervisor)
    builder.add_node(call_company_profiler)
    builder.add_node(company_profiler)
    builder.add_node(crm_analyst)
    builder.add_node(consumption_analyst)
    builder.add_node(reflect_customer_analysis)
    builder.add_node(generate_customer_analysis)
    builder.add_node('company_web_search', company_web_search)

    builder.add_edge('__start__', "customer_supervisor")
    builder.add_edge('call_company_profiler', "company_profiler")
    builder.add_edge('company_web_search', "company_profiler")
    builder.add_edge('crm_analyst', "customer_supervisor")
    builder.add_edge('consumption_analyst', "customer_supervisor")
    builder.add_edge('generate_customer_analysis', "customer_supervisor")

    return builder.compile()


def customer_supervisor(state: CustomerState) -> Command[Literal[*tools]]:
    """Supervise the customer analysis by routing between workers."""
    time.sleep(SLEEP_TIME)

    if state['pricing_advice_asked']:
        return continue_pricing_loop(state)

    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal[*tools]

    messages = [{"role": "system", "content": customer_supervisor_prompt}, ] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]

    if goto == "FINISH":
        goto = END

    return Command(goto=goto)


def continue_pricing_loop(state: CustomerState) -> Command:
    """Continue to the next step in the pricing advice loop."""
    loop_step = state.get('customer_loop_step', 0)
    goto = tools[loop_step]

    if loop_step == len(tools) - 1:
        loop_step = 0
    else:
        loop_step += 1

    return Command(update={'next': goto, 'customer_loop_step': loop_step}, goto=goto)


def call_company_profiler(state: CustomerState):
    """Restrict the call to market research only."""
    time.sleep(SLEEP_TIME)

    research_question = AIMessage(content=company_profiler_prompt(state["client_name"]))
    return {"messages": [research_question]}


def company_profiler(state: CustomerState) -> Command[Literal["company_web_search", "customer_supervisor"]]:
    """Perform a web search on the company."""
    time.sleep(SLEEP_TIME)

    llm_with_tools = llm.bind_tools([tavily_tool])
    response = llm_with_tools.invoke(state["messages"])

    if response.tool_calls:
        goto = "company_web_search"
    else:
        goto = "customer_supervisor"

    return Command(
        update={"messages": [response]},
        goto=goto
    )


def generate_customer_analysis(state: CustomerState) -> Command[Literal['customer_supervisor']]:
    """Generate a report on the customer analysis."""
    time.sleep(SLEEP_TIME)
    research_question = AIMessage(content=customer_analyst_prompt)
    messages = state['messages'] + [research_question]

    response = llm_with_reasoning.invoke(messages)

    return Command(update={'customer_report': response.content, 'messages': [response]}, goto='customer_supervisor')


def crm_analyst(state: CustomerState):
    """Evaluate product importance for customers."""
    time.sleep(SLEEP_TIME)
    return {
        'messages': [AIMessage(
            content=f'Previous client, last contract ended in 2019. Switched to competitor offering lower fixed rates. Cost sensitive in contract decisions. Showed interest in renewable energy options but found pricing too high at the time',
            name='crm_analyst'
        )]
    }


def consumption_analyst(state: CustomerState):
    """Determine the pricing behavior of a customer."""
    time.sleep(SLEEP_TIME)

    return {
        'messages': [AIMessage(
            content=f'The company has a predictable, high-load consumption pattern. Peak usage hours: 4:00AM-10:00AM and 6:00PM-11:00PM. Slighly more usage in Q4 due to holidays.',
            name='consumption_analyst'
        )]
    }


def reflect_customer_analysis(state: CustomerState) -> Command[Literal['customer_supervisor', END]]:
    """Reflect on the results of the market analysis."""
    time.sleep(SLEEP_TIME)

    if HIL_FLAG:
        feedback = interrupt(f'Please review the customer analysis and provide feedback. If no feedback is needed, type "continue".')
        if 'continue' in feedback.lower():
            return Command(goto=END)
        else:
            feedback_message = HumanMessage(content=feedback)
            loop_step = 0
            return Command(update={'messages': [feedback_message], 'customer_loop_step': loop_step}, goto='customer_supervisor')

    return Command(update={'messages': [AIMessage(content='The analysis is okay')]}, goto=END)
