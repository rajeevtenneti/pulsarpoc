from flask import Flask,jsonify,request, redirect,url_for
from flask_cors import CORS
from flask_restful import Api, Resource, reqparse
from flask_swagger_ui import get_swaggerui_blueprint
import run_service
import logging

#configure logging for the main process
logging.basicConfig(filename ='logs/server.log' ,level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
api = Api(app)

SWAGGER_URL = '/swagger'
API_URL = '/static/run_swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(
 SWAGGER_URL,
 API_URL,
    config={
        'app_name': "Batch RUN API"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL) 

@app.route('/')
def index():
    return redirect(url_for('static', filename='index.html'))

# class to Start new Run
class Run(Resource):
    def post(self):
        """start a new run and return a runId"""
        parser = reqparse.RequestParser()
        parser.add_argument('type',type=str,required=True,help="Type of run that is Required")
        parser.add_argument('cob_date', type=str,required=True,help="COB_DATE is Required")        
        parser.add_argument('run_group', type=str,required=True,help="Run group  is Required")
        parser.add_argument('scenario', type=str,required=True,help="Scenario is Required")      
        args = parser.parse_args()

        run_type = args['type']
        cob_date = args['cob_date']
        run_group = args['run_group']
        scenario = args['scenario']

        logger.info(f"Strting new run: type={run_type}, cob_date={cob_date}, run_group={run_group}, scenario={scenario}")
        runId = run_service.start_run(run_type,cob_date,run_group,scenario)
        return jsonify({'runId': runId}), 201
    


# class to get run status 
class RunStatus(Resource):
    """Get the status of a run given a runId"""
    def post(self,runId):
        logger.info(f"fetching status for run_id={runId}")
        status = run_service.get_run_status(runId)
        return jsonify({'status':status}),200

class KillRun(Resource):
    """Kill a run given a runiD"""
    def post(self,runId):
        logger.info(f"Killing run_id={runId}")
        run_service.kill_run(runId)
        return jsonify({'message': 'run killed successfully'}),200
    
api.add_resource(Run,'/run')
api.add_resource(RunStatus,'/run/<string:runId>/status')
api.add_resource(KillRun, '/run/<string:runId>/kill')

if __name__ == '__main__':
    run_service.initialize()
    app.run(port=5000,debug=True)
