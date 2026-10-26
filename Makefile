VENV=.venv
PYTHON=$(VENV)/bin/python

APP=main.py
APPNAME=hotel_step20
PYXAPP=$(APPNAME).pyxapp

HTML=$(APPNAME).html
OUTPUT=index.html

run:
	$(PYTHON) -m pyxel run $(APP)

build:
	$(PYTHON) -m pyxel package . $(APP)

html: build
	$(PYTHON) -m pyxel app2html $(PYXAPP)
	mv $(HTML) $(OUTPUT)

deploy: html
	git add $(OUTPUT)
	git commit -m "deploy: update html" || true
	git push

clean:
	rm -f *.pyxapp *.html
