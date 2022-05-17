# Description
Stub flask app that implements a subset of the OGC ADES/WPST specification.

# Get started
Clone the repo and create a subdirectory for the SQLite database file.

    git clone https://github.com/unity-sds/ades_wpst.git
    cd ades_wpst
    mkdir sqlite #to setup the local db

# Install it natively (not in a container) as a python module
Be sure to follow the steps in the "Get started" section above first.  Install
natively as a python module with:

    python setup.py install

The `Flask` python module is required for installation.

# Run it natively (not in a container)
Be sure to follow the steps in the "Get started" section above first.
Run the Flask app server with:

    python -m flask_ades_wpst.flask_wpst


# Build the container locally
Be sure to follow the steps in the "Get started" section above first.
If you run the Docker container as shown above, you will automatically download
the latest container version from Docker Hub.  If you like, you can also build
your own local container as follows:

    docker build -t unity/ades-wpst-api:<tag> -f docker/Dockerfile .
   
For active development purposes (not releases), if you want to build container as frequent as multiple times a day, you can use the following to version containers by datetime

Run the following commands in order, every time:

    export DOCKER_TAG=$(date +"%d-%m-%yT%H.%M.%S")
    docker build -t unity/ades-wpst-api:$DOCKER_TAG -f docker/Dockerfile .
    docker run -it -p 5000:5000 -v ${PWD}/sqlite:/flask_ades_wpst/sqlite unity/ades-wpst-api:$DOCKER_TAG

# Run it as a Docker container
Be sure to follow the steps in the "Get started" section above first.
To run as a Docker container, but sure to do the following in the `docker run`
command as shown in the example below:

1. Map the Flask application server port to the host port (`-p` option)
1. Mount your `sqlite` subdirectory on the host machine in to the container
(`-v` option)
1. Set the `ADES_PLATFORM` environment variable to a supported environment
(e.g., `K8s`, `PBS`, `Generic`) (`-e` option).  If no environment variable
is set, the default is `Generic`, which results in no additional actions
being done on the host.

# Run with Docker: 
For prototype, don't specify the platform when running the docker container

    docker run -it -p 5000:5000 -v ${PWD}/sqlite:/flask_ades_wpst/sqlite unity/ades-wpst-api:<tag>


In the following, set the `ADES_PLATFORM` environment variable to the
appropriate setting for your platform (examples: K8s, PBS)

    docker run -it -p 5000:5000 -v ${PWD}/sqlite:/flask_ades_wpst/sqlite -e "ADES_PLATFORM=<platform>" <org>/ades-wpst-api:<tag>

# Try out the OGC ADES/WPS-T endpoints
You can see the available endpoints by starting with the root endpoint and inspecting the links returned:

    curl http://127.0.0.1:5000/
    
## Using Swagger UI
http://127.0.0.1:5000/api/docs#/
![Screenshot](screenshot.png)

You can find the example requests and sample responses for each WPS-T operation in the `examples` directory. 

## Run on Postman
To try out the WPS-T operations using Postman as a client,

You can import the collection under `examples/postman_collection` into the tool and run the requests.
 
Or you can download the collection: https://www.getpostman.com/collections/0686347f4f69157f07e3

To download Postman: postman.com/downloads/

# Notes
This is an implementation of the OGC ADES/WPS-T specification:
http://docs.opengeospatial.org/per/18-050r1.html#_wps_t_restjson


