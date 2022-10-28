from flask import Flask
from flask import render_template


#hack to add probe utlities module
import sys
from pathlib import Path
PROBE_UTILITIES_DIR = str(Path(__file__).parent.parent.resolve())
print(PROBE_UTILITIES_DIR)
sys.path.append(PROBE_UTILITIES_DIR)
import probe_utilities


app = Flask(__name__, template_folder='template', static_folder='template/assets')


@app.route("/")
def hello_world():
    info = probe_utilities.get_system_information()
    system_info = {
        'uptime' : info.get('uptime'),
        'temperature' : info.get('temp')
    }

    #return "<p>Hello, World!</p>"
    return render_template('index.html', system_info = system_info)
