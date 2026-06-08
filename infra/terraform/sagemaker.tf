# SageMaker Endpoint for GNN and TFT Inference Models

resource "aws_sagemaker_model" "gnn_model" {
  name               = "${var.project_name}-gnn-model"
  execution_role_arn = aws_iam_role.sagemaker_execution.arn

  primary_container {
    image          = "763104351884.dkr.ecr.${var.aws_region}.amazonaws.com/pytorch-inference:2.0.0-cpu-py310" # Standard AWS PyTorch image
    model_data_url = "s3://${aws_s3_bucket.model_artifacts.bucket}/gnn_model.tar.gz"
  }
}

resource "aws_sagemaker_endpoint_configuration" "gnn_endpoint_config" {
  name = "${var.project_name}-gnn-ep-config"

  production_variants {
    variant_name           = "AllTraffic"
    model_name             = aws_sagemaker_model.gnn_model.name
    initial_instance_count = 1
    instance_type          = "ml.t2.medium"
  }
}

resource "aws_sagemaker_endpoint" "gnn_endpoint" {
  name                 = "${var.project_name}-gnn-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.gnn_endpoint_config.name
}

resource "aws_s3_bucket" "model_artifacts" {
  bucket = "${var.project_name}-models-${var.environment}"
}
