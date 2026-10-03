FROM python:3.12-slim

# The code imports itself as `cisco_cdr_analyzer`, so it must live in a folder with that name
WORKDIR /app
COPY requirements.txt /app/cisco_cdr_analyzer/requirements.txt
RUN pip install --no-cache-dir -r /app/cisco_cdr_analyzer/requirements.txt
COPY . /app/cisco_cdr_analyzer

VOLUME ["/data", "/output"]
ENTRYPOINT ["python", "-m", "cisco_cdr_analyzer"]
CMD ["--cdr", "/app/cisco_cdr_analyzer/cdr.csv", "--cmr", "/app/cisco_cdr_analyzer/cmr.csv", "--summary", "--report", "--output", "/output"]
