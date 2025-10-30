from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage

import dataiku
from dataiku.llm.python import BaseLLM

OPENAI_CONNECTION_NAME = "REPLACE_BY_YOUR_OPENAI_CONNECTION_NAME"

@tool
def add(a: int, b: int) -> int:
    """Adds a and b."""
    return a + b

@tool
def multiply(a: int, b: int) -> int:
    """Multiplies a and b."""
    return a * b

tools = [add, multiply]

# add a visual tool
project = dataiku.api_client().get_default_project()
project_visual_tools = project.list_agent_tools()

def find_tool(name: str) -> object:
    for tool in project_visual_tools:
        if tool["name"] == name:
            return project.get_agent_tool(tool['id'])
    return None

visual_tool = find_tool("Calculator") # use any visual tool by name
if visual_tool:
    tools.append(visual_tool.as_langchain_structured_tool())


class MyLLM(BaseLLM):
    def __init__(self):
        pass

    def process(self, query, settings, trace):
        llm = dataiku.api_client().get_default_project().get_llm(f"openai:{OPENAI_CONNECTION_NAME}:gpt-5-mini").as_langchain_chat_model(completion_settings=settings)
        llm_with_tools = llm.bind_tools(tools)

        messages = [m for m in query["messages"] if m.get("content")]
        iterations = 0
        while True:
            iterations += 1
            
            if iterations < 10:
                with trace.subspan("Invoke LLM with tools") as llm_invoke_span:
                    llm_response = llm_with_tools.invoke(messages)
            else:
                with trace.subspan("Invoke LLM without tools") as llm_invoke_span:
                    llm_response = llm.invoke(messages)

            if len(llm_response.tool_calls) == 0:
                return {"text": llm_response.content}
            
            with llm_invoke_span.subspan("Call the tools") as tools_subspan:
                messages.append(llm_response)
                for tool_call in llm_response.tool_calls:
                    with tools_subspan.subspan("Call a tool") as tool_subspan:
                        tool_subspan.attributes["tool_name"] = tool_call["name"]
                        tool_subspan.attributes["tool_args"] = tool_call["args"]
                        if tool_call["name"] == "add":
                            tool_output = add(tool_call["args"])
                        elif tool_call["name"] == "multiply":
                            tool_output = multiply(tool_call["args"])
                        elif visual_tool:
                            tool_output = visual_tool.run(tool_call["args"])
                    messages.append(ToolMessage(tool_call_id =tool_call["id"], content=tool_output))
    