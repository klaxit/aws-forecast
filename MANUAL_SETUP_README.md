# Setting up Lambda

There are 3 parts to configuring this to run as a Lambda
1. IAM Role for Lambda - The IAM Role for you Lambda will have to give permissions for Lambda and Cost Explorer.
2. Trigger - Event Bridge(Cloudwatch Alarms) setup with a cron expression to trigger a run daily.
3. Function Code - You can directly paste in the get_forecast.py file is all ready to go.

## Configuring Slack

1. Navigate to https://<your-team-domain>.slack.com/services/new

2. Search for and select "Incoming WebHooks".

3. Choose the default channel where messages will be sent and click "Add Incoming WebHooks Integration".

4. set webhook URL as `SLACK_WEBHOOK_URL` as Lambda env variable

## IAM Role
AWS lambda functions need a role with permissions attached to access AWS resources. Create an IAM policy with the following permissions and the associated IAM role :
![Lambda IAM Role](https://github.com/klaxit/aws-forecast/blob/master/images/IAM_permissions.png)


## Function Code
You can directly copy and paste get_forecast.py into the Lambda definition without modifications.
![Lambda Function Code](https://github.com/klaxit/aws-forecast/blob/master/images/lambda_function.png)

## Configuring Trigger
Here is an example trigger, keep in mind the cron runs in UTC Timezone.
![Lambda Trigger](https://github.com/klaxit/aws-forecast/blob/master/images/event_bridge.png)
