#!/bin/bash
cd /home/kavia/workspace/code-generation/recipeexplorer-28868-ada793ea/frontend_web_workspace/frontend_web
npm run build
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
   exit 1
fi

