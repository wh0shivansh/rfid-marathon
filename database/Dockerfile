FROM postgres:15

# Copy initialization SQL into the image so Postgres will run it on first startup
COPY init.sql /docker-entrypoint-initdb.d/

EXPOSE 5432

CMD ["postgres"]
