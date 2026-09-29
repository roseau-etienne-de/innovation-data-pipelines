ENV      ?= dev
TAG      ?= latest
PROJECT  := project_id
LOCATION := europe-west1
TZ		 := Europe/Paris
AR       := $(ENV)-ar-innovation-data-pipelines
SA_CRJ   := sa-crj-innovation-dp-runner@project_id.iam.gserviceaccount.com
SA_WF    := sa-wf-innovation-dp-trigger@project_id.iam.gserviceaccount.com

PATH_LIST     := $(subst /, ,$(FILE_PATH))
PIPELINE_PATH := $(word 1, $(PATH_LIST))/$(word 2, $(PATH_LIST))
# ex: data_pipelines/openweather
PIPELINE      := $(word 2, $(PATH_LIST))
# ex: openweather
JOB_NAME      := $(word 3, $(PATH_LIST))
# ex: 01_extract
IMAGE_NAME    := $(ENV)-dp-$(subst _,-,$(PIPELINE)-$(JOB_NAME))
IMAGE         := $(LOCATION)-docker.pkg.dev/$(PROJECT)/$(AR)/$(IMAGE_NAME)
CRJ_NAME      := $(IMAGE_NAME)-crj

WF_FILE  := $(lastword $(PATH_LIST))
WF_NAME  := $(ENV)-dp-$(PIPELINE)-$(basename $(WF_FILE))
# ex: dev-dp-openweather-workflow
SCHEDULER_NAME := $(ENV)-dp-scheduler-$(PIPELINE)-$(basename $(WF_FILE))
# ex: dev-dp-scheduler-openweather-workflow

# Detects Dockerfile (python or dbt)
IS_PYTHON := $(shell [ -f $(FILE_PATH)/*.py ] && echo "python")

ifeq ($(IS_PYTHON),python)
    DOCKERFILE := config_python/Dockerfile.python
else
    DOCKERFILE := config_dbt/Dockerfile.dbt
endif

vars:
	@echo "======== GLOBAL VARIABLES =========="
	@echo "PROJECT=$(PROJECT)"
	@echo "LOCATION=$(LOCATION)"
	@echo "TZ=$(TZ)"
	@echo "PIPELINE_PATH=$(PIPELINE_PATH)"
	@echo "FILE_PATH=$(FILE_PATH)"
	@echo "PIPELINE=$(PIPELINE)"
	@echo "JOB_NAME=$(JOB_NAME)"
	@echo "DOCKERFILE=$(DOCKERFILE)"
	@echo "AR=$(AR)"
	@echo "IMAGE_NAME=$(IMAGE_NAME)"
	@echo "IMAGE=$(IMAGE)"
	@echo "CRJ_NAME=$(CRJ_NAME)"

orchestration_vars:
	@echo "======== ORCHESTRATION VARIABLES =========="
	@echo "WF_FILE=$(WF_FILE)"
	@echo "WF_NAME=$(WF_NAME)"
	@echo "SCHEDULER_NAME=$(SCHEDULER_NAME)"
	@echo "CRON=$(CRON)"


########### CRJ DEPLOYMENT ###########
# 1. Build the container locally
local_build:
	@echo
	@echo "========== LOCAL BUILD =========="
	docker build \
 	-t $(IMAGE):$(TAG) \
	-f $(DOCKERFILE) \
	--build-arg JOB_PATH=$(FILE_PATH) \
	--progress=plain \
	--debug \
	.

allow_docker:
	gcloud auth configure-docker $(LOCATION)-docker.pkg.dev --quiet

# Push the image to AR
push:
	@echo
	@echo "========== PUSH IMG to AR =========="
	docker push $(IMAGE):$(TAG)

# 2. Create or update CRJ, other params exist https://docs.cloud.google.com/sdk/gcloud/reference/run/jobs/create
crj_deploy:
	@echo
	@echo "========== CRJ DEPLOY =========="
	gcloud config set run/region $(LOCATION) && \
	gcloud run jobs deploy $(CRJ_NAME) \
	--image=$(IMAGE):$(TAG) \
	--service-account=$(SA_CRJ) \
	--max-retries=0

build_push_deploy: allow_docker local_build push crj_deploy

# Copies the current dev CRJ image to prd AR (server-side, no docker pull/push)
img_copy:
	@echo
	@echo "========== COPY IMAGE dev -> prd =========="
	$(eval DEV_CRJ_NAME := dev-dp-$(subst _,-,$(PIPELINE)-$(JOB_NAME))-crj)
	$(eval DEV_IMAGE := $(shell gcloud run jobs describe $(DEV_CRJ_NAME) --region=$(LOCATION) --format="value(spec.template.spec.template.spec.containers[0].image)"))
	docker pull $(DEV_IMAGE)
	docker tag $(DEV_IMAGE) $(IMAGE):$(TAG)
	docker push $(IMAGE):$(TAG)

# 3. Run the CRJ
crj_run:
	@echo
	@echo "========== CRJ RUN =========="
	gcloud run jobs execute $(CRJ_NAME) \
	--project=$(PROJECT) \
	--region=$(LOCATION) \
	--args=$(ARGS_CRJ)
# ex :
# make crj_run ARGS_CRJ=--reports,e_feedbacks_android,e_feedbacks_ios FILE_PATH=data_pipelines/app_stores/01_e_feedbacks
# ARGS_CRJ=--reports,e_feedbacks_ios,e_feedbacks_android,--rattrapage_debut,20251209,--rattrapage_fin,20251210


########### ORCHESTRATION DEPLOYMENT ###########
# 1. Deploy the workflow (here FILE_PATH is the path of the workflow.yml file)
wf_deploy:
	@echo
	@echo "========== WORKFLOW DEPLOY =========="
	gcloud workflows deploy $(WF_NAME) \
	--source=$(FILE_PATH) \
	--service-account=$(SA_WF) \
	--project=$(PROJECT) \
	--location=$(LOCATION) \
	--set-env-vars=ENV=$(ENV),LOCATION=$(LOCATION) \
	--labels=env=$(ENV) \
	--call-log-level=log-errors-only

# 2. Deploy the orchestrator
scheduler_deploy:
	@echo
	@echo "========== SCHEDULER DEPLOY =========="
	gcloud scheduler jobs create http $(SCHEDULER_NAME) \
	--location=$(LOCATION) \
	--time-zone=$(TZ) \
	--uri="https://workflowexecutions.googleapis.com/v1/projects/$(PROJECT)/locations/$(LOCATION)/workflows/$(WF_NAME)/executions" \
	--schedule='$(CRON)' \
	--oauth-service-account-email=$(SA_WF) \
	|| \
	( echo "Scheduler already exists, updating..." && \
	gcloud scheduler jobs update http $(SCHEDULER_NAME) \
	--location=$(LOCATION) \
	--schedule='$(CRON)' )


########### LOCAL SETUP ###########
login_gcp:
	gcloud config set project $(PROJECT)
	gcloud auth application-default login
	gcloud auth login

quota:
	gcloud auth application-default set-quota-project $(PROJECT)

delete_images:
	docker image prune -a -f
