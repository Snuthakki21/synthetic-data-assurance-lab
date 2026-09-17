.PHONY: test build serve package
PYTHON ?= python3
test:
	$(PYTHON) -m coverage run -m unittest discover -s tests -v
	$(PYTHON) -m coverage report --fail-under=90
	$(PYTHON) -m portfolio build
	node --test tests/*.test.mjs
build:
	$(PYTHON) -m portfolio build
serve:
	$(PYTHON) -m portfolio serve
package:
	$(PYTHON) -m pip wheel --no-deps --wheel-dir build/wheels .
