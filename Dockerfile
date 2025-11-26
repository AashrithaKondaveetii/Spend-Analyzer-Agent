# Use Google Cloud SDK's container as the base image
FROM google/cloud-sdk

# Specify your e-mail address as the maintainer of the container image
LABEL maintainer="aashritk@pdx.edu"

# Copy the contents of the current directory into the container directory /app
COPY . /app

# Copy the credentials folder to the container
COPY credentials /app/credentials

COPY .env /app/.env
# Set the working directory of the container to /app
WORKDIR /app

# Install Python and create a virtual environment for the application
RUN apt-get update && \
    apt-get install -y python3 python3-venv && \
    python3 -m venv /app/venv

# Install dependencies in the virtual environment
RUN /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -r requirements.txt

# Set the environment path to use the virtual environment
ENV PATH="/app/venv/bin:$PATH"

# Set the parameters to the program
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
