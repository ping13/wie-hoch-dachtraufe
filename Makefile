

.PHONY: help

help:		## output help for all targets
	@echo "These are the targets of this Makefile:"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'


all: help


devserver: 	## Runs Streamlit app on local
	uv run streamlit run app.py

aider:		## Start a chat with an LLM to change your code
	uvx -p 3.12 --from aider-chat aider --architect --watch-files


i18n_extract:	# extract messages from the source code for i18n
	uv run pybabel extract -F babel.cfg -o locale/messages.pot .

i18n_compile:
	uv run pybabel compile -d locale
