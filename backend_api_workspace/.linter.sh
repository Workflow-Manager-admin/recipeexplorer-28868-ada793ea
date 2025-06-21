#!/bin/bash
cd /home/kavia/workspace/code-generation/recipeexplorer-28868-ada793ea/backend_api_workspace/backend_api
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

