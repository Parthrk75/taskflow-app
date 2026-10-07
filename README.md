# Taskflow - Docker & Kubernetes

Two-tier application using **Python + MySQL**, containerized with Docker and deployed on Kubernetes using **Helm + Kind**.

## Tech Stack

* Docker
* Kubernetes
* Helm
* Kind
* MySQL 8.0
* Python / Gunicorn

## 1. Build Docker Image

```bash
docker build -t taskflow:1.0.0 .
```

Check image:

```bash
docker images
```

## 2. Push Image to Docker Hub

Login:

```bash
docker login
```

Tag the image:

```bash
docker tag taskflow:1.0.0 <dockerhub-username>/taskflow:1.0.0
```

Push:

```bash
docker push <dockerhub-username>/taskflow:1.0.0
```

Example:

```bash
docker tag taskflow:1.0.0 parth75/taskflow:1.0.0
docker push parth75/taskflow:1.0.0
```

## 3. Run Locally with Docker

Create network:

```bash
docker network create taskflow-net
```

Run MySQL:

```bash
docker run -d --name taskflow-mysql --network taskflow-net \
  -e MYSQL_ROOT_PASSWORD=RootPass123 \
  -e MYSQL_DATABASE=tasksdb \
  -e MYSQL_USER=taskuser \
  -e MYSQL_PASSWORD=taskpass \
  -v taskflow-mysql-data:/var/lib/mysql \
  mysql:8.0
```

Run Taskflow:

```bash
docker run -d --name taskflow-app \
  --network taskflow-net \
  -p 5000:5000 \
  --restart unless-stopped \
  -e DB_HOST=taskflow-mysql \
  -e DB_NAME=tasksdb \
  -e DB_USER=taskuser \
  -e DB_PASSWORD=taskpass \
  -e SECRET_KEY=change-me \
  taskflow:1.0.0
```

Open:

```text
http://localhost:5000
```

## 4. Kubernetes with Kind

Create the cluster:

```bash
kind create cluster --config kind-config.yaml
```

Check nodes:

```bash
kubectl get nodes
```

Load the local image into Kind:

```bash
kind load docker-image taskflow:1.0.0
```

Create namespace:

```bash
kubectl create namespace taskflow
```

## 5. Deploy with Helm

Go to the Helm chart:

```bash
cd taskflow-helm
```

Update `values.yaml` with the Docker image and database configuration.

Validate:

```bash
helm lint .
```

Install:

```bash
helm install taskflow . -n taskflow
```

For future changes:

```bash
helm upgrade taskflow . -n taskflow
```

Check resources:

```bash
kubectl get all -n taskflow
```

Check logs:

```bash
kubectl logs deployment/taskflow-taskflow-helm -n taskflow
```

## 6. Access Application

For local access:

```bash
kubectl port-forward svc/taskflow-taskflow-helm 8080:80 -n taskflow
```

Open:

```text
http://localhost:8080
```

## Architecture

```text
Docker:
Taskflow App → MySQL

Kubernetes:
Taskflow Pod → taskflow-mysql Service → MySQL Pod

Helm:
Manages Taskflow + MySQL Kubernetes resources
```