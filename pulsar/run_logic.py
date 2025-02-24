# Function to read Swagger OpenAPI specifications from a folder
import os
import subprocess

def read_openapi_specs(folder_path):
    specs = {}
    for filename in os.listdir(folder_path):
        if filename.endswith(".yaml") or filename.endswith(".json"):
            with open(os.path.join(folder_path, filename), 'r') as file:
                specs[filename] = file.read()
    return specs



# Function to create Python scripts to execute API endpoints
def create_api_scripts(specs):
    scripts = {}
    for filename, spec in specs.items():
        # Here you would parse the OpenAPI spec and generate the Python script
        # For simplicity, we'll just create a dummy script
        script_content = f"""
import requests

def call_api():
    response = requests.get('http://example.com/api')
    return response.json()
"""
        scripts[filename] = script_content
    return scripts


# Function to execute a Python script in a subprocess
def execute_script(script_content):
    with open("temp_script.py", "w") as file:
        file.write(script_content)
    result = subprocess.run(["python", "temp_script.py"], capture_output=True, text=True)
    #os.remove("temp_script.py")
    return result.stdout
