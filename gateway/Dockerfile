FROM python:3.12-slim-bookworm

LABEL maintainer="Foxerine"
LABEL description="Gateway and manager for the Python code interpreter."

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

WORKDIR /gateway
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY . /gateway

EXPOSE 3874
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3874"]
