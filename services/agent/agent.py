import json
from typing import TypedDict, Annotated, Sequence, List
import operator
import time

try:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolExecutor, ToolInvocation
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

import tools as agent_tools

# 1. Define State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    supplier_id: str
    actions_taken: List[str]

if HAS_LANGGRAPH:
    # 2. Define Tools List
    tools = [
        agent_tools.get_supplier_risk,
        agent_tools.get_affected_skus,
        agent_tools.trigger_reroute,
        agent_tools.check_inventory,
        agent_tools.escalate_to_human,
        agent_tools.generate_incident_report
    ]

    tool_executor = ToolExecutor(tools)
    
    # 3. LLM Setup (Anthropic Claude 3 Haiku for speed)
    model = ChatAnthropic(temperature=0, model_name="claude-3-haiku-20240307")
    model = model.bind_tools(tools)

    # 4. Define Nodes
    def call_model(state: AgentState):
        messages = state['messages']
        response = model.invoke(messages)
        return {"messages": [response]}

    def call_tool(state: AgentState):
        messages = state['messages']
        last_message = messages[-1]
        
        # Parse tool calls
        tool_calls = last_message.tool_calls
        responses = []
        actions = state.get('actions_taken', [])
        
        for tool_call in tool_calls:
            action = ToolInvocation(
                tool=tool_call['name'],
                tool_input=tool_call['args']
            )
            response = tool_executor.invoke(action)
            actions.append(f"Used tool: {tool_call['name']}")
            responses.append(
                AIMessage(content=str(response), name=tool_call['name'], role="tool", tool_call_id=tool_call['id'])
            )
            
        return {"messages": responses, "actions_taken": actions}

    def should_continue(state: AgentState):
        messages = state['messages']
        last_message = messages[-1]
        if not last_message.tool_calls:
            return "end"
        return "continue"

    # 5. Build Graph
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("action", call_tool)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "action",
            "end": END
        }
    )
    workflow.add_edge("action", "agent")

    app = workflow.compile()


class AgentRunner:
    @staticmethod
    def run_for_supplier(supplier_id: str) -> dict:
        """Run the autonomous agent for a specific supplier."""
        start_time = time.time()
        
        if not HAS_LANGGRAPH:
            return {
                "agent_run_id": "mock-run-123",
                "supplier_id": supplier_id,
                "actions_taken": ["Evaluated risk (mock)", "Rerouted SKUs (mock)", "Generated report (mock)"],
                "final_status": "completed",
                "duration_ms": 150
            }
        
        system_prompt = f"""You are an autonomous Supply Chain Analyst Agent.
Your job is to investigate risk alerts for supplier {supplier_id}.
1. Get supplier risk. If risk < 0.6, do nothing and generate report.
2. If risk >= 0.6, get affected SKUs and check inventory for each.
3. If any SKU has < 14 days of stock remaining, trigger reroute immediately.
4. If reroute fails or NO alternatives exist, escalate to human.
5. Always generate an incident report at the end detailing your findings.
"""
        inputs = {
            "messages": [SystemMessage(content=system_prompt), HumanMessage(content=f"Investigate {supplier_id}")],
            "supplier_id": supplier_id,
            "actions_taken": []
        }
        
        output = app.invoke(inputs)
        
        return {
            "agent_run_id": f"run_{supplier_id}_{int(time.time())}",
            "supplier_id": supplier_id,
            "actions_taken": output.get('actions_taken', []),
            "final_status": "completed",
            "duration_ms": int((time.time() - start_time) * 1000)
        }
