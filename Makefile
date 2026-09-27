PY_FILES := $(shell git ls-files '*.py')

.PHONY: install lint deploy

install:
	python -m pip install -r requirements.txt

lint:
	python -m pylint --disable=R,C $(PY_FILES)

deploy:
	venv/bin/python -m pip install -r requirements.txt
	venv/bin/python -m compileall -q $(PY_FILES)
	sudo -n systemctl restart expense-tracker-bot.service
	sleep 5
	sudo -n systemctl is-active --quiet expense-tracker-bot.service
