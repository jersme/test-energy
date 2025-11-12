from langgraph.graph.state import CompiledStateGraph

from run import pretty_print_messages

# do not use this, simulates objectives already present in namespace at interruption
graph = CompiledStateGraph()


# template code below to throw into the console after an interrupt

from langgraph.types import Command

command = Command(resume="Use the report writer to slightly shorten each chapter of the report")

for event in graph.stream(command, {"configurable": {"thread_id": "1"}}, subgraphs=True, stream_mode="updates"):
    pretty_print_messages(event)
