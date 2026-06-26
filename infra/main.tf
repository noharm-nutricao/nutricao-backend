terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

locals {
  nutritional_job_endpoint = "${trimsuffix(aws_lambda_function_url.app_url.function_url, "/")}/nutritional/job/run"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_ecr_repository" "app" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_security_group" "lambda_sg" {
  name        = "${var.project_name}-lambda-sg"
  description = "Security group da Lambda"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_lambda_function" "app" {
  function_name = var.project_name
  role          = aws_iam_role.lambda_role.arn

  package_type = "Image"
  image_uri    = var.image_uri

  timeout     = 30
  memory_size = 512

  publish = true

  vpc_config {
    subnet_ids         = data.aws_subnets.default.ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  environment {
    variables = {
      DB_HOST     = var.db_host
      DB_PORT     = "5432"
      DB_NAME     = var.db_name
      DB_USER     = var.db_user
      DB_PASSWORD = var.db_password
      API_KEY     = var.api_key
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_vpc
  ]
}

resource "aws_lambda_alias" "live" {
  name             = "live"
  description      = "Alias de produção"
  function_name    = aws_lambda_function.app.function_name
  function_version = aws_lambda_function.app.version
}

resource "aws_lambda_function_url" "app_url" {
  function_name      = aws_lambda_function.app.function_name
  authorization_type = "NONE"
  qualifier          = aws_lambda_alias.live.name

  cors {
    allow_credentials = true
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["*"]
    max_age           = 86400
  }
}

resource "aws_cloudwatch_event_connection" "nutritional_job" {
  count = var.enable_nutritional_job_schedule ? 1 : 0

  name               = "${var.project_name}-nutritional-job"
  description        = "Conexao EventBridge para disparo do job nutricional"
  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-API-Key"
      value = var.api_key
    }
  }
}

resource "aws_cloudwatch_event_api_destination" "nutritional_job" {
  count = var.enable_nutritional_job_schedule ? 1 : 0

  name                             = "${var.project_name}-nutritional-job"
  description                      = "POST no endpoint do job nutricional"
  invocation_endpoint              = local.nutritional_job_endpoint
  http_method                      = "POST"
  invocation_rate_limit_per_second = 1
  connection_arn                   = aws_cloudwatch_event_connection.nutritional_job[0].arn
}

resource "aws_iam_role" "eventbridge_api_destination_role" {
  count = var.enable_nutritional_job_schedule ? 1 : 0

  name = "${var.project_name}-eventbridge-api-destination-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_api_destination_policy" {
  count = var.enable_nutritional_job_schedule ? 1 : 0

  name = "${var.project_name}-eventbridge-api-destination-policy"
  role = aws_iam_role.eventbridge_api_destination_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "events:InvokeApiDestination"
        ]
        Resource = [
          aws_cloudwatch_event_api_destination.nutritional_job[0].arn
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "nutritional_job" {
  count = var.enable_nutritional_job_schedule ? 1 : 0

  name                = "${var.project_name}-nutritional-job"
  description         = "Dispara o job nutricional a cada 3 minutos"
  schedule_expression = var.nutritional_job_schedule_expression
}

resource "aws_cloudwatch_event_target" "nutritional_job" {
  count = var.enable_nutritional_job_schedule ? 1 : 0

  rule      = aws_cloudwatch_event_rule.nutritional_job[0].name
  target_id = "nutritional-job-endpoint"
  arn       = aws_cloudwatch_event_api_destination.nutritional_job[0].arn
  role_arn  = aws_iam_role.eventbridge_api_destination_role[0].arn
  input     = jsonencode({ source = "eventbridge" })
}
