import os
import yaml
from dotenv import load_dotenv
from langchain.tools import Tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_community.utilities.openapi import OpenAPISpec
from langchain_community.utilities import TextRequestsWrapper
from typing import List, Dict, TypedDict, Annotated
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langchain.agents import Tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents.format_scratchpad.openai_tools import format_to_openai_tool_messages
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
# from langchain.schema.runnable import RunnablePassthrough
import gradio as gr
import json
import operator

class State(TypedDict):
    messages: Annotated[List[Dict], operator.add]
    input: str
    intermediate_steps: Annotated[List[Dict], operator.add]


load_dotenv(override=True)
openai_api_key = os.getenv('OPENAI_API_KEY')


def load_openapi_specs(folder_path):
    specs = {}
    for filename in os.listdir(folder_path):
        if filename.endswith((".yaml", ".yml")):
            with open(os.path.join(folder_path, filename), "r") as f:
                try:
                  specs[filename] = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    print(f"Error loading {filename}: {e}")
    return specs

# Set the path to your folder containing OpenAPI specs
openapi_folder = "open_api_specs" # Replace with the actual path
openapi_specs = load_openapi_specs(openapi_folder)


def _create_api_tool(spec_name: str, method: str, path: str, requests_wrapper: TextRequestsWrapper) -> Tool:
    """Helper function to create a single OpenAPI tool."""
    def _tool_func(input):
        if not isinstance(input, dict) or "url" not in input:
            return "Invalid input: provide a dictionary with a URL and optionally a body"
        try:
            url = input["url"]
            headers = {"Content-Type":"application/json"}
            if method == "get":
                return requests_wrapper.get(url)
            elif method == "post":
                return requests_wrapper.post(url, headers=headers, data=json.dumps(input.get("body", {})))
            elif method == "put":
                return requests_wrapper.put(url, headers=headers, data=json.dumps(input.get("body", {})))
            elif method == "delete":
                return requests_wrapper.delete(url)
            return "Invalid method"
        except Exception as e:
            return f"Error: {e}"

    tool_name = f"API: {spec_name} - {method.upper()} {path}"
    tool_description = f"Use this to interact with the {method.upper()} endpoint {path} of the API defined in {spec_name}. Input should be a dictionary with a url and optionally a body for POST/PUT requests."
    return Tool(name=tool_name, func=_tool_func, description=tool_description)

def create_openapi_tools(specs: Dict) -> List[Tool]:
    """Creates a list of OpenAPI tools from a dictionary of specs."""
    requests_wrapper = TextRequestsWrapper()
    all_tools = []

    for spec_name, spec_dict in specs.items():
        try:
          spec = OpenAPISpec.spec(spec_dict)
          tools = [
              _create_api_tool(spec_name, method, path, requests_wrapper)
              for path, path_item in spec.paths.items()
              for method in path_item
              if method in ["get", "post", "put", "delete"]
          ]
          all_tools.extend(tools)

        except Exception as e:
            print(f"Error creating tool from {spec_name}: {e}")

    return all_tools


openapi_tools = create_openapi_tools(openapi_specs)


python_tool = PythonREPLTool()
python_tool.description = "Use this to execute python code."



# Initialize LLM, tools, and prompts
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)
tools = [
   python_tool,
]
tools.extend(openapi_tools)


prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI assistant, use tools to answer user questions."),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
    ("user", "{input}"),
])
# Define the agent's action and response logic

def format_messages(state):
    messages = state["messages"]
    inputs = state["input"]
    intermediate_steps = state.get("intermediate_steps", [])
    formatted_messages = prompt.format_messages(
        input=inputs,
        agent_scratchpad=format_to_openai_tool_messages(intermediate_steps, tools=list(map(convert_to_openai_tool,tools)))
    )
    return {"messages": formatted_messages}

def run_agent(state):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"response": response}

def parse_agent_response(state):
  response = state["response"]
  parser = OpenAIToolsAgentOutputParser()
  result = parser.parse_result(response)
  return {"action": result}


def handle_tool_call(state):
    action = state["action"]
    if action.tool_call:
      tool_name = action.tool_call.name
      tool = {tool.name:tool for tool in tools}[tool_name]
      output = tool.run(action.tool_call.arguments)
      return {"tool_output": output, "continue": True}
    else:
      return {"tool_output": None, "continue": False}
      
def update_messages(state):
    messages = state["messages"]
    action = state["action"]
    if action.tool_call:
      messages.append(action.tool_call.message)
      return {"messages":messages}
    else:
        messages.append(action.return_message)
        return {"messages":messages}

def update_intermediate_steps(state):
    intermediate_steps = state.get("intermediate_steps", [])
    action = state["action"]
    if action.tool_call:
        intermediate_steps.append(action.tool_call)
        return {"intermediate_steps":intermediate_steps}
    else:
      return {"intermediate_steps":intermediate_steps}

def tool_message(state):
    messages = state["messages"]
    tool_output = state["tool_output"]
    messages.append({"role":"tool", "content": str(tool_output), "name": state["action"].tool_call.name})
    return {"messages":messages}


# Build the LangGraph
workflow = StateGraph(State)
format_messages_node = workflow.add_node("format_messages", format_messages)
run_agent_node = workflow.add_node("run_agent", run_agent)
parse_agent_response_node = workflow.add_node("parse_agent_response", parse_agent_response)
handle_tool_call_node = workflow.add_node("handle_tool_call", handle_tool_call)
tool_message_node = workflow.add_node("tool_message", tool_message)
update_messages_node = workflow.add_node("update_messages", update_messages)
update_intermediate_steps_node = workflow.add_node("update_intermediate_steps", update_intermediate_steps)


workflow.set_entry_point(format_messages_node)
workflow.add_edge(format_messages_node, run_agent_node)
workflow.add_edge(run_agent_node, parse_agent_response_node)
workflow.add_edge(parse_agent_response_node, handle_tool_call_node)
workflow.add_conditional_edges(handle_tool_call_node, {True: tool_message_node, False: update_messages_node})
workflow.add_edge(tool_message_node, update_intermediate_steps_node)
workflow.add_edge(update_intermediate_steps_node, format_messages_node)
workflow.add_edge(update_messages_node, END)


def respond(message, history):
  response = graph.invoke({"input": message, "messages": []})
  for event in response:
    if "messages" in event and event["messages"]:
        for message in event["messages"]:
          if message["role"] == "assistant":
             history.append((message["content"], None))
          elif message["role"] == "user":
              history.append((None, message["content"]))
          elif message["role"] == "tool":
            history.append((None, f"tool: {message['content']}"))

  return history

if __name__ == '__main__':
    iface = gr.ChatInterface(respond,
        chatbot=gr.Chatbot(height = 500),
        textbox=gr.Textbox(placeholder="Ask me anything", container=False, scale=7),
        title="ReAct Agent",
        description="Ask questions about any topic.",
        theme="soft"
    )
    iface.launch()