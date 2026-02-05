import boto3

AWS_REGION = "us-east-1"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

users_table = dynamodb.Table("Users")
providers_table = dynamodb.Table("Providers")
service_requests_table = dynamodb.Table("ServiceRequests")
service_offers_table = dynamodb.Table("ServiceOffers")