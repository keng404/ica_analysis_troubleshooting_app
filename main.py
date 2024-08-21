##########
import asyncio
from js import document,alert,console,window
from pyodide.http import pyfetch,open_url
from pyscript import display
from pyweb import pydom
import json
import pandas as pd
from pyodide.ffi import create_proxy,to_js
###########
import sys
import os
import websockets
from websockets import exceptions
########################
#from pprint import pprint
from datetime import datetime as dt
####################################
from tempfile import NamedTemporaryFile
import webbrowser
###############
from collections import OrderedDict
from operator import itemgetter
import re
###############
step1_message = "STEP1: Login using your ICA credentials"
pydom["h1#step1-message"].html = step1_message
step2_message = "STEP2: Identify ICA project to get ICA project id <br> Use search bar to query table <br> once project is found, below the table enter a project name and click on the 'Select Project' button"
pydom["h1#step2-message"].html = step2_message
step3_message = "STEP3: Identify analysis to get ICA analysis id <br> Use search bar to query table <br> once project is found, below the table enter an analysis name, and click on the 'Select Analysis' button"
pydom["h1#step3-message"].html = step3_message

step4_message = "STEP4: Start troubleshooting analysis"
pydom["h1#step4-message"].html = step4_message

step5_message = "STEP5: Download Analysis logs for all troubleshooting<br>A ZIP file containing all stderr/stdout logs for your analysis will be available for download"
pydom["h1#step5-message"].html = step5_message
#######################
### hide elements until we are ready
pydom["div#step2-selection-form"].style["display"] = "none"
pydom["div#step3-selection-form"].style["display"] = "none"
#pydom["div#step4-selection"].style["display"] = "none"
pydom["div#step4-selection-form"].style["display"] = "none"
pydom["pre#gantt-chart"].style['display'] = "none"
#pydom["div#requeue-template-download"].style["display"] = "none"
#pydom["section#learn-the-steps"].style["display"] = "none"
#pydom["div#troubleshoot-download"].style['display'] = "none"
pydom["div#analysis-step-metadata-download"].style["display"] = "none"
pydom["div#analyses-metadata-output"].style["display"] = "none"
pydom["div#step6-selection-form"].style["display"] = "none"
pydom["h1#step6-message"].style["display"] = "none"
################
ICA_BASE_URL = 'https://ica.illumina.com/ica'
import base64
#### info we'll collect from the html 
authorization_metadata = dict()
analysis_metadata = dict()
analysis_metadata['step4-api'] = []
##########################
async def curlify(method="GET",endpoint="FOOBAR",header={},body={}):
    curlified_command_components = []
    curlified_command_components.append(f"curl -X '{method}' \\")
    curlified_command_components.append(f" '{endpoint}' \\")
    for key in list(header.keys()):
        curlified_command_components.append(f"-H '{key}:" + f" {header[key]}' \\")
    if len(body) > 0:
        rest_of_command = json.dumps(body, indent = 4)
        curlified_command_components.append(f"-d '{rest_of_command}'")
    # strip out any trailing slashes
    curlified_command_components[len(curlified_command_components)-1].strip('\\')
    curlified_command = "\n".join(curlified_command_components)
    print(f"{curlified_command}")
    return curlified_command

### helper functons to paginate pandas tables

def df_html(df):
    """HTML table """
    df_html = df.to_html()
    return df_html

##################    
async def get_jwt(username,password,tenant = None):
    #######
    encoded_key = base64.b64encode(bytes(f"{username}:{password}", "utf-8")).decode()
    ################ Get JWT
    api_base_url = ICA_BASE_URL + "/rest"
    if tenant is not None:
        TENANT_NAME = tenant
        token_endpoint = f"/api/tokens?tenant={TENANT_NAME}"
    else:
        token_endpoint = f"/api/tokens"
    init_headers = dict()
    init_headers['accept'] = 'application/vnd.illumina.v3+json'
    #init_headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    init_headers['Authorization'] = f"Basic {encoded_key}"
    token_url = api_base_url + token_endpoint
    ##############
    #display(token_url)
    #display(init_headers)
    response = await pyfetch(url=token_url,method = 'POST',headers=init_headers)
    curl_command = await curlify(method="POST",endpoint=token_url,header=init_headers)
    analysis_metadata['step1-api'] = curl_command
    status = f"Request status: {response.status}"
    #display(status)
    jwt = await response.json()
    #display(jwt)
    if 'token' not in jwt.keys():
        print(jwt)
        raise ValueError(f"Could not get JWT for user: {username}\nPlease double-check username and password.\nYou also may need to enter a domain name")
    return jwt['token']
#########################################
async def list_projects(jwt_token,max_retries=20):
    # List all analyses in a project
    pageOffset = 0
    pageSize = 1000
    page_number = 0
    number_of_rows_to_skip = 0
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects?pageOffset={pageOffset}&pageSize={pageSize}&includeHiddenProjects=true"
    projects_metadata = []
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    try:
        #display(full_url)
        projectPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
        ##########################
        curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
        analysis_metadata['step2-api'] = curl_command
        ################################
        projectPagedListResponse = await projectPagedList.json()
        totalRecords = projectPagedListResponse['totalItemCount']
        response_code = projectPagedList.status
        while page_number * pageSize < totalRecords:
            endpoint = f"/api/projects/?pageOffset={number_of_rows_to_skip}&pageSize={pageSize}&includeHiddenProjects=true"
            full_url = api_base_url + endpoint  ############ create header
            projectPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
            projectPagedListResponse = await projectPagedList.json()
            for project in projectPagedListResponse['items']:
                #display(str(project))
                projects_metadata.append([project['name'], project['id']])
            page_number += 1
            number_of_rows_to_skip = page_number * pageSize
    except:
        raise ValueError(f"Could not get projects")
    return projects_metadata
##########################################
async def get_project_id(jwt_token, project_name):
    projects = []
    pageOffset = 0
    pageSize = 30
    page_number = 0
    number_of_rows_to_skip = 0
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects?search={project_name}&includeHiddenProjects=true&pageOffset={pageOffset}&pageSize={pageSize}"
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    try:
        projectPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
        projectPagedListResponse = await projectPagedList.json()
        totalRecords = projectPagedListResponse['totalItemCount']
        while page_number * pageSize < totalRecords:
            projectPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
            for project in projectPagedListResponse['items']:
                projects.append({"name": project['name'], "id": project['id']})
            page_number += 1
            number_of_rows_to_skip = page_number * pageSize
    except:
        raise ValueError(f"Could not get project_id for project: {project_name}")
    if len(projects) > 1:
        raise ValueError(f"There are multiple projects that match {project_name}")
    else:
        return projects[0]['id']

#########

############
async def list_project_analyses(jwt_token,project_id,max_retries=20):
    # List all analyses in a project
    pageOffset = 0
    pageSize = 1000
    page_number = 0
    number_of_rows_to_skip = 0
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analyses?pageOffset={pageOffset}&pageSize={pageSize}"
    analyses_metadata = []
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    analysis_metadata['metadata_by_analysis_id'] = dict()
    analysis_metadata['metadata_by_analysis_name'] = dict()
    try:
        projectAnalysisPagedList = None
        response_code = 404
        num_tries = 0
        while response_code != 200 and num_tries  < max_retries:
            num_tries += 1
            if num_tries > 1:
                print(f"NUM_TRIES:\t{num_tries}\tTrying to get analyses  for project {project_id}")
            projectAnalysisPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
            ##############
            curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
            analysis_metadata['step3-api'] = curl_command
            ###################
            projectAnalysisPagedList_response = await projectAnalysisPagedList.json()
            totalRecords = projectAnalysisPagedList_response['totalItemCount']
            response_code = projectAnalysisPagedList.status
            while page_number * pageSize < totalRecords:
                endpoint = f"/api/projects/{project_id}/analyses?pageOffset={number_of_rows_to_skip}&pageSize={pageSize}"
                full_url = api_base_url + endpoint  ############ create header
                projectAnalysisPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
                projectAnalysisPagedList_response = await projectAnalysisPagedList.json()
                my_count = 0
                for analysis in projectAnalysisPagedList_response['items']:   
                    ### add lookup dict objects for faster querying later .... 
                    analysis_metadata['metadata_by_analysis_id'][analysis['id']]  = analysis  
                    analysis_metadata['metadata_by_analysis_name'][analysis['userReference']]  = analysis   
                    ### store list of analyses metadata
                    analyses_metadata.append(analysis)
                page_number += 1
                number_of_rows_to_skip = page_number * pageSize
    except:
        raise ValueError(f"Could not get analyses for project: {project_id}")
    return analyses_metadata
################
def subset_analysis_metadata_list(analysis_metadata_list):
    subset_metadata = []
    for analysis in analysis_metadata_list:
        my_subset = []
        if 'startDate' in analysis.keys():
            my_subset = [analysis['userReference'],analysis['id'],analysis['startDate'],analysis['status'],analysis['pipeline']['code']]
        else:
            my_subset = [analysis['userReference'],analysis['id'],'1970-01-01T01:00:00Z',analysis['status'],analysis['pipeline']['code']]                            
        subset_metadata.append(my_subset)
    return subset_metadata

##################
async def get_project_analysis_id(jwt_token,project_id,analysis_name):
    desired_analyses_status = ["REQUESTED","INPROGRESS","SUCCEEDED","FAILED"]
    analysis_id  = None
    analyses_list = await list_project_analyses(jwt_token,project_id)
    if analysis_name is not None:
        for aidx,project_analysis in enumerate(analyses_list):
            name_check  = project_analysis['userReference'] == analysis_name 
            status_check = project_analysis['status'] in desired_analyses_status
            # and project_analysis['status'] in desired_analyses_status
            if project_analysis['userReference'] == analysis_name:
                analysis_id = project_analysis['id']
                return analysis_id
    else:
        idx_of_interest = 0
        status_of_interest = analyses_list[idx_of_interest]['status'] 
        current_analysis_id = analyses_list[idx_of_interest]['id'] 
        while status_of_interest not in desired_analyses_status:
            idx_of_interest = idx_of_interest + 1
            status_of_interest = analyses_list[idx_of_interest]['status'] 
            current_analysis_id = analyses_list[idx_of_interest]['id'] 
            print(f"analysis_id:{current_analysis_id} status:{status_of_interest}")
        default_analysis_name = analyses_list[idx_of_interest]['userReference']
        print(f"No user reference provided, will poll the logs for the analysis {default_analysis_name}")
        analysis_id = analyses_list[idx_of_interest]['id']
    return analysis_id

####################

#############################
async def get_pipeline_id(pipeline_code, jwt_token,project_name,project_id=None):
    pipelines = []
    pageOffset = 0
    pageSize = 1000
    page_number = 0
    number_of_rows_to_skip = 0
    # ICA project ID
    if project_id is None:
        project_id = await get_project_id(jwt_token,project_name)
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/pipelines?pageOffset={pageOffset}&pageSize={pageSize}"
    full_url = api_base_url + endpoint	############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    try:
        #print(f"FULL_URL: {full_url}")
        pipelinesPagedList =  await pyfetch(full_url, method='GET', headers=headers)
        #####
        curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab pipeline identifier</h3><br>This tells ICA what pipeline to run. Via the CLI you can just provide the [ PIPELINE_NAME ] in single quotes instead of the pipeline id<br>" + curl_command)
        #####     
        pipelinesPagedList_response = await pipelinesPagedList.json()
        if 'totalItemCount' in pipelinesPagedList_response.keys():
            totalRecords = pipelinesPagedList_response['totalItemCount']
            while page_number*pageSize <  totalRecords:
                endpoint = f"/api/projects/{project_id}/pipelines?pageOffset={number_of_rows_to_skip}&pageSize={pageSize}"
                full_url = api_base_url + endpoint  ############ create header
                #print(f"FULL_URL: {full_url}")
                pipelinesPagedList =  await pyfetch(full_url, method='GET', headers=headers)
                pipelinesPagedList_response = await pipelinesPagedList.json()
                for pipeline_idx,pipeline in enumerate(pipelinesPagedList_response['items']):
                    pipelines.append({"code":pipeline['pipeline']['code'],"id":pipeline['pipeline']['id']})
                page_number += 1
                number_of_rows_to_skip = page_number * pageSize
        else:
            for pipeline_idx,pipeline in enumerate(pipelinesPagedList_response['items']):
                pipelines.append({"code": pipeline['pipeline']['code'], "id": pipeline['pipeline']['id']})
    except:
        raise ValueError(f"Could not get pipeline_id for project: {project_name} and name {pipeline_code}\n")
    for pipeline_item, pipeline in enumerate(pipelines):
        # modify this line below to change the matching criteria ... currently the pipeline_code must exactly match
        if pipeline['code'] == pipeline_code:
             pipeline_id = pipeline['id']
    return pipeline_id


#######################


async def get_analysis_storage_id(jwt_token, storage_label=""):
    storage_id = None
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/analysisStorages"
    full_url = api_base_url + endpoint	############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    try:
        # Retrieve the list of analysis storage options.
        api_response = await pyfetch(full_url, method = 'GET', headers=headers)
        #####
        curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab analysis storage identifier</h3><br>This sets the size of result data that can be sent back to ICA<br>" + curl_command)
        #####        
        api_responses = await api_response.json()
        #pprint(api_response, indent = 4)
        if storage_label not in ['Large', 'Medium', 'Small','XLarge','2XLarge','3XLarge']:
            print("Not a valid storage_label\n" + "storage_label:" + str(storage_label))
            raise ValueError
        else:
            for analysis_storage_item, analysis_storage in enumerate(api_responses['items']):
                if analysis_storage['name'] == storage_label:
                    storage_id = analysis_storage['id']
                    return storage_id
    except :
        raise ValueError(f"Could not find storage id based on {storage_label}")


#### Conversion functions
async def convert_data_inputs(data_inputs):
    converted_data_inputs = []
    for idx,item in enumerate(data_inputs):
        converted_data_input = {}
        converted_data_input['parameterCode'] = item['parameter_code']
        converted_data_input['dataIds'] = item['data_ids']
        converted_data_inputs.append(converted_data_input)
    return converted_data_inputs

async def get_activation_code(jwt_token,project_id,pipeline_id,data_inputs,input_parameters,workflow_language):
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/activationCodes:findBestMatchingFor{workflow_language}"
    full_url = api_base_url + endpoint
    #print(full_url)
    ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    ######## create body
    collected_parameters = {}
    collected_parameters["pipelineId"] = pipeline_id
    collected_parameters["projectId"] = project_id
    collected_parameters["analysisInput"] = {}
    collected_parameters["analysisInput"]["objectType"] = "STRUCTURED"
    collected_parameters["analysisInput"]["inputs"] = await convert_data_inputs(data_inputs)
    collected_parameters["analysisInput"]["parameters"] = input_parameters
    collected_parameters["analysisInput"]["referenceDataParameters"] = []
    #display(full_url)
    #display(collected_parameters)
    response = await pyfetch(full_url, method = 'POST', headers = headers, body = json.dumps(collected_parameters))
    #####
    curl_command = await curlify(method="POST",endpoint=full_url,header=headers, body = collected_parameters)
    analysis_metadata['step4-api'].append("<h3>#Grab activation code</h3><br>" + curl_command)
    #####
    #response = await pyfetch(full_url, method = 'POST', headers = headers, data = json.dumps(collected_parameters))
    #pprint(response.json())
    entitlement_details = await response.json()
    #display(entitlement_details)
    return entitlement_details['id']
###############################################
async def launch_pipeline_analysis_cwl(jwt_token,project_id,pipeline_id,data_inputs,input_parameters,user_tags,storage_analysis_id,user_pipeline_reference,workflow_language,make_template=False):
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analysis:{workflow_language}"
    full_url = api_base_url + endpoint
    if workflow_language == "cwl":
        activation_details_code_id = await get_activation_code(jwt_token,project_id,pipeline_id,data_inputs,input_parameters,"Cwl")
    elif workflow_language == "nextflow":
        activation_details_code_id = await get_activation_code(jwt_token,project_id,pipeline_id,data_inputs,input_parameters,"Nextflow")
    #print(full_url)
    ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    ######## create body
    collected_parameters = {}
    collected_parameters['userReference'] = user_pipeline_reference
    collected_parameters['activationCodeDetailId'] = activation_details_code_id
    collected_parameters['analysisStorageId'] = storage_analysis_id
    collected_parameters["tags"] = {}
    collected_parameters["tags"]["technicalTags"] = []
    collected_parameters["tags"]["userTags"] = user_tags
    collected_parameters["tags"]["referenceTags"] = []
    collected_parameters["pipelineId"] = pipeline_id
    collected_parameters["projectId"] = project_id
    collected_parameters["analysisInput"] = {}
    collected_parameters["analysisInput"]["objectType"] = "STRUCTURED"
    collected_parameters["analysisInput"]["inputs"] = await convert_data_inputs(data_inputs)
    collected_parameters["analysisInput"]["parameters"] = input_parameters
    collected_parameters["analysisInput"]["referenceDataParameters"] = []
    # Writing to job template to f"{user_pipeline_reference}.job_template.json"
    if make_template is True:
        user_pipeline_reference_alias = user_pipeline_reference.replace(" ","_")
        api_template = {}
        api_template['headers'] = dict(headers)
        api_template['data'] = collected_parameters
        #print(f"Writing your API job template out to {user_pipeline_reference_alias}.api_job_template.txt for future use.\n")
        curl_command = await curlify(method="POST",endpoint=full_url,header=api_template['headers'],body=api_template['data'])
        with open(f"{user_pipeline_reference_alias}.api_job_template.txt", "w") as outfile:
            outfile.write(f"{curl_command}")
        return(f"{user_pipeline_reference_alias}.api_job_template.txt")
    else:
        ##########################################
        response = await pyfetch(full_url, method = 'POST', headers = headers, data = json.dumps(collected_parameters))
        launch_details = await response.json()
        print(launch_details, indent=4)
        return launch_details


############
####
def flatten_list(nested_list):
    def flatten(lst):
        for item in lst:
            if isinstance(item, list):
                flatten(item)
            else:
                flat_list.append(item)

    flat_list = []
    flatten(nested_list)
    return flat_list
    
def get_pipeline_request_template(jwt_token, project_id, pipeline_name, data_inputs, params,tags, storage_size, pipeline_run_name,workflow_language):
    user_pipeline_reference_alias = pipeline_run_name.replace(" ","_")
    pipeline_run_name = user_pipeline_reference_alias
    cli_template_prefix = ["icav2","projectpipelines","start",f"{workflow_language}",f"'{pipeline_name}'","--user-reference",f"{pipeline_run_name}"]
    #### user tags for input
    cli_tags_template = []
    for k,v in enumerate(tags):
        cli_tags_template.append(["--user-tag",v])
    ### data inputs for the CLI command
    cli_inputs_template =[]
    for k in range(0,len(data_inputs)):
        # deal with data inputs with a single value
        if len(data_inputs[k]['data_ids']) < 2 and len(data_inputs[k]['data_ids']) > 0:
            cli_inputs_template.append(["--input",f"{data_inputs[k]['parameter_code']}:{data_inputs[k]['data_ids'][0]}"])
         # deal with data inputs with multiple values
        else:
            v_string = ','.join(data_inputs[k]['data_ids'])
            cli_inputs_template.append(["--input",f"{data_inputs[k]['parameter_code']}:{v_string}"])
    ### parameters for the CLI command        
    cli_parameters_template = []
    for k in range(0,len(params)):
        parameter_of_interest = 'value'
        if 'value' not in params[k].keys():
            parameter_of_interest = 'multiValue'
        # deal with parameters with a single value
        if isinstance(params[k][parameter_of_interest],list) is False:
            if params[k][parameter_of_interest] != "":
                cli_parameters_template.append(["--parameters",f"{params[k]['code']}:'{params[k][parameter_of_interest]}'"])
        else:
        # deal with parameters with multiple values
            if len(params[k][parameter_of_interest])  > 0:
                # remove single-quotes 
                simplified_string = [x.strip('\'') for x in params[k][parameter_of_interest]]
                # stylize multi-value parameters
                v_string = ','.join([f"'{x}'" for x in simplified_string])
                if len(simplified_string) > 1:
                    cli_parameters_template.append(["--parameters",f"{params[k]['code']}:\"{v_string}\""])
                elif len(simplified_string) > 0 and simplified_string[0] != '':
                    cli_parameters_template.append(["--parameters",f"{params[k]['code']}:{v_string}"])
    cli_metadata_template = ["--access-token",f"'{jwt_token}'","--project-id",f"{project_id}","--storage-size",f"{storage_size}"]
    if workflow_language == "cwl":
        cli_metadata_template.append("--type-input STRUCTURED")
    full_cli = [cli_template_prefix,cli_tags_template,cli_inputs_template,cli_parameters_template,cli_metadata_template]
    cli_template = ' '.join(flatten_list(full_cli))
    ######
    pipeline_run_name_alias = pipeline_run_name.replace(" ","_")
    #print(f"Writing your cli job template out to {pipeline_run_name_alias}.cli_job_template.txt for future use.\n")
    with open(f"{pipeline_run_name_alias}.cli_job_template.txt", "w") as outfile:
        outfile.write(f"{cli_template}")
    #print("Also printing out the CLI template to screen\n")
    return  f"{pipeline_run_name_alias}.cli_job_template.txt"
###################################################

def create_analysis_parameter_input_object_extended(parameter_template, params_to_keep):
    parameters = []
    for parameter_item, parameter in enumerate(parameter_template):
        param = {}
        param['code'] = parameter['name']
        if len(params_to_keep) > 0:
            if param['code'] in params_to_keep:
                if parameter['multiValue'] is False:
                    if len(parameter['values']) > 0:
                        param['value'] = parameter['values'][0]
                    else:
                        param['value'] = ""
                else:
                    param['multiValue'] = parameter['values']
            else:
                param['value']  = ""
        else:
            if parameter['multiValue'] is False:
                if len(parameter['values']) > 0:
                    param['value'] = parameter['values'][0]
                else:
                    param['value'] = ""
            else:
                param['multiValue'] = parameter['values']           
        parameters.append(param)
    return parameters

def parse_analysis_data_input_example(input_example, inputs_to_keep):
    input_data = []
    for input_item, input_obj in enumerate(input_example):
        input_metadata = {}
        input_metadata['parameter_code'] = input_obj['code']
        data_ids = []
        if len(inputs_to_keep) > 0:
            if input_obj['code'] in inputs_to_keep:
                for inputs_idx, inputs in enumerate(input_obj['analysisData']):
                    data_ids.append(inputs['dataId'])
        else:
            for inputs_idx, inputs in enumerate(input_obj['analysisData']):
                data_ids.append(inputs['dataId'])
        input_metadata['data_ids'] = data_ids
        input_data.append(input_metadata)
    return input_data

async def get_cwl_input_template(pipeline_code, jwt_token,project_name, fixed_input_data_fields,params_to_keep=[] , analysis_id=None,project_id=None):
    if project_id is None:
        project_id = await get_project_id(jwt_token, project_name)
    headers = dict()
    headers['Accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    # users can define an analysis_id of interest
    if analysis_id is None:
        project_analyses = await list_project_analyses(jwt_token,project_id)
        # find most recent analysis_id for the pipeline_code that succeeeded
        for analysis_idx,analysis in enumerate(project_analyses):
            if analysis['pipeline']['code'] == pipeline_code and analysis['status'] == "SUCCEEDED":
                analysis_id = analysis['id']
                continue
    templates = {}  # a dict that returns the templates we'll use to launch an analysis
    api_base_url = ICA_BASE_URL + "/rest"
    # grab the input files for the given analysis_id
    input_endpoint = f"/api/projects/{project_id}/analyses/{analysis_id}/inputs"
    full_input_endpoint = api_base_url + input_endpoint
    #display(f"ANALYSIS_INPUTS_URL: {full_input_endpoint}")
    try:
        inputs_response = await pyfetch(full_input_endpoint, method='GET', headers=headers)
        #####
        curl_command = await curlify(method="GET",endpoint=full_input_endpoint,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab dataInputs JSON from previous analysis</h3><br>" + curl_command)
        #####
        inputs_responses = await inputs_response.json()
        #display(inputs_responses)
        input_data_example = inputs_responses['items']
    except:
        raise ValueError(f"Could not get inputs for the project analysis {analysis_id}")
    # grab the parameters set for the given analysis_id
    parameters_endpoint = f"/api/projects/{project_id}/analyses/{analysis_id}/configurations"
    full_parameters_endpoint = api_base_url + parameters_endpoint
    #display(f"ANALYSIS_PARAMETERS_URL: {full_parameters_endpoint}")
    try:
        parameter_response = await pyfetch(full_parameters_endpoint, method = 'GET', headers=headers)
        #####
        curl_command = await curlify(method="GET",endpoint=full_parameters_endpoint,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab parameters JSON from previous analysis</h3><br>" + curl_command)
        #####
        parameter_responses = await parameter_response.json()
        parameter_settings = parameter_responses['items']
    except:
        raise ValueError(f"Could not get parameters for the project analysis {analysis_id}")
    # return both the input data template and parameter settings for this pipeline
    input_data_template = parse_analysis_data_input_example(input_data_example, fixed_input_data_fields)
    parameter_settings_template = create_analysis_parameter_input_object_extended(parameter_settings,params_to_keep)
    templates['input_data'] = input_data_template
    templates['parameter_settings'] = parameter_settings_template
    return templates
#####################
async def get_analysis_steps(jwt_token,project_id,analysis_id):
     # List all analyses in a project
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analyses/{analysis_id}/steps"
    analysis_step_metadata = []
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    #headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] = 'Bearer ' + jwt_token
    try:
        projectAnalysisSteps = await pyfetch(full_url, method = 'GET', headers = headers)
        test_response = await projectAnalysisSteps.json()
        if 'items' in test_response.keys():
            for step in test_response['items']:
                analysis_step_metadata.append(step)
        else:
            print(test_response)
            raise ValueError(f"Could not get analyses steps {analysis_id} for project: {project_id}")
    except:
        raise ValueError(f"Could not get analyses steps {analysis_id}  for project: {project_id}")
    return analysis_step_metadata

def generate_step_file(step_object,output_path):
    f = open(output_path, "w")
    for s1 in json.dumps(step_object,indent=4,sort_keys=True): 
        f.write(s1)
    f.close()
    return print(f"Created {output_path}")

########################

def create_analysis_metadata_table(step_data):
    analysis_metadata_table = []
    for step in step_data:
        #print(step)
        #print(step.keys())
        #if re.match(":",step['name']) is not None:
        #    step['name'] = re.sub(":","_",step['name'])
        #if len(re.findall("\(",step['name'])) > 0: 
        #    step['name'] = re.sub("\(","_",step['name'])
        #if len(re.findall("\)",step['name'])) > 0 : 
        #    step['name'] = re.sub("\)","_",step['name'])
        if 'endDate' not in step.keys():
            step['endDate'] = "2024-01-03T00:00:00Z"
        if 'startDate' not in step.keys():
            step['startDate'] = "2024-01-03T00:00:00Z"
        if 'exitCode' in step.keys():
            new_line = f"{step['name']}\t{step['id']}\t{step['startDate']}\t{step['endDate']}\t{step['exitCode']}\t{step['technical']}"
            #print(new_line)
        else:
            if step['status'] == "DONE":
                new_line = f"{step['name']}\t{step['id']}\t{step['startDate']}\t{step['endDate']}\t0\t{step['technical']}"
                #print(new_line)
            else:
                new_line = f"{step['name']}\t{step['id']}\t{step['startDate']}\t{step['endDate']}\t?\t{step['technical']}"
                #print(new_line)
        analysis_metadata_table.append(new_line.split("\t"))
    return(analysis_metadata_table)


def add_to_section(section_dict,section_name,new_line):
        if section_name in section_dict.keys():
            section_dict[section_name].append(new_line)
        else:
            section_dict[section_name] = []
            section_dict[section_name].append(new_line)
        return(section_dict)

def create_gantt_section_stubs(analysis_metadata_table):
    ## store our lists in an ordered dictionary so we can create sections for mermaidJS
    analysis_sections = OrderedDict()
    ### sort our list of lists based on startDate
    analysis_metadata_table = sorted(analysis_metadata_table, key=itemgetter(2))
    for step in analysis_metadata_table:
        if step[len(step)-1] == "True":
            #print(step)
            if re.search("finalize_output",step[0]) is not None  or re.search("Urn",step[0]) is not None or re.search("Storage",step[0]) is not None or re.search("Finalize Output",step[0]) is not None:
                section_name = "Finalize_Output_Data"
                add_to_section(analysis_sections,section_name,step)
            elif re.search("prepare_input",step[0]) is not None or re.search("Prepare Input",step[0]) is not None or re.search("Workflow_pre",step[0]) is not None:
                section_name = "Prepare_Input_Data"
                add_to_section(analysis_sections,section_name,step) 
            elif re.search("pipeline",step[0]) is not None or re.search("Pipeline",step[0]) is not None:
                section_name = "Pipeline Runner"
                add_to_section(analysis_sections,section_name,step) 
            elif re.search("Workflow_monitor",step[0]) is not None:
                section_name = "Run_Monitor"
                add_to_section(analysis_sections,section_name,step) 
            else:
                display(f"[WARNING] : Not sure what to do with {step}")
        else:
            section_name = "Pipeline Runner"
            add_to_section(analysis_sections,section_name,step)
    return(analysis_sections)

#print(analysis_sections.keys())
#### example gantt section
#      section Clickable
#      Visit mermaidjs         :active, cl1, 2014-01-07 10:21:15, 3d
#      Print arguments         :cl2, after cl1, 3d
#      Print task              :cl3, after cl2, 3d
###################
def create_gantt_sections(section_dict):
    sections_stub = f""
    step_num = 0
    for section in section_dict.keys():
        sections_stub += f"\n"
        sections_stub += f"\tsection {section}\n"
        for sub_steps in section_dict[section]:
            step_name = sub_steps[0]
            step_name = re.sub("\s+","_",step_name)
            step_num = step_num + 1
            start_date = sub_steps[2].strip("Z").split("T")
            start_date = " ".join(start_date)
            if start_date == "":
                start_date = f"after step{step_num}"
            end_date = sub_steps[3].strip("Z").split("T")
            end_date = " ".join(end_date)
            if end_date == "":
                end_date = "1d"
            if sub_steps[len(sub_steps)-2] == "?":
                string_to_add = f"\t\t{step_name}\t:active, step{step_num}, {start_date}, {end_date}\n"
            elif sub_steps[len(sub_steps)-2] == "0":       
                string_to_add =f"\t\t{step_name}\t:step{step_num}, {start_date}, {end_date}\n"   
            else:
                string_to_add = f"\t\t{step_name}\t:crit, step{step_num}, {start_date}, {end_date}\n"      
            sections_stub += f"{string_to_add}"
    return(sections_stub)



#print(to_mermaid)
def mermaid_boilerplate_prefix(analysis_id):
    return(f"gantt\n\ttitle Analysis Timeline for {analysis_id}\n\tdateFormat\tYYYY-MM-DD HH:mm:ss")

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

#############
async def get_analysis_info(jwt_token,project_id,analysis_id):
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analyses/{analysis_id}"
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    #headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] = 'Bearer ' + jwt_token
    try:
        analysis_info = await pyfetch(full_url, method = 'GET', headers = headers)
        analysis_info_response = await analysis_info.json()
    except:
        raise ValueError(f"Could not get analysis_info for analysis {analysis_id} in project: {project_id}")
    return analysis_info_response

async def get_analysis_metadata(jwt_token,project_id,analysis_id):
         # List all analyses in a project
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analyses/{analysis_id}"
    analysis_metadata = []
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    #headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] = 'Bearer ' + jwt_token
    try:
        projectAnalysis = await pyfetch(full_url, method = 'GET', headers = headers)
        analysis_metadata = await projectAnalysis.json()
        ##print(pprint(analysis_metadata,indent=4))
    except:
        raise ValueError(f"Could not get analyses metadata for project: {project_id}")
    return analysis_metadata

def get_relative_path(file_path,term_of_interest):
    file_path_split = file_path.split('/')
    idx_of_interest = 0
    for idx,i in enumerate(file_path_split):
        if i == term_of_interest:
            idx_of_interest  = idx + 1
    end_idx = len(file_path_split) -1
    list_subset = file_path_split[idx_of_interest::]
    #print(list_subset)
    relative_path_str = "/".join(list_subset)
    return  relative_path_str


async def find_ica_logs(jwt_token,project_id,analysis_metadata,search_query = "ica_logs"):
    ica_logs = None
    ### assume user has not output the results of analysis to custom directory
    search_query_path = "/" + analysis_metadata['reference'] + "/" 
    search_query_path_str = [re.sub("/", "%2F", x) for x in search_query_path]
    search_query_path = "".join(search_query_path_str)
    search_query_path_str = [re.sub("\s+", "%20", x) for x in search_query_path]
    search_query_path = "".join(search_query_path_str) + search_query  + "%2F"
    datum = []
    pageOffset = 0
    pageSize = 1000
    page_number = 0
    number_of_rows_to_skip = 0
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/data?filePath={search_query_path}&filePathMatchMode=STARTS_WITH_CASE_INSENSITIVE&pageOffset={pageOffset}&pageSize={pageSize}"
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    #headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] = 'Bearer ' + jwt_token
    try:
        #print(full_url)
        #display(full_url)
        projectDataPagedList = await pyfetch(full_url, method = 'GET', headers = headers)
        projectDataPagedList_response = await projectDataPagedList.json()
        #display(projectDataPagedList_response)
        #display(projectDataPagedList.status_code)
        #if projectDataPagedList.status_code == 200:
        if 'totalItemCount' in projectDataPagedList_response.keys():
            totalRecords = projectDataPagedList_response['totalItemCount']
            while page_number * pageSize < totalRecords:
                endpoint = f"/api/projects/{project_id}/data?filePath={search_query_path}&filePathMatchMode=STARTS_WITH_CASE_INSENSITIVE&pageOffset={number_of_rows_to_skip}&pageSize={pageSize}"
                full_url = api_base_url + endpoint  ############ create header
                projectDataPagedList = await pyfetch(full_url, method = 'GET', headers = headers)
                projectDataPagedList_response = await projectDataPagedList.json()
                for projectData in projectDataPagedList_response['items']:
                    # if re.search(analysis_metadata['reference'],projectData['data']['details']['path']) is not None:
                    if os.path.basename(projectData['data']['details']['path']) != "" and projectData['data']['details']['dataType'] != "FOLDER":
                        relative_path = get_relative_path(projectData['data']['details']['path'],search_query)
                        #display(relative_path)
                        datum.append({"name": projectData['data']['details']['name'], "id": projectData['data']['id'],
                                    "path": relative_path})
                    page_number += 1
                    number_of_rows_to_skip = page_number * pageSize
            else:
                for projectData in projectDataPagedList_response['items']:
                    if os.path.basename(projectData['data']['details']['path']) != "" and projectData['data']['details']['dataType'] != "FOLDER":
                        relative_path = get_relative_path(projectData['data']['details']['path'],search_query)
                        #display(relative_path)
                        datum.append({"name": projectData['data']['details']['name'], "id": projectData['data']['id'],
                                "path": relative_path}) 
        else:
            print(f"Could not get results for project: {project_id} looking for filename: {search_query}")
    except:
        print(f"Could not get results for project: {project_id} looking for filename: {search_query}")
    return datum
#####################################################
#################
def file_or_stream(analysis_step_metadata):
    log_status = None
    for step in analysis_step_metadata:
        if 'stdOutData' in step['logs'].keys() or 'stdErrData' in step['logs'].keys()  :
            log_status = 'file'
        elif 'stdOutStream' in step['logs'].keys() or 'stdErrStream' in step['logs'].keys()  :
            log_status = 'stream'
    return log_status
###################
def download_data_from_url(download_url,output_name=None):
    command_base = ["wget"]
    if output_name is not None:
        output_name = '"' + output_name + '"' 
        command_base.append("-O")
        command_base.append(f"{output_name}")
    command_base.append(f"{download_url}")
    command_str = " ".join(command_base)
    #display(f"Running: {command_str}",target="troubleshoot-download",append=True)
    os.system(command_str)
    return print(f"Downloading from {download_url}")
######################################################
def download(download_url, output_name = None):
    response =   open_url(download_url)
    response_data =  response.read()
    # print(response_data)
    #if response.status == 200:
    with open(output_name, 'w') as f:  # 'wb' for write binary mode
        for l in response_data:
            f.write(l)
        #print(response_data)
    return print(f"Downloading from {download_url}")

async def download_binary(download_url, output_name = None):
    response = await pyfetch(download_url)
    response_data =  await response.bytes()
    with open(output_name, 'wb') as f:  # 'wb' for write binary mode
        f.write(response_data)
    return print(f"Downloading from {download_url}")

async def download_file(jwt_token,project_id,data_id,output_path):
    # List all analyses in a project
    api_base_url = ICA_BASE_URL+ "/rest"
    endpoint = f"/api/projects/{project_id}/data/{data_id}:createDownloadUrl"
    download_url = None
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    #headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] = 'Bearer ' + jwt_token
    try:
        downloadFile = await pyfetch(full_url, method = 'POST', headers = headers)
        downloadFile_response = await downloadFile.json()
        download_url = downloadFile_response['url']
        download_url = '"' + download_url + '"'
        #download_data_from_url(download_url,output_path)
    except:
        raise ValueError(f"Could not get analyses streams for project: {project_id}")

    return download_url
##################
 
async def stream_log(uri,extra_headers,output_file=None):
    if output_file is None:
        sys.stderr.write("Please define an output file to stream to")
        sys.exit()
    output_lines = []
    async with websockets.connect(uri,extra_headers=extra_headers) as ws:
        try:
            text = await ws.recv()
            print(f"< {text.rstrip()}")
            output_lines.append(f"{text.rstrip()}")
        except (exceptions.ConnectionClosedError,exceptions.ConnectionClosed):
            print(f"Connection closed")
            return 0
    ###############################
    f = open(output_file, "w")
    for s1 in output_lines: 
        f.write(s1)
    f.close()
    return print(f"Completed streaming from {uri}")

async def get_logs(jwt_token,project_id,analysis_id,extra_headers,output_dir):
    log_urls = dict()
    analysis_step_metadata = await get_analysis_steps(jwt_token,project_id,analysis_id)
    while len(analysis_step_metadata) < 1:
        analysis_step_metadata = await get_analysis_steps(jwt_token,project_id,analysis_id)
    generate_step_file(analysis_step_metadata,f"analysis_id_{analysis_id}/step_metadata.json")
    for step in analysis_step_metadata:
        log_status = file_or_stream([step])
        step_name = step['id']
        if log_status == "file":
            if 'stdOutData' in step['logs'].keys():
                stdout_path = step['logs']['stdOutData']['details']['path']
                stdout_id = step['logs']['stdOutData']['id']
                print(f"For {step_name} Downloading the log for {stdout_path}")
                #display(f"For {step_name} Downloading the log for {stdout_path}",target="troubleshoot-download",append=True)
                download_url = await download_file(jwt_token,project_id,stdout_id,f"{output_dir}/" +step_name +".stdout.log")
                #download_data_from_url(download_url,f"{output_dir}/" +step_name +".stdout.log")
                log_urls[f"{output_dir}/" +step_name +".stdout.log"] = download_url 
            else:
                sys.stderr.write(f"Cannot find stdOutData for {step_name}")
                print(step['logs'])
            if 'stdErrData' in step['logs'].keys():
                stderr_path = step['logs']['stdErrData']['details']['path']
                stderr_id = step['logs']['stdErrData']['id']
                print(f"For {step_name} Downloading the log for {stderr_path}")
                #display(f"For {step_name} Downloading the log for {stderr_path}",target="troubleshoot-download",append=True)
                download_url = await download_file(jwt_token,project_id,stderr_id,f"{output_dir}/" +step_name +".stderr.log")
                #download_data_from_url(download_url,f"{output_dir}/" +step_name +".stderr.log")
                log_urls[f"{output_dir}/" +step_name +".stderrlog"] = download_url 
            else:
                sys.stderr.write(f"Cannot find stdErrData for {step_name}")
                print(step['logs'])
        elif log_status == "stream":
        ### assume stream
            stdout_websocket = step['logs']['stdOutStream']
            output_file = f"{output_dir}/" +step_name +".stdout.log"
            print(f"For step: {step_name}, streaming {stdout_websocket}")
            asyncio.get_event_loop().run_until_complete(stream_log(stdout_websocket,extra_headers,output_file))
            stderr_websocket = step['logs']['stdErrStream']
            output_file = f"{output_dir}/" +step_name +".stderr.log"
            print(f"For step: {step_name}, streaming {stderr_websocket}")
            asyncio.get_event_loop().run_until_complete(stream_log(stderr_websocket,extra_headers,output_file))
        else:
            print(f"Nothing to do for step {step_name}, analysis {analysis_id} is not running that step")
    print(f"Finished getting logs for {analysis_id}")
    return log_urls

##########################################
#### STEP 1 in HTML
async def load_login_info(event):
    display("STEP1: Authorizing login credentials",target="step1-output",append="False")
    USERNAME = document.getElementById('txt-uname').value
    #display('MY_USERNAME: ' + USERNAME)
    PASSWORD = document.getElementById('txt-pwd').value
    #display('MY_PASSWORD: ' + PASSWORD)
    PROJECT_NAME = None
    #display('MY_PROJECT_NAME: ' + PROJECT_NAME)
    DOMAIN_NAME = document.getElementById('txt-domain-name').value
    if DOMAIN_NAME == '':
        DOMAIN_NAME = None
    #display('MY_DOMAIN_NAME: ' + DOMAIN_NAME)
    ### get JWT token
    jwt_token = None
    try:
        jwt_token = await get_jwt(USERNAME,PASSWORD,tenant = DOMAIN_NAME)
    except:
        console.error('Please retry login.\nYou May need to refresh your webpage')
        alert('Please retry login.\nPlease double-check username and password\nYou May need to refresh your webpage')
        raise ValueError(f"Could not get JWT for user: {USERNAME}\nPlease double-check username and password.\nYou also may need to enter a domain name\n")
    authorization_metadata['jwt_token'] = jwt_token 
    analysis_metadata['domain_name'] = DOMAIN_NAME
    #### Step 2 get project ID
    PROJECT_ID = None
    #### select project if needed
    if PROJECT_NAME is None:
        project_table = await list_projects(jwt_token)
        df = pd.DataFrame(project_table, columns = ['ICA Project Name', 'ICA Project ID']) 

        pydom["div#project-output"].style["display"] = "block"

        ### show field and submit button for STEP2:
        pydom["div#step2-selection-form"].style["display"] = "block"

        #pydom["div#roject-output-inner"].innerHTML = df_window(df)
        #document.getElementById('project-output-inner').innerHTML = df.to_html()
        document.getElementById('project-output-inner').innerHTML = df_html(df)

        new_script = document.createElement('script')
        new_script.innerHTML  = """$(document).ready(function(){$('#project-output-inner').DataTable({
            "pageLength": 10
        });});"""
        document.getElementById('project-output').appendChild(new_script)

        #display(df.to_html(), target="project-output-inner", append="False")
        #display(df_window(df), target="project-output-inner", append="False")
    return display("You are logged in",target="step1-output",append="True")
#######
#### STEP 2 in HTML
async def load_project_selection_info(event):
    display("STEP2 starting",target ="step2-selection",append="False")
    # Create a Python proxy for the callback function
    PROJECT_NAME =  document.getElementById("txt-project-name").value 
    console.log(f"{PROJECT_NAME}")
    pydom["div#step2-selection"].html = PROJECT_NAME
    display(f'Selected project name is: {PROJECT_NAME}',target ="step2-selection",append="True")
    try:
        PROJECT_ID = await get_project_id(authorization_metadata['jwt_token'], PROJECT_NAME)
        display(f'project id is : {PROJECT_ID}',target ="step2-selection",append="True")
        analysis_metadata['project_name'] = PROJECT_NAME
        analysis_metadata['project_id'] = PROJECT_ID
    except:
        console.error('Please retry entering a project name')
        alert('Please retry entering a project name.')
        raise ValueError(f"Could not get project id for project: {PROJECT_NAME}\nPlease double-check project name exists.")    
    display(f"Fetching all analyses from {PROJECT_NAME}",target ="step2-selection",append="True")    
    analyses_list = await list_project_analyses(authorization_metadata['jwt_token'],analysis_metadata['project_id'])
    display(f"Fetching Completed\nCreating Table\n",target ="step2-selection",append="True")    
    analyses_table = subset_analysis_metadata_list(analyses_list)
    df = pd.DataFrame(analyses_table, columns = ['Analysis Name', 'Analysis ID','Analysis Start Date','Analysis Status','Pipeline']) 
    df['Analysis Start Date'] = pd.to_datetime(df['Analysis Start Date'], format='%Y-%m-%dT%H:%M:%SZ')

    #df.sort_values(by='Analysis Start Date',ascending=False,inplace = True)
    ### using slicing to invert dataframe to give ICA default sorting
    #df = df[::-1]
    pydom["div#analyses-output"].style["display"] = "block"
    #display(df, target="project-output-inner", append="False")
    document.getElementById('analyses-output-inner').innerHTML = df_html(df)

    new_script = document.createElement('script')
    new_script.innerHTML  = """$(document).ready(function(){$('#analyses-output-inner').DataTable({
            "pageLength": 10
        });});"""
    document.getElementById('analyses-output').appendChild(new_script)
    ### show field and submit button for STEP3:
    pydom["div#step3-selection-form"].style["display"] = "block"

    return display("STEP2 complete",target ="step2-selection",append="True")
##################    
#### STEP 3 in HTML
async def load_analysis_selection_info(event):
    display("STEP3 starting",target ="step3-selection",append="False")
    ANALYSIS_NAME = document.getElementById("txt-analysis-name").value 
    analysis_metadata['analysis_name'] = ANALYSIS_NAME
    pydom["div#step3-selection"].html = ANALYSIS_NAME
    display(f'Selected analysis name is: {ANALYSIS_NAME}',target ="step3-selection",append="True")
    try:
        if ANALYSIS_NAME in analysis_metadata['metadata_by_analysis_id'].keys():
            analysis_metadata['analysis_id'] = ANALYSIS_NAME
            pydom["div#step4-selection-form"].style["display"] = "block"
        elif ANALYSIS_NAME in analysis_metadata['metadata_by_analysis_name'].keys():
            #ANALYSIS_ID = await get_project_analysis_id(authorization_metadata['jwt_token'],analysis_metadata['project_id'],analysis_metadata['analysis_name'])
            ANALYSIS_ID_LOOKUP = analysis_metadata['metadata_by_analysis_name'][ANALYSIS_NAME]
            ANALYSIS_ID = ANALYSIS_ID_LOOKUP['id']
            display(f'analysis id is : {ANALYSIS_ID}',target ="step3-selection",append="True")
            analysis_metadata['analysis_id'] = ANALYSIS_ID
            pydom["div#step4-selection-form"].style["display"] = "block"
        else:
            console.error('Please retry entering an analysis name')
            alert('Please retry entering an analysis name.')
            raise ValueError(f"Could not get analysis id for analysis: {ANALYSIS_NAME}\nPlease double-check analysis name exists.") 
    except:
        if ANALYSIS_NAME in analysis_metadata['metadata_by_analysis_id'].keys():
            analysis_metadata['analysis_id'] = ANALYSIS_NAME
            pydom["div#step4-selection-form"].style["display"] = "block"
        else:
            console.error('Please retry entering an analysis name')
            alert('Please retry entering an analysis name.')
            raise ValueError(f"Could not get analysis id for analysis: {ANALYSIS_NAME}\nPlease double-check analysis name exists.") 
    return display("STEP3 complete",target ="step3-selection",append="True")
#####################
def make_dir(my_dir):
    if os.path.isdir(f"{my_dir}") is False:
        os.mkdir(f"{my_dir}")   
    return 0
### STEP 4 get step log from ICA and generate gantt chart in mermaid
async def generate_gantt(event):
    ##### log in and get STEP file
    step_object = await get_analysis_steps(authorization_metadata['jwt_token'],analysis_metadata['project_id'],analysis_metadata['analysis_id'])
    step_file = 'step_metadata.json'
    generate_step_file(step_object,step_file)
    ################
    ANALYSIS_ID = analysis_metadata['analysis_id']
    display(f'Writing out analysis step metadata for {ANALYSIS_ID} to {step_file}',target ="step3-selection",append="True")
    with open(step_file) as f:
        step_data= json.load(f)
    #display(step_data)
    ######################### convert step_file into
    analysis_metadata_table =  create_analysis_metadata_table(step_data)
    #display(analysis_metadata_table)
    analysis_sections = create_gantt_section_stubs(analysis_metadata_table)
    #display(analysis_sections)
    to_mermaid =  create_gantt_sections(analysis_sections)
    #display(to_mermaid)
    ###############################################
    mermaid_content =  mermaid_boilerplate_prefix(analysis_metadata['analysis_id']) + to_mermaid

    #display(f"{mermaid_content}")
    ########
    mermaid_file = "mermaid_gantt.txt"
    with open(mermaid_file,"w") as f:
        f.write(mermaid_content)
    ################
    #mermaid_content_v2 = mermaid_content.split("\n")
    #for l in mermaid_content_v2:
    #    document.getElementById('gantt-chart').innerHTML += l
    mermaid_content_v2 = mermaid_content.split("\n")
    mermaid_code = ""
    for l in mermaid_content_v2:
        l1 = re.sub("\t","    ",l)
        mermaid_code += l1 + '\n'
    document.getElementById('gantt-chart').innerHTML = f"{mermaid_code}"
    # elements can be appended to any other element on the page
    new_script = document.createElement('script')
    new_script.setAttribute('type', 'module');
    new_script.innerHTML  = """import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    const config = {
        fontSize: 12, // Font size
        sectionFontSize: 28, // Font size for sections
        numberSectionStyles: 5, // The number of alternating section styles
        startOnLoad: false,
        securityLevel: 'loose',
        };
    mermaid.initialize(config);
    await mermaid.run({
        nodes: [document.getElementById('gantt-chart')],
    });"""
    #### https://developer.mozilla.org/en-US/docs/Web/API/Node/insertBefore
    gantt_element = document.getElementById('gantt-chart')
    parent_node = gantt_element.parentNode;
    parent_node.insertBefore(new_script, gantt_element.nextSibling);
    #document.body.appendChild(new_script)
    #######
    pydom["pre#gantt-chart"].style["display"] = "block"
    #####
    ############
    extra_headers = {}
    extra_headers['Origin'] = ICA_BASE_URL
    extra_headers['User-Agent'] = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Mobile Safari/537.36"
    ####
    #my_dir = f"{os.getcwd()}/analysis_id_{analysis_metadata['analysis_id']}"
    my_dir = f"analysis_id_{analysis_metadata['analysis_id']}"
    make_dir(my_dir)
    my_analysis_log_dir = f"analysis_id_{analysis_metadata['analysis_id']}/analysis_logs"
    make_dir(my_analysis_log_dir)
    ##########################    
    analysis_metadata['download_urls'] = dict()
    ## download files
    ### write out mermaid file for downstream visualization
    mermaid_file = f"{my_dir}/mermaid_gantt.txt"
    with open(mermaid_file,"w") as f:
        f.write(mermaid_content)
    ## download analysis log files from pipeline
    pydom["div#troubleshoot-download"].style["display"] = "block"
    analysis_info = await get_analysis_info(authorization_metadata['jwt_token'],analysis_metadata['project_id'],analysis_metadata['analysis_id'])
    if 'startDate'  in list(analysis_info.keys()):
        ica_analysis_log_download = await get_logs(authorization_metadata['jwt_token'],analysis_metadata['project_id'],analysis_metadata['analysis_id'],extra_headers,my_analysis_log_dir)
        if len(list(ica_analysis_log_download.keys())) > 0:
            display("Downloading analysis logs from ICA",target="troubleshoot-download",append=True)
        for log_to_download in list(ica_analysis_log_download.keys()):
            download(ica_analysis_log_download[log_to_download],log_to_download)
            analysis_metadata['download_urls'][ica_analysis_log_download[log_to_download]] = log_to_download
    else:
        display(f"It appears that {analysis_metadata['analysis_id']} failed before it was run",target="troubleshoot-download",append=True)
    ### obtain analysis run metadata so we can check the results
    analysis_run_metadata = await get_analysis_metadata(authorization_metadata['jwt_token'],analysis_metadata['project_id'],analysis_metadata['analysis_id'])

    ## download ICA platform logs
    ica_logs_ids = await find_ica_logs(jwt_token = authorization_metadata['jwt_token'],project_id = analysis_metadata['project_id'],analysis_metadata=analysis_run_metadata)
    make_dir(f"{my_dir}/ica_logs")
    if len(ica_logs_ids) > 0:
        display("Downloading ICA platform analysis logs",target="troubleshoot-download",append=True)
        for idx,ica_log in enumerate(ica_logs_ids):
            ######
            path_split = ica_log['path'].split('/')
            for i in range(0,len(path_split)-1):
                if i != 0:
                    test_dir = f"{my_dir}/ica_logs" + "/" + "/".join(path_split[0:(i+1)])
                else:
                    test_dir = f"{my_dir}/ica_logs" + "/" + path_split[0]
                make_dir(f"{test_dir}")
            ########
            output_path = f"{my_dir}/ica_logs/{ica_log['path']}"
            #display(f"Downloading the log for {ica_log['path']}",target="troubleshoot-download",append=True)
            ica_log_download_url = await download_file(jwt_token = authorization_metadata['jwt_token'],project_id = analysis_metadata['project_id'],data_id = ica_log['id'],output_path =f"{output_path}")
            if  re.search(".db$",os.path.basename(output_path)) is None:
                download(ica_log_download_url,output_path)
            else:
                await download_binary(ica_log_download_url,output_path)
            analysis_metadata['download_urls'][ica_log_download_url] = output_path
    else:
        display(f"Could not ICA platform analysis logs for analysis: {analysis_metadata['analysis_id']} in the project: {analysis_metadata['project_id']}",target="troubleshoot-download",append=True)
    display("Log download completed",target="troubleshoot-download",append=True)
    #### Displaying the analysis step metadata in a table
    analysis_metadata_table = sorted(analysis_metadata_table, key=itemgetter(2))
    df = pd.DataFrame(analysis_metadata_table, columns = ['Step Name', 'Step ID','Step Start Date','Step End Date','Exit Code','ICA Platform Step']) 
    df['Step Start Date'] = pd.to_datetime(df['Step Start Date'], format='%Y-%m-%dT%H:%M:%SZ')
    df['Step End Date'] = pd.to_datetime(df['Step End Date'], format='%Y-%m-%dT%H:%M:%SZ')
    df = df.drop(['Step ID'], axis=1)
    #df.sort_values(by='Analysis Start Date',ascending=False,inplace = True)
    ### using slicing to invert dataframe to give ICA default sorting
    #df = df[::-1]
    pydom["div#analyses-metadata-output"].style["display"] = "block"
    #display(df, target="project-output-inner", append="False")
    document.getElementById('analyses-metadata-output-inner').innerHTML = df_html(df)

    new_script = document.createElement('script')
    new_script.innerHTML  = """$(document).ready(function(){$('#analyses-metadata-output-inner').DataTable({
            "pageLength": 100
        });});"""
    document.getElementById('analyses-metadata-output').appendChild(new_script)
    #####################
    #new_script = document.createElement('py-config') 
    #json_config = "myfiles.json"
    #temp_dict = dict()
    #temp_dict['files'] = analysis_metadata['download_urls']
    #new_script.innerHTML  = f"{json.dumps(temp_dict,indent =4)}"
    #generate_step_file(temp_dict,json_config)  
    #new_script.setAttribute('src', json_config);
    #### https://developer.mozilla.org/en-US/docs/Web/API/Node/insertBefore
    #download_ready_element = document.getElementById('download-ready')
    #parent_node = download_ready_element.parentNode;
    #parent_node.insertBefore(new_script, download_ready_element.nextSibling);
    pydom["div#step6-selection-form"].style["display"] = "block"
    ########
    analysis_metadata_short = dict()
    analysis_metadata_short['domain_name'] = analysis_metadata['domain_name']
    analysis_metadata_short['project_name'] = analysis_metadata['project_name']
    analysis_metadata_short['project_id'] = analysis_metadata['project_id']
    analysis_metadata_short['analysis_name'] = analysis_metadata['analysis_name']
    analysis_metadata_short['analysis_id'] = analysis_metadata['analysis_id']
    ##########################
    analysis_metadata_json= f"analysis_metadata.json"
    generate_step_file(analysis_metadata_short,analysis_metadata_json)

    analysis_metadata_json= f"analysis_info.json"
    generate_step_file(analysis_info,analysis_metadata_json)    

    analysis_metadata_json= f"{my_dir}/analysis_metadata.json"
    generate_step_file(analysis_metadata_short,analysis_metadata_json)

    analysis_metadata_json= f"{my_dir}/analysis_info.json"
    generate_step_file(analysis_info,analysis_metadata_json)   
    return display("STEP4 complete",target ="step4-selection",append="True")

