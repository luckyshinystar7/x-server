# In root outputs.tf
output "ecr_repository_url" {
  value = module.ecr.ecr_repository_url
}


output "postgres_db_url" {
  value = module.database.db_instance_address
}

output "api_gateway_lambda_url" {
  value = module.apigateway.api_gateway_invoke_url
}
