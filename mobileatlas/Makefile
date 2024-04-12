SRCDIRS := ./tunnel/src ./management/src
TESTDIR := ./tests
VENV := venv
PYTHON := python
PACKAGES := moatt_types moatt_clients moatt_server management
INSTALLS := $(patsubst %,install-%-deps,$(notdir $(PACKAGES)))
DEV_INSTALLS := $(patsubst %,install-%-deps-dev,$(notdir $(PACKAGES)))
PIP_FLAGS :=

.PHONY: dev clean $(INSTALLS) $(DEV_INSTALLS) dev-tools lint test

install: $(VENV) $(INSTALLS)

$(INSTALLS): $(VENV)
	./install-package.sh -f "$(PIP_FLAGS)" "$(VENV)" "$(patsubst install-%-deps,%,$@)"

dev: $(DEV_INSTALLS) dev-tools

$(VENV):
	"$(PYTHON)" -m venv "$(VENV)"
	. "$(VENV)/bin/activate" && \
		pip install -U pip

$(DEV_INSTALLS): $(VENV)
	./install-package.sh -d -f "$(PIP_FLAGS)" "$(VENV)" "$(patsubst install-%-deps-dev,%,$@)"

dev-tools:
	. "$(VENV)/bin/activate" && \
		pip install pyright black isort

clean:
	rm -rf "$(VENV)"

test:
	[ -d "$(VENV)" ] || { echo 'Virtual env does not exist. Please run `make dev` first'; false; }
	@. "$(VENV)/bin/activate" && \
		pytest

lint: isort black

.PHONY: isort black

isort:
	@. "$(VENV)/bin/activate" && \
		isort . --profile black

black:
	@. "$(VENV)/bin/activate" && \
		black --diff --check $(SRCDIRS)
