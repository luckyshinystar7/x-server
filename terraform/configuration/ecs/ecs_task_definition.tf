resource "aws_ecs_task_definition" "my_task" {
  family                   = "my-task-family"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.ecs_tasks_execution_role_arn

  container_definitions = jsonencode([
    {
      name      = "fastapi-container",
      image     = "${var.ecr_repository_url}:vps-latest",
      cpu       = 256,
      memory    = 512,
      essential = true,
      portMappings = [{
        containerPort = 80,
        hostPort      = 80
      }],
      environment = [
        {
          name  = "DATABASE_URL",
          value = "postgresql+asyncpg://${var.database_username}:${var.database_password}@${var.db_instance_address}/${var.database_name}"
        },
        {
          name = "JWT_SECRET",
          value = var.jwt_secret
        },
        {
          name = "ACCESS_TOKEN_DURATION_MINUTES",
          value = var.access_token_duration_minutes
        },
        {
          name = "REFRESH_TOKEN_DURATION_MINUTES",
          value = var.refresh_token_duration_minutes
        },
        {
          name = "ENVIRONMENT",
          value = var.environment
        }
      ]
    }
  ])
}
