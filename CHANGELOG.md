# Changelog

All notable changes to this project will be documented in this file. 

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added 

- Added connection to HySDS using the otello library
- Integrated following endpoints with HySDS:
  - GET /processes/{id}/jobs
  - POST /processes/{id}/jobs
  - GET /processes/{id}/jobs/{jobID}
  - POST /processes/{id}/jobs/{jobID}
  - GET /processes/{id}/jobs/{jobID}/result

## [0.1.0] - 2022-04-26

### Added 
- Created initial prototype of OGC WPS-T compliant ADES API
- Implemented following endpoints:
  - Retrieve available processes: GET /processes
  - Deploy a process: POST /processes
  - Retrieve a process description: GET /processes/{id}
  - Undeploy a process: DELETE /processes/{id}
  - Retrieve the list of jobs for a process: GET /processes/{id}/jobs
  - Execute a process: POST /processes/{id}/jobs
  - Retrieve the status of a job: GET /processes/{id}/jobs/{jobID}
  - Dismiss a job: DELETE /processes/{id}/jobs/{jobID}
  - Retrieve the result(s) of a job: GET /processes/{id}/jobs/{jobID}/result
- Created docker deployment for the API
