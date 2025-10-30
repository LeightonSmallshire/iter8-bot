FROM python:3.14
WORKDIR /app

#RUN apt update && apt install docker && apt autoclean

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt


# Install Docker CLI + dependencies
RUN apt-get update && \
    apt-get install -y curl ca-certificates gnupg lsb-release && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/debian $(lsb_release -cs) stable" > \
      /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*


COPY . .

EXPOSE 8080
CMD ["python3", "deployer.py"]
