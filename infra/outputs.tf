output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "lambda_function_name" {
  value = aws_lambda_function.app.function_name
}

output "lambda_alias_name" {
  value = aws_lambda_alias.live.name
}