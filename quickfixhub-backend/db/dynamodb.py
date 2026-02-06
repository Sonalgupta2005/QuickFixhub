import boto3
import os

AWS_REGION = "us-east-1"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

# ----------------------------------
# Tables (must already exist in AWS)
# ----------------------------------

users_table = dynamodb.Table("Users")

provider_profiles_table = dynamodb.Table("ProviderProfiles")

service_requests_table = dynamodb.Table("ServiceRequests")

service_offers_table = dynamodb.Table("ServiceOffers")
