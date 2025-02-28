import os
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import yaml
from langchain import PromptTemplate, LLMChain, OpenAI
from langchain.agents import AgentExecutor, AgentType
from langchain.agents.agent_toolkits import create_python_agent
from langchain.tools.python.tool import PythonREPLTool
from langgraph import LangGraph, ToolNode, CustomNode
from gradio import Interface, Chatbot

# --- OpenAPI Spec Parser ---
class Endpoint(BaseModel):
    path: str
    method: str
    parameters: List[Dict] = Field(default_factory=list)

class OpenAPISpecInterpreter:
    def __init__(self, openapi_dir: str):
        self.openapi_dir = openapi_dir
        self.llm = OpenAI(temperature=0)

    def interpret_spec(self, filename: str) -> List[Endpoint]:
        with open(f"{self.openapi_dir}/{filename}", "r") as f:
            openapi_spec = yaml.safe_load(f)

        prompt_template = """
            Extract all endpoints from the given OpenAPI specification (YAML or JSON).
            Return the list of endpoints in JSON format, with each endpoint having:
            - path: The URL path of the endpoint.
            - method: The HTTP method (GET, POST, etc.).
            - parameters: A list of parameters with their names and types.

            OpenAPI Specification:
            {openapi_spec}
        """
        prompt = PromptTemplate(template=prompt_template, input_variables=["openapi_spec"])
        llm_chain = LLMChain(llm=self.llm, prompt=prompt)
        response = llm_chain.run(openapi_spec=openapi_spec)
        endpoints = [Endpoint(**endpoint_data) for endpoint_data in response]  # type: ignore
        return endpoints

    def interpret_specs(self) -> Dict[str, List[Endpoint]]:
        all_endpoints = {}
        for filename in os.listdir(self.openapi_dir):
            if filename.endswith(".yaml"):
                spec_name = filename[:-5]  # Remove .yaml extension
                endpoints = self.interpret_spec(filename)
                all_endpoints[spec_name] = endpoints
        return all_endpoints

    def __call__(self, spec_name: str) -> List[Endpoint]:
        all_endpoints = self.interpret_specs()
        return all_endpoints.get(spec_name, [])

# --- Supervisor ---
class SupervisorNode(CustomNode):
    def __init__(self, openapi_interpreter: OpenAPISpecInterpreter):
        super().__init__(function=self.select_endpoint)
        self.openapi_interpreter = openapi_interpreter

    def select_endpoint(self, user_input: str, spec_name: str) -> str:
        # Placeholder for endpoint selection logic
        endpoints = self.openapi_interpreter(spec_name)
        # ... (Logic to select endpoint based on user_input and endpoints) ...
        selected_endpoint = endpoints[0].path  # Replace with actual selection
        return selected_endpoint

# --- Python Code Generator ---
def generate_python_code(endpoint: Endpoint, params: Dict) -> str:
    method = endpoint.method.lower()
    code = f"""
        import requests

        url = "{endpoint.path}"
        params = {params}

        if method == "get":
            response = requests.get(url, params=params)
        elif method == "post":
            response = requests.post(url, json=params)  # Assuming JSON for POST
        elif method == "delete":
            response = requests.delete(url, params=params)
        # ... (add other methods as needed)

        print(response.json())
    """
    return code

# --- Python Code Executor ---
def execute_python_code(code: str):
    # In a real-world scenario, use a sandbox environment for security.
    exec(code, {"requests": __import__("requests")})

# --- Main Execution ---
if __name__ == "__main__":
    # Initialize components
    openapi_interpreter = OpenAPISpecInterpreter("../open_api_specs/")  # Replace with your directory
    supervisor_node = SupervisorNode(openapi_interpreter)
    llm = OpenAI(temperature=0)
    python_tool = PythonREPLTool()
    tools = [python_tool]
    agent = create_python_agent(llm, tools, agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
    agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)
    tool_node = ToolNode(name="Python REPL", function=agent_executor.run)

    # Build LangGraph
    graph = LangGraph()
    graph.add_node(supervisor_node)
    graph.add_node(tool_node)
    graph.add_edge(supervisor_node.node_id, tool_node.node_id, edge_condition="always")

    # Gradio Chatbot Interface
    def chatbot_function(message, history):
        # Get spec name and parameters from user input (replace with your logic)
        spec_name = "your_spec_name"  # Replace with how you extract spec name
        params = {}  # Replace with how you extract parameters
        
        response = graph.execute(
            {"user_input": message, "spec_name": spec_name, "params": params},
            start_node_id=supervisor_node.node_id,
        )
        history.append((message, response))
        return history, history

    iface = Interface(
        fn=chatbot_function,
        inputs=Chatbot(),
        outputs=Chatbot(),
        title="LangGraph Chatbot with OpenAI",
    )

    iface.launch()