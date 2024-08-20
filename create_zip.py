from pyscript import display
from pyweb import pydom
import json
import pandas as pd
from pyodide.ffi import create_proxy,to_js
###########
import sys
import os


# create download button and serve templates as text files
from js import Uint8Array, File, URL, document
import io
from pyodide.ffi.wrappers import add_event_listener

def create_download_button(file_of_interest=None):
    if file_of_interest is not None:
        f1 = open(file_of_interest,"rb")
        data = f1.read()
        f1.close() 
        encoded_data = data
        my_stream = io.BytesIO(data)
    
        js_array = Uint8Array.new(len(encoded_data))
        js_array.assign(my_stream.getbuffer())
    
        file = File.new([js_array], file_of_interest, {type: "application/octet-stream"})
        url = URL.createObjectURL(file)
        # hide download button if it exists
        #if document.getElementById("requeue-template-download") is not None:
        pydom["div#analysis-step-metadata-download"].style["display"] = "none"

        #downloadDoc = document.createElement('a')
        downloadDoc = document.getElementById('analysis-step-metadata-download-child')
        downloadDoc.href = window.URL.createObjectURL(file)

        ############## hard-coded in html to avoid creating mutliple buttons
        #downloadButton = document.createElement('button')
        #downloadButton.innerHTML = "Download Requeue Template"
        #downloadDoc.appendChild(downloadButton)
        ##############
        
        document.getElementById("analysis-step-metadata-download").appendChild(downloadDoc)
        downloadDoc.setAttribute("download", file_of_interest)
        pydom["div#analysis-step-metadata-download"].style["display"] = "block"
    else:
        print("Nothing to do")
    return 0 

###### stage log files from above
async def create_log_archive(event):
    pydom["div#analysis-step-metadata-download"].style["display"] = "block"
    ######  create ZIP file
    with open('analysis_metadata.json') as f:
        analysis_metadata= json.load(f)

    dir_name = f"analysis_id_{analysis_metadata['analysis_id']}"
    output_zip = f"analysis_id_{analysis_metadata['analysis_id']}.zip"
    import shutil
    shutil.make_archive(dir_name, 'zip', dir_name)

    print('Current Working directory contents:')
    files = os.listdir(os.getcwd()+f"/{dir_name}")
    for file in files:
        print(file)

    print('Root Working directory contents:')
    files = os.listdir("./")
    for file in files:
        print(file)

    create_download_button(file_of_interest = output_zip)
    step6_message = "ZIP file contains logs when extracted/unzipped <br><br> The <code>analysis_logs</code> directory contains logs from pipeline run <br><br> The <code>ica_logs</code> directory contains all logs, metric files, and configuration files for the entire workflow <br><br> To start troubleshooting <code>analysis_metadata.json</code> will contain <code>project_id, analysis_id, and domain_name of the ICA analysis in question</code> <br><br> The file <code>analysis_info.json</code> contains output from <code>https://ica.illumina.com/ica/api/swagger/index.html#/Project%20Analysis/getAnalysis</code> <br><br> The file <code>step_metadata.json</code> contains start, end, exit status of each step in your pipeline <br><br> For visualization purposes <code>mermaid_gantt.txt</code> can be used by mermaid.js to visualize the timeine of your pipeline <br>"
    pydom["h1#step6-message"].html = step6_message
    pydom["h1#step6-message"].style["display"] = "block"
    return display("STEP5 complete",target ="download-ready",append="True")