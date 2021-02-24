# atg-ops-jupyterhub-costs-lambda
This repository contains code for a lambda function that sends weekly reports of the usage and costs of a FAS/SEAS jupyterhub cluster.
It also contains the terraform code for the lambda function's infrastructure. 

## Deployment
`cd terraform`<br/>
Open lambda.tf, inspect the values of the environment variables, and edit where appropriate.<br/>
`zip -r lambda_function.zip lambda_function.py`<br/>
`terraform apply`<br/>
`rm lambda_function.zip`<br/>
