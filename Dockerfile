FROM python:3.12-alpine

RUN apk add bash

WORKDIR /src

COPY requirements.txt ./

COPY .env ./

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p app
COPY ./app/*.py ./app/

VOLUME [ "/data" ]

CMD ["python", "app/rise_above_monitor.py", "production"]