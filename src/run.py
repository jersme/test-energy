import re
import textwrap

from langchain_core.messages import HumanMessage, convert_to_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Interrupt

from sales_agent.graph import graph
from PIL import Image

QUERY = {
    'client_name': 'AkzoNobel',
    'client_address': 'Christian Neefestraat 2, 1077 WW Amsterdam',
    'electricity_volume': '3000 MWh',
    'contract_duration': '2 years',
}


def main():
    """Show and run graph."""
    query = {
        'messages': [
            HumanMessage(
                content=("Give me advice and insights to help me negotiate an energy contract with my client"),
                name='user'
            )
        ]
    }
    query.update(QUERY)
    run_graph(graph, query)
    save_and_open_graph(graph, 'graph', xray=1)


def save_and_open_graph(graph: CompiledStateGraph, name: str, xray=0):
    """Save and open the graph."""
    img = graph.get_graph(xray=xray).draw_mermaid_png()
    with open(f"{name}.png", "wb") as f:
        f.write(img)
    Image.open(f"{name}.png").show()


def pretty_print_messages(update, max_length=100):
    ns, update = update

    for node_name, node_update in update.items():
        print(f"Update from node {node_name}:")

        if node_update:
            # print all messages
            if "messages" in node_update:
                for m in convert_to_messages(node_update.get("messages")):
                    content = m.pretty_repr()

                    headers = [
                        '================================ Human Message =================================',
                        '================================== Ai Message ==================================',
                        '================================= Tool Message ================================='
                    ]

                    split_content = re.split(f"({'|'.join(re.escape(header) for header in headers)})|'\n'", content)

                    for text in split_content:
                        if text in headers:
                            print(text)
                        else:
                            wrapped_content = '\n'.join(textwrap.wrap(text, max_length, replace_whitespace=False))
                            print(wrapped_content)

            # print all other updates
            if isinstance(node_update, tuple) and isinstance(node_update[0], Interrupt):
                print(node_update)
            else:
                for k, v in node_update.items():
                    if k != "messages":
                        print(f"{k}: {v}")

        print("\n")


def run_graph(graph: CompiledStateGraph, input: dict):
    """Run the graph."""
    config = {"configurable": {"thread_id": "1"}}
    events = graph.stream(input, config, subgraphs=True, stream_mode="updates")
    nodes = []
    for event in events:
        pretty_print_messages(event)
        nodes.append(list(event[1].keys())[0])

    print('Node execution order: ', nodes)


if __name__ == "__main__":
    main()
