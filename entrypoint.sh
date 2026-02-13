#!/bin/bash

# Create .netrc file for NASA CDDIS authentication if credentials are provided
if [ -n "$NASA_USERNAME" ] && [ -n "$NASA_PASSWORD" ]; then
    echo "machine urs.earthdata.nasa.gov login $NASA_USERNAME password $NASA_PASSWORD" > /root/.netrc
    echo "machine cddis.nasa.gov login $NASA_USERNAME password $NASA_PASSWORD" >> /root/.netrc
    chmod 600 /root/.netrc
    echo "Created .netrc for NASA Earthdata authentication"
fi

# Run the main command (python app.py)
exec "$@"
