resource "aws_lambda_function" "jupyterhub-costs-lambda-function" {
    filename      = "lambda_function.zip"
    function_name = "jupyterhub-lambda-costs-LambdaReportClusterUsageAndCosts"
    role          = aws_iam_role.jupyterhub-costs-lambda-role.arn
    handler       = "lambda_function.lambda_handler"
    source_code_hash = filebase64sha256("lambda_function.zip")
    runtime = "python3.7"
    timeout = "360"

    environment {
        variables = {
            # See the docstring of the lambda function for descriptions of the env variables below.
            COMMON_TAG_KEY = "Name",
            COMMON_TAG_VALUE = "JUPYTER_HUB_1b_cs109b_WORKER",
            DISTINCT_TAG_KEY = "owner"           
            START_DATE = "2021-02-01"
            S3_BUCKET_FOR_ALL_DATA = "atg-jupyterhub"
            S3_KEY_FOR_COST_DATA_PER_USER = "cost_data/total_cost_per_user.csv"
            S3_KEY_FOR_USAGE_DATA_PER_USER = "cost_data/daily_usage_per_user.csv"
            EMAIL_SENDER_ADDRESS = "tylor_dodge@harvard.edu"
            EMAIL_SENDER_NAME = "Tylor Dodge"
            EMAIL_RECIPIENTS = "abarrett@fas.harvard.edu, tylor_dodge@harvard.edu, jemanuel@fas.harvard.edu, jguillette@fas.harvard.edu, pavlos@seas.harvard.edu, havy@g.harvard.edu"
            ATG_HELP_EMAIL_ADDRESS = "atg@fas.harvard.edu"
        }
    }
}

resource "aws_cloudwatch_event_rule" "jupyterhub-costs-cloudwatch-event-rule" {
  name                = "jupyterhub-costs-cloudwatch-event-rule"
  description         = "Trigger the jupyterhub costs lambda function to report usage and costs of a cluster"
  schedule_expression = "cron(00 13 ? * 6 *)" # Run at 1:00pm every Friday
}

resource "aws_cloudwatch_event_target" "jupyterhub-costs-cloudwatch-event-target" {
  target_id = "jupyterhub-costs-cloudwatch-event-target"
  rule      = aws_cloudwatch_event_rule.jupyterhub-costs-cloudwatch-event-rule.name
  arn       = aws_lambda_function.jupyterhub-costs-lambda-function.arn
}

resource "aws_lambda_permission" "jupyterhub-costs-cloudwatch-permission-to-invoke-lambda" {
    statement_id  = "AllowExecutionFromCloudWatch"
    action        = "lambda:InvokeFunction"
    function_name = aws_lambda_function.jupyterhub-costs-lambda-function.function_name
    principal     = "events.amazonaws.com"
    source_arn    = aws_cloudwatch_event_rule.jupyterhub-costs-cloudwatch-event-rule.arn
}