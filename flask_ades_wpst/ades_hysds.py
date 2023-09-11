"""
ADES WPS-T layer for HySDS
Author: Namrata Malarout
"""
import sys
import os
from subprocess import run
import json
from flask_ades_wpst.ades_abc import ADES_ABC
import otello
from otello import Mozart
import requests
import traceback
import backoff

sys.path.append("..")

import utils.github_util as git
from utils.image_container_builder import ContainerImageBuilder
from utils.datatypes import Job

hysds_to_ogc_status = {
    "job-started": "running",
    "job-queued": "accepted",
    "job-failed": "failed",
    "job-completed": "succeeded",
    "job-revoked": "dismissed"
}


class ADES_HYSDS(ADES_ABC):
    def __init__(
        self,
        hysds_version="v4.0",
        mozart_url="https://[MOZART_IP]/mozart/api/v0.2",
        default_queue="test-job_worker-large",
        lw_queue="system-jobs-queue",
        lw_version="v0.0.5",
        grq_url="http://[GRQ_IP]/api/v0.1",
        s3_code_bucket="s3://[S3_BUCKET_NAME]",
    ):
        self._hysds_version = hysds_version
        self._mozart_url = mozart_url
        self._default_queue = default_queue
        self._lw_queue = lw_queue
        self._lw_version = lw_version
        self._grq_url = grq_url
        self.s3_code_bucket = s3_code_bucket
        m = Mozart()

    def _generate_job_id_stub(self, qsub_stdout):
        return ".".join(qsub_stdout.strip().split(".")[:2])

    def _construct_job_spec(self, cwl_wfl, wfl_inputs):
        """
        create the job spec for a process to deploy
        :return:
        """
        command = f"{cwl_wfl}"
        recommended_queues = ["verdi-job_worker"]
        disk_usage = "500MB"
        soft_time_limit = 86400
        time_limit = 86460
        imported_worker_files = {
            "/static-data": ["/static-data", "rw"],
            "/tmp": ["/tmp", "rw"],
            "/stage": ["/stage", "rw"]
        }
        params = list()

        for inp in wfl_inputs:
            hysds_inp = {"name": inp.get("id"), "destination": "context"}
            params.append(hysds_inp)

        job_spec = {
            "command": command,
            "recommended-queues": recommended_queues,
            "disk_usage": disk_usage,
            "soft_time_limit": soft_time_limit,
            "time_limit": time_limit,
            "imported_worker_files": imported_worker_files,
            "params": params,
        }
        return job_spec

    def _construct_hysds_io(self, label, wfl_inputs):
        """
        Create HySDS IO
        :return:
        """
        params = list()

        for inp in wfl_inputs:
            hysds_inp = {"name": inp.get("id"), "from": "submitter", "type": "text"}
            params.append(hysds_inp)
        hysds_io = {"label": label, "params": params, "enable_dedup": True}
        print(hysds_io)
        return hysds_io

    def get_proc(self, proc_id):
        """
        Get job type from HySDS with given proc_id
        :return: proc_desc dictionary as returned by payload
        :param proc_id: the proc_id as registered with wps-t
        """
        m = otello.Mozart()
        proc_id = f"job-{proc_id}"
        job_type = m.get_job_type(proc_id)
        job_type.initialize()
        job_type.describe()
        return str(job_type)

    def get_procs(self):
        """
        Get all job types in HySDS
        :return:
        """
        """
        Otello Implementation
        job_types = m.get_job_types()
        for proc_name in job_types:
        """
        # For prototype,
        m = Mozart()
        job_types = m.get_job_types()
        for proc_name in job_types:
            jt = m.get_job_type(proc_name)
            jt.initialize()
            jt.describe()
        return [str(jt) for jt in job_types]

    def deploy_proc(self, proc_spec):
        """
        Register a process in HySDS and add to SQLite DB
        :param proc_spec: the OGC package deployment payload
        Example proc_spec:
        {
           "processDescription":{
              "process":{
                 "id":"job-hello_world:develop",
                 "title":"Hello World Job",
                 "owsContext":{
                    "offering":{
                       "code":"http://www.opengis.net/eoc/applicationContext/cwl",
                       "content":{
                          "href":"https://some-host/CWL/NDVIMultiSensor.cwl"
                       }
                    }
                 },
                 "abstract":"HySDS Hello World Job",
                 "keywords":[
                 ],
                 "inputs":[
                 ],
                 "outputs":[
                    {
                       "id":"output",
                       "title":"hello_world-product",
                       "formats":[
                          {
                             "mimeType":"image/tiff",
                             "default":true
                          }
                       ]
                    }
                 ]
              },
              "processVersion":"1.0.0",
              "jobControlOptions":[
                 "async-execute"
              ],
              "outputTransmission":[
                 "reference"
              ]
           },
           "immediateDeployment":true,
           "executionUnit":[
              {
                 "href":"docker.registry/ndvims:latest"
              }
           ],
           "deploymentProfileName":"http://www.opengis.net/profiles/eoc/dockerizedApplication"
        }
        :return:
        """
        error = None
        try:
            # Parse the request
            # Get process ID
            proc_id = proc_spec.get("processDescription").get("process").get("id")
            # Get process Label
            proc_label = (
                proc_spec.get("processDescription").get("process").get("abstract")
            )
            # Get process version
            proc_version = proc_spec.get("processDescription").get("processVersion")
            process_name = f"job-{proc_id}:{proc_version}"
            # cwl document for workflow
            cwl_wfl_location = (
                proc_spec.get("processDescription")
                .get("process")
                .get("owsContext")
                .get("offering")
                .get("content")
                .get("href")
            )
            # extract workflow inputs
            wfl_inps = proc_spec.get("processDescription").get("process").get("inputs")
            # get base docker container location
            base_docker = proc_spec.get("executionUnit")[0].get("href")

            job_spec = self._construct_job_spec(
                cwl_wfl=cwl_wfl_location, wfl_inputs=wfl_inps
            )
            hysds_io = self._construct_hysds_io(label=proc_label, wfl_inputs=wfl_inps)

            # Write the HySDS spec files to the register-job repo
            register_job_location = "/unity-sps-register_job"
            with open(
                f"{register_job_location}/docker/hysds-io.json.{proc_id}", "w"
            ) as iofile:
                # open a file with the name that we have assigned stac file name, it's in write mode hence 'w'
                # outfile is a variable that stands for open, json dump the document into stac file
                json.dump(hysds_io, iofile, indent=4)
            with open(
                f"{register_job_location}/docker/job-spec.json.{proc_id}", "w"
            ) as specfile:
                # open a file with the name that we have assigned stac file name, it's in write mode hence 'w'
                # outfile is a variable that stands for open, json dump the document into stac file
                json.dump(job_spec, specfile, indent=4)
        except Exception as ex:
            tb = traceback.format_exc()
            error = f"Failed to create ADES required files for process deployment.\n {ex}.\n{tb}"

        try:
            cb = ContainerImageBuilder(
                image_name=proc_id,
                image_tag=proc_version,
                job_repo_path=register_job_location,
            )
            cb.validate_hysds_ios()
            cb.validate_job_specs()

            build_args = {
                "STAGING_BUCKET": os.getenv("STAGING_BUCKET"),
                "CLIENT_ID": os.getenv("CLIENT_ID"),
                "DAPA_API": os.getenv("DAPA_API"),
                "JOBS_DATA_SNS_TOPIC_ARN": os.getenv("JOBS_DATA_SNS_TOPIC_ARN"),
            }
            cb.build_image(build_args=build_args)
            image_url = cb.push_image()

            cb.publish_job_spec()
            cb.publish_hysds_io()
            cb.publish_container(image_url)

            # repo = None  # to be replaced by some function / code
            # # TODO: figure out how to assign repo without git clone
            # commit_hash = git.update_git_repo(
            #     repo,
            #     repo_path=register_job_location,
            #     repo_name="unity-sps-register_job",
            #     algorithm_name=proc_id,
            # )
            # print("Updated Register Job repo with hash {}".format(commit_hash))
        except Exception as ex:
            tb = traceback.format_exc()
            error = "Failed to register {}\n Exception: {}\n Error: {}".format(
                f"{proc_id}:{proc_version}", ex, tb
            )

        if error is not None:
            raise RuntimeError(error)

        return

    def undeploy_proc(self, proc_id):
        get_jobspec_endpoint = os.path.join(self._MOZART_REST_API, "job_spec/type")
        remove_jobspec_endpoint = os.path.join(self._MOZART_REST_API, "job_spec/remove")
        remove_container_endpoint = os.path.join(
            self._MOZART_REST_API, "container/remove"
        )

        try:
            print(f"Getting container id information for job type job-{proc_id}")
            r = requests.get(
                get_jobspec_endpoint, params={"id": f"job-{proc_id}"}, verify=False
            )
            response = r.json()
            if response.get("success"):
                container_id = response.get("result").get("container")
                print(f"Found container {container_id} for job type {proc_id}")
            else:
                raise RuntimeError(
                    f"Container information not found for job type {proc_id}. {r}"
                )
        except Exception as ex:
            raise Exception(ex)
        try:
            print(f"Deleting container {container_id}")
            requests.get(
                remove_container_endpoint, params={"id": container_id}, verify=False
            )
        except Exception as ex:
            raise Exception(f"Failed to delete container {container_id}. {ex}")
        try:
            print(f"Deleting jobspec for job-{proc_id}")
            requests.get(
                remove_jobspec_endpoint, params={"id": f"job-{proc_id}"}, verify=False
            )
        except Exception as ex:
            raise Exception(f"Failed to delete jobspec job-{proc_id}. {ex}")
        return

    @backoff.on_exception(backoff.expo, Exception, jitter=backoff.full_jitter, max_time=10) 
    def _hysds_poll_job_status(self, hysds_job):
        return hysds_job.get_status()

    def exec_job(self, job_spec):
        """

        :param job_spec:
        :return:
        """
        print(job_spec)
        # Make Otello call to submit job with job type and parameters
        m = otello.Mozart()
        proc_id = f"job-{job_spec.get('proc_id')}"
        print(proc_id)
        print(job_spec.get("inputs").get("inputs"))
        job = m.get_job_type(proc_id)
        job.initialize()  # retrieving the Job wiring and parameters
        # Create params dictionary
        params = dict()
        if len(job_spec.get("inputs").get("inputs")) != 0:
            for input in job_spec.get("inputs").get("inputs"):
                params[input["id"]] = input["data"]
        job.set_input_params(params=params)

        if "labels" in job_spec["inputs"]:
            labels = job_spec["inputs"]["labels"]
        else:
            labels = []

        print("Submitting job of type job-{}\n Parameters: {}".format(proc_id, params))

        try:
            # Publish job to JobPublisher passed in the job_spec
            hysds_job = job.submit_job(queue="verdi-job_worker", priority=0, tag="test")

            print(f"Submitted job with id {hysds_job.job_id}")

            # Sleep for artificial latency to allow job to propagate through hysds
            return {
                "job_id": hysds_job.job_id,
                "status": hysds_to_ogc_status[self._hysds_poll_job_status(hysds_job)],
                "inputs": params,
                "error": None,
            }
        except Exception as ex:
            error = str(ex)
            return {"job_id": hysds_job.job_id, "status": "failed", "inputs": params, "error": error}

    def dismiss_job(self, proc_id, job_id):
        # We can only dismiss jobs that were last in accepted or running state.
        # initialize job
        response = {
                "job_id": None,
                "status": None,
                "error": None
            }
        job = otello.Job(job_id=job_id)
        status = job.get_status()
        print("dismiss_job got start status: ", status)
        if status in ("job-started", "job-queued"):
            # if status is started then revoke the job
            try:
                if status == "job-started":
                    job.revoke()
                elif status == "job-queued":
                    # if status is queued then purge (remove) the job
                    job.remove()
                response["job_id"] = job_id
                response["status"] = hysds_to_ogc_status.get("job-revoked")

            except Exception as ex:
                if "NotFoundError(404," in ex.get("message") :
                    response["error"] = "ADES Job Management Job Suite is not installed. So cannot Dismiss Job"
                else:
                    response["error"] = f"Failed to dismiss job. {ex}"
        else:
            response["error"] = f"Can not dismiss a job in state {hysds_to_ogc_status.get(status)}."
        return response

    def get_jobs(self, proc_id):
        jobs_result = list()
        m = otello.Mozart()
        job_set = m.get_jobs()
        print(f"filtering jobs for process job-{proc_id}")
        # {"jobID": job_id, "status": job_info["status"], "message": "Status of job {}".format(job_id)}
        for job in job_set:
            job_dets = dict()
            job_info = job.get_info()
            if job_info.get("type") == f"job-{proc_id}":
                job_dets["jobID"] = job_info.get("payload_id")
                job_dets["status"] = hysds_to_ogc_status.get(job.get_status())
                job_dets["inputs"] = (
                    job_info.get("job")
                    .get("params")
                    .get("job_specification")
                    .get("params")
                )
                jobs_result.append(job_dets)
        return jobs_result

    def get_job(self, job_spec):
        # Get PBS job status.
        #
        job_id = job_spec["jobID"]
        job = otello.Job(job_id=job_id)
        status = job.get_status()
        job_spec["status"] = hysds_to_ogc_status.get(status)
        print(f"Job status {status}")
        return job_spec

    def get_job_results(self, job_id):
        job = otello.Job(job_id=job_id)
        products = job.get_generated_products()
        print(f"Found products: {products}")
        return products
