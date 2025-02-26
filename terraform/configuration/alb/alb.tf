resource "aws_lb" "my_alb" {
  name               = "${terraform.workspace}-fastapi-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.aws_security_group_alb_sg_id]
  subnets            = [var.subnet_a_id, var.subnet_b_id]
}

resource "aws_lb_target_group" "fastapi_tg" {
  name        = "${terraform.workspace}-fastapi-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/healthcheck"
    protocol            = "HTTP"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.my_alb.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = var.aws_acm_certificate_my_cert_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi_tg.arn
  }
}
