import markdown
from langchain_core.messages import AIMessage

from sales_agent.report_writer.prompt import report_writer_prompt
from sales_agent.state import ParentState
from sales_agent.config import llm_with_reasoning

LLM_ACTIVATED = True


def report_writer(state: ParentState):
    """Retrieve prediction."""
    if LLM_ACTIVATED:

        messages = [AIMessage(content=report_writer_prompt(state['sourcing_report'], state['network_report'], state['risk_report'], state['customer_report'], state['market_report'], state['pricing_report'], state['negotiation_report']))]
        response = llm_with_reasoning.invoke(messages)
        last_message = response.content
    else:
        ## read markdown text file named report.md
        with open('report.md', 'r') as f:
            last_message = f.read()

    final_message = str()
    for line in last_message.split('\n'):
        if line.startswith('<!DOCTYPE html>'):
            final_message += line + '\n'
        elif line.startswith('</html>'):
            final_message += line + '\n'
            break
        final_message += line + '\n'


    with open('report.html', 'w') as f:
        f.write(final_message)

    return {'messages': [AIMessage(last_message)]}
