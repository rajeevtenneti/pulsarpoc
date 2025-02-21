import logging
import sqlite3
from concurrent.futures import ProcessPoolExecutor
import time
import os
import uuid
import psutil

# Set up logging configuration
logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'run_service.log',
            'formatter': 'default'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file']
    }
})

logger = logging.getLogger(__name__)

# Set up SQLite database connection
DB_FILE = 'runs.db'
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Create table to store run status
cursor.execute('''
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        status TEXT,
        progress REAL,
        start_time REAL,
        end_time REAL,
        pid INTEGER
    )
''')
conn.commit()

def start_run(run_id, run_type, cob_date, run_group, scenario):
    try:
        # Simulate work
        logger.info(f'Starting run {run_id}...')
        cursor.execute('INSERT INTO runs (run_id, status, progress, start_time, pid) VALUES (?, ?, 0.0, ?, ?)', (run_id, 'running', time.time(), os.getpid()))
        conn.commit()

        # Simulate work using time.sleep
        time.sleep(10)

        # Update run status and progress
        cursor.execute('UPDATE runs SET status = ?, progress = ?, end_time = ? WHERE run_id = ?', ('completed', 1.0, time.time(), run_id))
        conn.commit()

        logger.info(f'Run {run_id} completed successfully!')
    except Exception as e:
        logger.error(f'Error running {run_id}: {e}')
        cursor.execute('UPDATE runs SET status = ?, end_time = ? WHERE run_id = ?', ('failed', time.time(), run_id))
        conn.commit()

def run_service(run_type, cob_date, run_group, scenario):
    # Create a new run ID
    run_id = str(uuid.uuid4())
    logger.info(f'Creating new run: {run_id}')

    # Start the run in a new process
    with ProcessPoolExecutor() as executor:
        future = executor.submit(start_run, run_id, run_type, cob_date, run_group, scenario)
        future.result()

    return run_id

def kill_run(run_id):
    try:
        # Get the PID of the process
        cursor.execute('SELECT pid FROM runs WHERE run_id = ?', (run_id,))
        row = cursor.fetchone()
        if row:
            pid = row[0]
            # Kill the process
            process = psutil.Process(pid)
            process.terminate()
            # Update the run status
            cursor.execute('UPDATE runs SET status = ? WHERE run_id = ?', ('killed', run_id))
            conn.commit()
            logger.info(f'Run {run_id} killed successfully!')
        else:
            logger.error(f'Run {run_id} not found')
    except Exception as e:
        logger.error(f'Error killing run {run_id}: {e}')

def get_run_status(run_id):
    cursor.execute('SELECT status, progress FROM runs WHERE run_id = ?', (run_id,))
    row = cursor.fetchone()
    if row:
        status = row[0]
        progress = row[1]
        return {'status': status, 'progress': progress}
    else:
        return {'error': 'Run not found'}

def get_runs():
    cursor.execute('SELECT run_id, status, progress FROM runs')
    rows = cursor.fetchall()
    runs = []
    for row in rows:
        run_id = row[0]
        status = row[1]
        progress = row[2]
        runs.append({'run_id': run_id, 'status': status, 'progress': progress})
    return runs