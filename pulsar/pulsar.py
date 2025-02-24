import os
import openai
import gradio as gr
import requests
import subprocess
from dotenv import load_dotenv
import json

load_dotenv()
# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")



# Chatbot function
def chatbot(input_text):
    # Read OpenAPI specs
    specs = read_openapi_specs("swagger_yamls")
    # Create API scripts
    scripts = create_api_scripts(specs)
    # Execute scripts and collect results
    results = {}
    for filename, script_content in scripts.items():
        result = execute_script(script_content)
        results[filename] = result
    # Generate response using OpenAI
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=f"User input: {input_text}\nAPI results: {json.dumps(results)}",
        max_tokens=150
    )
    return response.choices[0].text.strip()

# Gradio interface
iface = gr.Interface(
    fn=chatbot,
    inputs="text",
    outputs="text",
    title="Pulsar Chatbot",
    description="Explore SuperNova with Pulsar"
)

iface.launch()