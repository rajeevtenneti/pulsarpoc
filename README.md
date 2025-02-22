# pulsarpoc
#  Below instructions for the setup  of BatchRun API 
cd BatchRun
## Create virtual environment 
python -m venv poc 
## use requirements.txt to install all required modules 
source poc/bin/activate.csh

pip install -r requirements.txt

python server.py 

