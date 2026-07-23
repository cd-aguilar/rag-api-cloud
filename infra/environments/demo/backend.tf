# Backend "parcial" a proposito: Terraform NO permite usar variables
# dentro de un bloque backend (limitacion del lenguaje, se resuelve
# antes de que las variables existan). Por eso el bucket y la tabla
# de locking se completan en el momento del `terraform init`, no
# quedan hardcodeados ni committeados al repo publico.
#
# Local, primera vez:
#   terraform init \
#     -backend-config="bucket=tu-bucket-de-state" \
#     -backend-config="dynamodb_table=tu-tabla-de-lock"
#
# En GitHub Actions, estos valores salen de secrets (ver deploy.yml).
terraform {
  backend "s3" {
    key     = "rag-api-cloud/demo/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
    # bucket y dynamodb_table se completan via -backend-config
  }
}
