#!/bin/sh

# Create config.py if it doesn't exist
if [ ! -f argo/config.py ]; then
    echo "Creating config file"
    cp argo/config.py.deploy argo/config.py
fi

# Apply database migrations
echo "Apply database migrations"
python manage.py migrate

#Start server
echo "Starting server"
python manage.py runserver 0.0.0.0:${APPLICATION_PORT}