import argparse
from flask import Flask, request, render_template
import os
from flask_ades_wpst.ades_base import ADES_Base


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-H", "--host", default="127.0.0.1", help="host IP address for Flask server"
    )
    args = parser.parse_args()
    return args.host


app = Flask(__name__)


@app.route("/api/docs")
def get_docs():
    print("sending docs")
    return render_template("swaggerui.html")


@app.route("/")
def root():
    print("sending root")
    # resp_dict = {"landingPage": {"links": [
    #     {"href": "/", "type": "GET", "title": "getLandingPage"},
    #     {"href": "/processes", "type": "GET", "title": "getProcesses"},
    #     {"href": "/processes", "type": "POST", "title": "deployProcess"},
    #     {"href": "/processes/<procID>", "type": "GET",
    #      "title": "getProcessDescription"},
    #     {"href": "/processes/<procID>", "type": "DELETE",
    #      "title": "undeployProcess"},
    #     {"href": "/processes/<procID>/jobs", "type": "GET",
    #      "title": "getJobList"},
    #     {"href": "/processes/<procID>/jobs", "type": "POST",
    #      "title": "execute"},
    #     {"href": "/processes/<procID>/jobs/<jobID>", "type": "GET",
    #      "title": "getStatus"},
    #     {"href": "/processes/<procID>/jobs/<jobID>", "type": "DELETE",
    #      "title": "dismiss"},
    #     {"href": "/processes/<procID>/jobs/<jobID>/result", "type": "GET",
    #      "title": "getResult"}]}}
    return render_template("index.html")


@app.route("/processes", methods=["GET", "POST"])
def processes():
    resp_dict = {}
    try:
        status_code = 200
        ades_base = ADES_Base(app.config)
        if request.method == "GET":
            # Retrieve available processes
            # Get list of all available algorithms
            proc_list = ades_base.get_procs()
            resp_dict = {"processes": proc_list}
        elif request.method == "POST":
            # Deploy a process
            # Register a new algorithm
            req_vals = request.get_json()
            proc_id = req_vals["processDescription"]["process"]["id"]
            if ades_base.get_proc(proc_id):
                raise ValueError(f"Process ({proc_id}) is already deployed.")
            proc_info = ades_base.deploy_proc(req_vals)
            resp_dict = {"deploymentResult": {"processSummary": proc_info}}
            status_code = 201
    except:
        status_code = 500
    return resp_dict, status_code, {"ContentType": "application/json"}


@app.route("/processes/<procID>", methods=["GET", "DELETE"])
def processes_id(procID):
    resp_dict = {}
    try:
        status_code = 200
        ades_base = ADES_Base(app.config)
        if request.method == "GET":
            # Retrieve a process description
            # Get a full description of the algorithm
            proc_dict = ades_base.get_proc(procID)
            resp_dict = {"process": proc_dict}
        elif request.method == "DELETE":
            # Undeploy a process
            # Delete the algorithm
            resp_dict = {"undeploymentResult": ades_base.undeploy_proc(procID)}
    except:
        status_code = 500
    return resp_dict, status_code, {"ContentType": "application/json"}


@app.route("/processes/<procID>/jobs", methods=["GET", "POST"])
def processes_jobs(procID):
    ades_base = ADES_Base(app.config)
    if request.method == "GET":
        # Retrieve the list of jobs for a process
        # Get list of jobs for a specific algorithm type
        status_code = 200
        job_list = ades_base.get_jobs(procID)
        resp_dict = {"jobs": job_list}
        return resp_dict, status_code, {"ContentType": "application/json"}
    elif request.method == "POST":
        # Execute a process
        # Submit a job
        status_code = 201
        job_params = request.get_json()
        job_info = ades_base.exec_job(procID, job_params)
        header_dict = job_info
        header_dict["ContentType"] = "application/json"
        return {}, status_code, header_dict


@app.route("/processes/<procID>/jobs/<jobID>", methods=["GET", "DELETE"])
def processes_job(procID, jobID):
    status_code = 200
    ades_base = ADES_Base(app.config)
    if request.method == "GET":
        # Retrieve the status of a job
        resp_dict = ades_base.get_job(procID, jobID)
    elif request.method == "DELETE":
        # Dismiss a job
        # Stop / Revoke a Job
        dismiss_status = ades_base.dismiss_job(procID, jobID)
        resp_dict = {"statusInfo": dismiss_status}
    return resp_dict, status_code, {"ContentType": "application/json"}


@app.route("/processes/<procID>/jobs/<jobID>/result", methods=["GET"])
def processes_result(procID, jobID):
    # Get the result of the job
    status_code = 200
    ades_base = ADES_Base(app.config)
    resp_dict = ades_base.get_job_results(procID, jobID)
    return resp_dict, status_code, {"ContentType": "application/json"}


def flask_wpst(
    app,
    debug=False,
    host="127.0.0.1",
    valid_platforms=("Generic", "K8s", "PBS", "HYSDS"),
):
    platform = os.environ.get("ADES_PLATFORM", default="Generic")
    job_notification_topic_arn = os.environ.get("JOBS_DATA_SNS_TOPIC_ARN")
    if platform not in valid_platforms:
        raise ValueError(
            "ADES_PLATFORM invalid - {} not in {}.".format(platform, valid_platforms)
        )
    app.config["PLATFORM"] = platform
    app.config["JOB_NOTIFICATION_TOPIC_ARN"] = job_notification_topic_arn
    app.run(debug=debug, host=host)


if __name__ == "__main__":
    print("starting")
    host = parse_args()
    flask_wpst(app, debug=True, host=host)
