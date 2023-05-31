SHELL:=/bin/bash
BUILDPATH=$(CURDIR)

# parameters
GIT_COMMIT:=$(shell git rev-parse --short HEAD)
PROJECT_NAME=devops_tools
VERSION?=v1

LOCAL_IMAGE_NAME=${PROJECT_NAME}:${VERSION}
DOCKERHUB_REGISTRY_NAME = hub.docker.com/yakirinp/${PROJECT_NAME}:${VERSION}

# docker parameters
DOCKER_CMD=$(shell which docker)
PODMAN_CMD=$(shell which podman)
DOCKER_BUILD=$(PODMAN_CMD) build
DOCKER_PULL=$(PODMAN_CMD) pull
DOCKER_PUSH=$(PODMAN_CMD) push
DOCKER_PRUNE=$(PODMAN_CMD) image prune -f
DOCKER_TAG=$(PODMAN_CMD) tag
DOCKER_COMPOSE_CMD=$(shell which docker-compose)

.PHONY: test docker clean all
all: build docker clean

docker: docker-build docker-tag docker-push

test:
	echo ${LOCAL_IMAGE_NAME}
	echo ${DOCKERHUB_REGISTRY_NAME}

clean:
	$(DOCKER_PRUNE)

build:
	echo no need to build

.ONESHELL: ddocker-build docker-tag docker-push
docker-build:
	$(DOCKER_BUILD) -t ${LOCAL_IMAGE_NAME} -f APP-META/Dockerfile .

docker-tag:
	$(DOCKER_TAG) ${LOCAL_IMAGE_NAME} ${DOCKERHUB_REGISTRY_NAME}

docker-push:
	$(DOCKER_PUSH) ${DOCKERHUB_REGISTRY_NAME}
