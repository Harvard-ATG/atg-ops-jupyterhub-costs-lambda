resource "aws_iam_role" "jupyterhub-costs-lambda-role" {
    name = "jupyterhub-costs-lambda-role"
    assume_role_policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
        "Action": "sts:AssumeRole",
        "Principal": {
            "Service": "lambda.amazonaws.com"
        },
        "Effect": "Allow",
        "Sid": ""
        }
    ]
}
EOF
}

resource "aws_iam_role_policy" "jupyterhub-costs-lambda-role-policy" {
    name = "jupyterhub-lambda-costs-ReportClusterUsageAndCostsPolicy"
    role = "${aws_iam_role.jupyterhub-costs-lambda-role.id}"
    policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ce:*",
                "s3:*",
                "ses:*",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
EOF
}