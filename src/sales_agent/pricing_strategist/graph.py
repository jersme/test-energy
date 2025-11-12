import time

from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.tools.retriever import create_retriever_tool
from typing_extensions import Literal

from langgraph.graph import END
from langgraph.types import Command, interrupt
from langgraph.prebuilt import ToolNode
from langgraph.graph.state import CompiledStateGraph, StateGraph

from sales_agent.pricing_strategist.prompts import strategy_supervisor_prompt, strategy_doc_retriever_prompt, pricing_report_prompt, negotiation_prompt
from sales_agent.pricing_strategist.tools import price_prediction, get_doc_retriever
from sales_agent.state import StrategyState
from sales_agent.config import llm, llm_with_reasoning, SLEEP_TIME, HIL_FLAG

REWRITE_GRAPH = False

strategy_retriever = get_doc_retriever(["/Users/sfotedar/Documents/genai-sales-rep-energy-sector/Energy Pricing Strategy.pdf"])
retriever_from_llm = MultiQueryRetriever.from_llm(
    retriever=strategy_retriever, llm=llm
)
retriever_tool = create_retriever_tool(
    strategy_retriever,
    "retrieve_pricing_startegy",
    "Search and return relevant details of the pricing strategy.",
)
strategy_doc_retriever = ToolNode([retriever_tool])

tools = ['call_pricing_strategy', 'price_modeller', 'generate_strategy_report', 'negotiation_expert', 'reflect_strategy', END]


def pricing_strategist() -> CompiledStateGraph:
    """Create graph for determining strategy"""
    builder = StateGraph(StrategyState)

    builder.add_node(strategy_supervisor)
    builder.add_node(call_pricing_strategy)
    builder.add_node(query_strategy_documents)
    builder.add_node(price_modeller)
    builder.add_node(reflect_strategy)
    builder.add_node(generate_strategy_report)
    builder.add_node(negotiation_expert)
    builder.add_node('strategy_doc_retriever', strategy_doc_retriever)

    builder.add_edge('__start__', "strategy_supervisor")
    builder.add_edge('call_pricing_strategy', "query_strategy_documents")
    builder.add_edge("strategy_doc_retriever", "query_strategy_documents")
    builder.add_edge('price_modeller', "strategy_supervisor")
    builder.add_edge('generate_strategy_report', "strategy_supervisor")
    builder.add_edge('negotiation_expert', "strategy_supervisor")

    return builder.compile()


def strategy_supervisor(
        state: StrategyState
) -> Command[Literal[*tools]]:
    """Retrieve prediction."""
    time.sleep(SLEEP_TIME)

    if state['pricing_advice_asked']:
        return continue_pricing_loop(state)
    
    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""
        next: Literal[*tools]

    messages = [{"role": "system", "content": strategy_supervisor_prompt},] + state["messages"]
    response = llm.with_structured_output(Router).invoke(messages)
    goto = response["next"]

    if goto == "FINISH":
        goto = END

    return Command(update={'next': goto}, goto=goto)


def continue_pricing_loop(state: StrategyState) -> Command:
    loop_step = state.get('strategy_loop_step', 0)
    goto = tools[loop_step]

    if loop_step == len(tools) - 1:
        loop_step = 0
    else:
        loop_step += 1

    return Command(update={'next': goto, 'strategy_loop_step': loop_step}, goto=goto)


def call_pricing_strategy(state: StrategyState):
    time.sleep(SLEEP_TIME)
    """Restrict the call to market research only."""
    research_question = AIMessage(content=strategy_doc_retriever_prompt(state["electricity_volume"], state['contract_duration']))
    return {"messages": [research_question]}


def query_strategy_documents(state: StrategyState) -> Command[Literal['strategy_doc_retriever', 'strategy_supervisor']]:
    """Analyze strategy."""
    time.sleep(SLEEP_TIME)
    llm_with_tools = llm.bind_tools([retriever_tool])
    response = llm_with_tools.invoke(state['messages'])
    print("Response from query_strategy_documents")
    print(response)
    if response.tool_calls:
        goto = "strategy_doc_retriever"
    else:
        goto = "strategy_supervisor"

    return Command(
        update={"messages": [response]},
        goto=goto
    )


def price_modeller(state: StrategyState):
    """Determine the market price of a product through data analysis."""
    time.sleep(SLEEP_TIME)

    if REWRITE_GRAPH:
        fig = price_prediction()
        fig.write_image('prediction_graph.png')

    return {
        'market_price': 0.29886,
        'messages': [
            AIMessage(
                content=f"The recommended rate is 0.29886 €/kWh)."
            )
        ]
    }


def generate_strategy_report(state: StrategyState) -> Command[Literal['strategy_supervisor']]:
    """Generate a comprehensive pricing strategy report."""
    time.sleep(SLEEP_TIME)
    research_question = AIMessage(content=pricing_report_prompt)
    messages = state['messages'] + [research_question]

    response = llm_with_reasoning.invoke(messages)
    PRICING_REPORT = response.content

    return Command(update={'pricing_report': response.content, 'messages': [response]}, goto='strategy_supervisor')


def negotiation_expert(state: StrategyState):
    """Negotiate strategy."""
    time.sleep(SLEEP_TIME)
    research_question = AIMessage(content=negotiation_prompt)
    messages = state['messages'] + [research_question]

    response = llm_with_reasoning.invoke(messages)
    NEGOTIATION_REPORT = response.content

    return Command(update={'negotiation_report': response.content, 'messages': [response]}, goto='strategy_supervisor')


def reflect_strategy(state: StrategyState) -> Command[Literal['strategy_supervisor', END]]:
    time.sleep(SLEEP_TIME)
    if HIL_FLAG:
        feedback = interrupt(f'Please review the pricing strategy and provide feedback. If no feedback is needed, type "continue".')
        if 'continue' in feedback.lower():
            return Command(goto=END)
        else:
            feedback_message = HumanMessage(content=feedback)
            loop_step = 0
            return Command(update={'messages': [feedback_message], 'strategy_loop_step': loop_step}, goto='strategy_supervisor')

    return Command(update={'messages': [AIMessage(content='The analysis is okay')]}, goto=END)
