# app.py
from flask import Flask, request, jsonify, Response
from flask_restx import Api, Resource, fields
import uuid
import time
import threading
import os
import yaml

app = Flask(__name__)
with open('open_api_specs/batchservice.yaml', 'r') as f:
    swagger_data = yaml.safe_load(f)
api = Api(app, version='1.0', title='Batch Run API',
          description='API to manage Batch runs',
           **swagger_data
          )

# Data structures to keep track of runs
runs = {}
run_logs = {}

# Define the 'runs' namespace for endpoints
runs_ns = api.namespace('runs', description='Operations related to runs')


class Run:
    def __init__(self, run_id, run_type, run_scenario, cob_date, run_group):
        self.run_id = run_id
        self.status = "pending"
        self.log_file = f"run_{run_id}.log"  # Simple log file path
        self.run_type = run_type
        self.run_scenario = run_scenario
        self.cob_date = cob_date
        self.run_group = run_group



run_input_model = api.model('RunInput', {
    'runType': fields.String(required=True, enum=['CCAR', 'RiskApetite', 'Stress'], description="Type of the run"),
    'runScenario': fields.String(default="Base", description="Scenario for the run"),
    'cobDate': fields.String(default="20240724", description="Cut-off date for the run"),
    'runGroup': fields.String(default="default_group", description="Group for the run")
})



@runs_ns.route('/')
class Runs(Resource):
    @runs_ns.doc(description="Start a dummy run", body=run_input_model)
    def post(self):
        data = request.get_json()
        run_id = str(uuid.uuid4())
        run_type = data.get('runType')
        run_scenario = data.get('runScenario', 'Base')
        cob_date = data.get('cobDate', '20240724')
        run_group = data.get('runGroup', 'default_group')
        run = Run(run_id, run_type, run_scenario, cob_date, run_group)
        runs[run_id] = run
        # Create the log file and add a starting log message
        with open(run.log_file, 'w') as f:
            f.write(f"Run {run_id} started at {time.ctime()}\n")
            f.write(f"Run Type: {run.run_type}, Scenario: {run.run_scenario}, Cob Date: {run.cob_date}, Group: {run.run_group}\n")
        run_logs[run_id] = run.log_file
         # Run the dummy run in a thread
        thread = threading.Thread(target=dummy_run, args=(run,))
        thread.start()
        return {'runId': run_id}, 201

@runs_ns.route('/<string:run_id>')
class RunById(Resource):
    @runs_ns.doc(params={'run_id': 'ID of the run'})
    def get(self, run_id):
        """Get the status of a run."""
        if run_id not in runs:
            return {'message': 'Run not found'}, 404
        return {'status': runs[run_id].status}, 200

    @runs_ns.doc(params={'run_id': 'ID of the run to kill'})
    def delete(self, run_id):
        """Kill a run."""
        if run_id not in runs:
           return {'message': 'Run not found'}, 404
        runs[run_id].status = "killed"
        with open(runs[run_id].log_file, 'a') as f:
           f.write(f"Run {run_id} killed at {time.ctime()}\n")

        return '', 200


@runs_ns.route('/<string:run_id>/log')
class RunLog(Resource):
    @runs_ns.doc(params={'run_id': 'ID of the run'})
    def get(self, run_id):
        """Get the log file for a run."""
        if run_id not in runs:
            return {'message': 'Run not found'}, 404
        
        log_file = runs[run_id].log_file
        if not os.path.exists(log_file):
             return {'message': 'Log file not found'}, 404
        
        def generate():
            with open(log_file, 'r') as f:
                yield from f
        return Response(generate(), mimetype='text/plain')


def dummy_run(run):
    """Simulates a dummy run, updating status and log."""
    run.status = "running"
    with open(run.log_file, 'a') as f:
        f.write(f"Run {run.run_id} is running...\n")
    time.sleep(10)
    if run.status != "killed":
        run.status = "completed"
        with open(run.log_file, 'a') as f:
            f.write(f"Run {run.run_id} completed at {time.ctime()}\n")


if __name__ == '__main__':
    app.run(debug=True, port=5000)