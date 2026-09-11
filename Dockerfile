FROM python:3.10-alpine AS base
ENV APPLICATION_NAME=argo
ENV APPLICATION_DIR=argo
ENV APPLICATION_PORT=8014

# Install base system requirements
RUN apk add --no-cache postgresql-dev gcc py3-setuptools py3-distutils-extra

WORKDIR /var/www/${APPLICATION_NAME}

# Install Python requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Add application code
COPY ${APPLICATION_DIR} ${APPLICATION_DIR}
COPY api_formatter api_formatter
COPY fixtures fixtures
COPY rac_schemas rac_schemas
COPY entrypoint.* manage.py ./

FROM base AS build

# Install webserver requirements
RUN apk add --no-cache apache2 apache2-dev apache2-mod-wsgi

# Disable all existing sites
RUN find /etc/apache2/conf.d/ -type f -name "*.conf" -print0 | xargs -0 -I {} mv {} {}.disabled
# Enable WSGI
RUN mv /etc/apache2/conf.d/wsgi-module.conf.disabled /etc/apache2/conf.d/wsgi-module.conf
# Create the default site
COPY ./apache/${APPLICATION_NAME}.conf /etc/apache2/conf.d/${APPLICATION_NAME}.conf

# Expose HTTP port
EXPOSE ${APPLICATION_PORT}

ENTRYPOINT [ "./entrypoint.prod.sh" ]