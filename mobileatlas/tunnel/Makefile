SRCDIR := ./src
TESTDIR := ./tests
VENV := venv
PYTHON := python
PACKAGE_SRC = ./src
PACKAGES := moatt_types moatt_clients moatt_server
INSTALLS := $(patsubst %,install-%-deps,$(PACKAGES))
DEV_INSTALLS := $(patsubst %,install-%-deps-dev,$(PACKAGES))

.PHONY: dev clean $(INSTALLS) $(DEV_INSTALLS) dev-tools lint test

install: $(VENV) $(INSTALLS)

$(INSTALLS): $(VENV)
	. "$(VENV)/bin/activate" && \
		pip install "$(PACKAGE_SRC)/$(patsubst install-%-deps,%,$@)"

dev: $(DEV_INSTALLS) dev-tools

$(VENV):
	"$(PYTHON)" -m venv "$(VENV)"
	. "$(VENV)/bin/activate" && \
		pip install -U pip

$(DEV_INSTALLS): $(VENV)
	. "$(VENV)/bin/activate" && \
		pip install -e "$(PACKAGE_SRC)/$(patsubst install-%-deps-dev,%,$@)[dev]"

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
		black --diff --check "$(SRCDIR)" "$(TESTDIR)"
