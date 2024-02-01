import os
import copy
from flask import Response
from jinja2 import Template
import logging
import json
from utils.job_publisher import SnsJobPublisher
from flask_ades_wpst.sqlite_connector import (
    sqlite_get_procs,
    sqlite_get_proc,
    sqlite_deploy_proc,
    sqlite_undeploy_proc,
    sqlite_get_jobs,
    sqlite_get_job,
    sqlite_exec_job,
    sqlite_dismiss_job,
    sqlite_update_job_status,
)
from datetime import datetime

log = logging.getLogger(__name__)


class ADES_Base:
    def __init__(self, app_config):
        self.host = "http://127.0.0.1:5000"
        self._app_config = app_config
        self._platform = app_config["PLATFORM"]
        if self._platform == "Generic":
            from flask_ades_wpst.ades_generic import ADES_Generic as ADES_Platform
        elif self._platform == "K8s":
            from flask_ades_wpst.ades_k8s import ADES_K8s as ADES_Platform
        elif self._platform == "PBS":
            from flask_ades_wpst.ades_pbs import ADES_PBS as ADES_Platform
        elif self._platform == "HYSDS":
            from flask_ades_wpst.ades_hysds import ADES_HYSDS as ADES_Platform
        else:
            # Invalid platform setting.  If you do implement a new
            # platform here, you must also add it to the valid_platforms
            # tuple default argument to the flask_wpst function in
            # flask_wpst.py.
            raise ValueError("Platform {} not implemented.".format(self._platform))
        self._ades = ADES_Platform()
        self._job_publisher = SnsJobPublisher(app_config["JOB_NOTIFICATION_TOPIC_ARN"])

        # set of job inputs to append to process deploy requests and job execute requests
        # { "job_parameter_name": "ENVIRONMENT_VARIABLE_WITH_JOB_PARAMETER_VALUE" }
        self._job_config_inputs = {
            "jobs_data_sns_topic_arn": "JOBS_DATA_SNS_TOPIC_ARN",
            "dapa_api": "DAPA_API",
            "client_id": "CLIENT_ID",
            "staging_bucket": "STAGING_BUCKET",
        }

    def proc_dict(self, proc):
        return {
            "id": proc[0],
            "title": proc[1],
            "abstract": proc[2],
            "keywords": proc[3],
            "owsContextURL": proc[4],
            "inputs": json.loads(proc[5]),
            "outputs": json.loads(proc[6]),
            "processVersion": proc[7],
            "jobControlOptions": proc[8].split(","),
            "outputTransmission": proc[9].split(","),
            "immediateDeployment": str(bool(proc[9])).lower(),
            "executionUnit": proc[10],
        }

    def get_procs(self):
        saved_procs = sqlite_get_procs()
        procs = [self.proc_dict(saved_proc) for saved_proc in saved_procs]
        return procs

    def get_proc(self, proc_id):
        """
        TODO: sqlite_get_proc vulnerable to sql injeciton through proc_id
        """
        saved_proc = sqlite_get_proc(proc_id)
        proc_dict = {}
        if saved_proc:
            proc_dict = self.proc_dict(saved_proc)
        return proc_dict

    def deploy_proc(self, req_proc):
        """
        DONE
        :param proc_desc:
        :return:
        """
        print(req_proc)
        proc_desc = req_proc["processDescription"]
        proc = proc_desc["process"]
        proc_id = proc["id"]
        # proc_id = f"{proc['id']}-{proc_desc['processVersion']}"
        proc_title = proc["title"]
        proc_abstract = proc["abstract"]
        proc_keywords = proc["keywords"]
        proc_version = proc_desc["processVersion"]
        job_control = proc_desc["jobControlOptions"]
        proc_desc_url = "{}/processes/{}".format(self.host, f"{proc_id}:{proc_version}")

        # creating response
        proc_summ = dict()
        proc_summ["id"] = proc_id
        proc_summ["title"] = proc_title
        proc_summ["abstract"] = proc_abstract
        proc_summ["keywords"] = proc_keywords
        proc_summ["version"] = proc_version
        proc_summ["jobControlOptions"] = job_control
        proc_summ["processDescriptionURL"] = proc_desc_url

        # add unity-sps workflow step inputs to process inputs
        backend_req_proc = copy.deepcopy(req_proc)
        backend_req_proc["processDescription"]["process"]["inputs"] += [
            {"id": key} for key in self._job_config_inputs.keys()
        ]

        try:
            self._ades.deploy_proc(backend_req_proc)
            sqlite_deploy_proc(req_proc)
        except Exception as ex:
            print(
                f"Failed to create ADES required files for process deployment. {ex.message}"
            )
        return proc_summ

    def undeploy_proc(self, proc_id):
        # self._ades.undeploy_proc(proc_id)
        proc_desc = self.proc_dict(sqlite_undeploy_proc(proc_id))
        print("proc_desc: ", proc_desc)
        return proc_desc

    def get_jobs(self, proc_id=None):
        # Removing sqlite query
        # jobs = sqlite_get_jobs(proc_id)
        # Query ADES
        jobs_list = self._ades.get_jobs(proc_id)
        return jobs_list

    def get_job(self, proc_id, job_id):
        # Required fields in job_info response dict:
        #   jobID (str)
        #   status (str) in ["accepted" | "running" | "succeeded" | "failed"]
        # Optional fields:
        #   expirationDate (dateTime)
        #   estimatedCompletion (dateTime)
        #   nextPoll (dateTime)
        #   percentCompleted (int) in range [0, 100]
        # job_spec = sqlite_get_job(job_id)
        # if job was dismissed, then bypass querying the ADES backend
        # job_info = {"jobID": job_id, "status": job_spec["status"]}
        # if job_spec["status"] == "dismissed":
        #     return job_info
        # otherwise, query the ADES backend for the current status
        job_spec = dict()
        job_spec["jobID"] = job_id
        ades_resp = self._ades.get_job(job_spec)
        print(ades_resp)
        job_info = dict()
        job_info["status"] = ades_resp["status"]
        job_info = {
            "jobID": job_id,
            "status": job_info["status"],
            "message": "Status of job {}".format(job_id),
        }
        # and update the db with that status
        # (job_id, job_info["status"])
        return job_info

    def exec_job(self, proc_id, job_params):
        """
        Execute algorithm
        :param proc_id: algorithm identifier
        :param job_inputs: Parameters for the job
        :return:
        """
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")
        # TODO: this needs to be globally unique despite underlying processing cluster
        # job_id = f"{proc_id}-{hashlib.sha1((json.dumps(job_inputs, sort_keys=True) + now).encode()).hexdigest()}"

        # TODO: relying on backend for job id means we need to pass the job publisher to backend impl code for submit notification
        # job notifications should originate from this base layer once

        # add input values from environment variables
        job_params["inputs"] += [
            {"id": key, "data": os.getenv(value)}
            for key, value in self._job_config_inputs.items()
        ]
        job_spec = {
            "proc_id": proc_id,
            # "process": self.get_proc(proc_id),
            "inputs": job_params,
            "job_publisher": self._job_publisher,
        }
        ades_resp = self._ades.exec_job(job_spec)

        # ades_resp will return platform specific information that should be
        # kept in the database with the job ID record
        sqlite_exec_job(proc_id, ades_resp["job_id"], ades_resp["inputs"], ades_resp)
        return {
            "code": 201,
            "location": "{}/processes/{}/jobs/{}".format(
                self.host, proc_id, ades_resp["job_id"]
            ),
        }

    def dismiss_job(self, proc_id, job_id):
        """
        Stop / Revoke Job
        :param proc_id:
        :param job_id:
        :return:
        """
        ades_resp = self._ades.dismiss_job(proc_id, job_id)
        if ades_resp.get("error") is None:
            job_spec = sqlite_dismiss_job(job_id)
        else:
            job_spec = {"error": ades_resp.get("error")}
        return job_spec

    def get_job_results(self, proc_id, job_id):
        # job_spec = self.get_job(proc_id, job_id)
        products = self._ades.get_job_results(job_id=job_id)
        job_result = dict()
        outputs = list()
        for product in products:
            id = product.get("id")
            location = None
            locations = product.get("browse_urls")
            for loc in locations:
                if loc.startswith("s3://"):
                    location = loc
            # create output blocks and append
            output = {"mimeType": "tbd", "href": location, "id": id}
            outputs.append(output)
        job_result["outputs"] = outputs
        return job_result
