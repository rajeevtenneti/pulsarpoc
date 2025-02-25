from flask import Flask, request, jsonify, send_file
from flask_restx import Api, Resource
import os
import yaml
from urllib.parse import urljoin
from werkzeug.utils import secure_filename

app = Flask(__name__)

with open('open_api_specs/resultsservice.yaml', 'r') as f:
    swagger_data = yaml.safe_load(f)
api = Api(app, version='1.0', title='Batch Results API',
          description='API to serve Batch Results',
          **swagger_data)

# Define the namespace
excel_ns = api.namespace('results', description='Operations to Retrive Batch Results')
# Define the path to your files, assuming they are in the same directory as your script
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATASETS_DIR = os.path.join(BASE_DIR, "Datasets")
DS1_PATH = os.path.join(DATASETS_DIR, "CCAR_Results.xlsx")
DS2_PATH = os.path.join(DATASETS_DIR, "CECL_Results.xlsx")



@excel_ns.route('/stressResults')
class StressResults(Resource):
    @excel_ns.doc(description="Get Stress Results")
    def get(self):
        """Get stress results and provide a clickable link."""
        #Extract parameters
        runtype = request.args.get('runtype')
        cob = request.args.get('cob')
        scenario = request.args.get('scenario')

        base_url = request.base_url  # Get the base URL of the request
        # Construct full URL for the file
        file_url = urljoin(base_url.replace('/stressResults', ''), f'download/{secure_filename("CCAR_Results.xlsx")}')
        
        return {'link': file_url}, 200


@excel_ns.route('/allowanceResults')
class AllowanceResults(Resource):
    @excel_ns.doc(description="Get Allowance Results")
    def get(self):
        """Get allowance results and provide a downloadable link."""
         #Extract parameters
        runtype = request.args.get('runtype')
        cob = request.args.get('cob')
        scenario = request.args.get('scenario')
        
        base_url = request.base_url  # Get the base URL of the request
        # Construct full URL for the file
        file_url = urljoin(base_url.replace('/allowanceResults', ''), f'download/{secure_filename("CECL_Results.xlsx")}')
        
        return {'link': file_url}, 200


@app.route('/download/<filename>')
def download_file(filename):
    """Serve the requested file."""
    if filename == "CCAR_Results.xlsx":
         file_path = DS1_PATH
    elif filename == "CECL_Results.xlsx":
        file_path = DS2_PATH
    else:
         return "File Not Found", 404

    if not os.path.exists(file_path):
        return "File Not Found", 404
    return send_file(file_path, as_attachment=True)


if __name__ == '__main__':
    # Create dummy excel files for testing
    # import pandas as pd
    # if not os.path.exists(DS1_PATH):
    #     df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
    #     df.to_excel(DS1_PATH, index=False)
    # if not os.path.exists(DS2_PATH):
    #     df = pd.DataFrame({"colA": [5, 6], "colB": [7, 8]})
    #     df.to_excel(DS2_PATH, index=False)
    app.run(debug=True, port=5001)