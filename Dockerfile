FROM python:3.12-alpine
COPY requirements.txt /
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY main.py /app/
COPY ./templates/ /app/templates/
RUN sh -c 'touch /app/config.json'
WORKDIR /app
CMD ["python", "main.py"]

