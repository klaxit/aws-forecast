"""
Script to reproduce forecast $ (%) we see in the AWS Cost Explorer
Written by: Jim Zucker
Date: Sept 4, 2020

Commandline:
python3 get_forecast.py

Environment Variables:
    SLACK_WEBHOOK_URL - URL of the Slack webhook where the report is sent

    FORECAST_COLUMNS_DISPLAYED - specify columnns and order
        default: "Account,M-1,Forecast,Change"

    FORECAST_ACCOUNT_COLUMN_WIDTH - max width for account name
        default: 22

    FORECAST_AWS_PROFILE - set for test on command line

Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
"""

import sys
import logging
import boto3
import os
import datetime
from dateutil.relativedelta import relativedelta
from botocore.exceptions import ClientError
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Initialize you log configuration using the base class
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger()

AWS_LAMBDA_FUNCTION_NAME = ""
try:
    AWS_LAMBDA_FUNCTION_NAME = os.environ['AWS_LAMBDA_FUNCTION_NAME']
except Exception as e:
    logger.info("Not running as lambda")

def send_slack(slack_url, message):
    #make it a NOP if URL is NULL
    if slack_url == "":
        return

    slack_message = {
        'text': message
    }

    req = Request(slack_url, json.dumps(slack_message).encode('utf-8'))
    try:
        response = urlopen(req)
        response.read()
        logger.debug("Message posted to slack")
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
        logger.error("SLACK_URL= %s", slack_url)
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)
        logger.error("slack_url= %s", slack_url)

def display_output(message):
    if 'SLACK_WEBHOOK_URL' in os.environ:
      send_slack(os.environ['SLACK_WEBHOOK_URL'], message)
    else:
      logger.info("Disabling Slack, URL not found")

    print(message)


def calc_forecast(boto3_session):
    #create the clients we need for ce & org
    ce = boto3_session.client('ce')
    org = boto3_session.client('organizations')
    sts = boto3_session.client('sts')

    #initialize the standard filter
    not_filter= {
        "Not": {
            "Dimensions": {
                "Key": "RECORD_TYPE",
                "Values": [ "Credit", "Refund" ]
            }
        }
    }

    utcnow = datetime.datetime.utcnow()
    today = utcnow.strftime('%Y-%m-%d')
    first_day_of_month = utcnow.strftime('%Y-%m') + "-01"
    first_day_next_month = (utcnow + relativedelta(months=1)).strftime("%Y-%m-01")
    first_day_prior_month = (utcnow + relativedelta(months=-1)).strftime("%Y-%m-01")

    logger.debug("today=",today)
    logger.debug("first_day_of_month=",first_day_of_month)
    logger.debug("first_day_next_month=",first_day_next_month)
    logger.debug("first_day_prior_month=",first_day_prior_month)


    #Get total cost_and_usage
    results = []
    data = ce.get_cost_and_usage(
        TimePeriod={'Start': first_day_of_month, 'End':  first_day_next_month}
        , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=not_filter
        )
    results = data['ResultsByTime']
    amount_usage = float(results[0]['Total']['UnblendedCost']['Amount'])

    try:
        data = ce.get_cost_and_usage(
            TimePeriod={'Start': first_day_prior_month, 'End':  first_day_of_month}
            , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=not_filter
            )
        results = data['ResultsByTime']
        amount_usage_prior_month = float(results[0]['Total']['UnblendedCost']['Amount'])
    except Exception as e:
        amount_usage_prior_month = 0

    #Total Forecast
    try:
        data = ce.get_cost_forecast(
            TimePeriod={'Start': today, 'End':  first_day_next_month}
            , Granularity='MONTHLY', Metric='UNBLENDED_COST', Filter=not_filter
            )
        amount_forecast = float(data['Total']['Amount'])
    except Exception as e:
        amount_forecast = amount_usage

    forecast_variance = 100
    if amount_usage_prior_month > 0 :
        forecast_variance = (amount_forecast-amount_usage_prior_month) / amount_usage_prior_month *100

    result = {
        "account_name": 'Total',
        "amount_usage_prior_month": amount_usage_prior_month,
        "amount_usage": amount_usage,
        "amount_forecast": amount_forecast,
        "forecast_variance": forecast_variance
    }
    output=[]
    output.append(result)

    #Get usage caose for all accounts
    results = []
    next_page_token = None
    while True:
        if next_page_token:
            kwargs = {'NextPageToken': next_page_token}
        else:
            kwargs = {}
        data = ce.get_cost_and_usage(
            TimePeriod={'Start': first_day_of_month, 'End':  first_day_next_month}
            , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=not_filter
            , GroupBy=[{'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}]
            , **kwargs)
        results += data['ResultsByTime']
        next_page_token = data.get('NextPageToken')
        if not next_page_token:
            break

    # Print each account
    for result_by_time in results:
        for group in result_by_time['Groups']:
            amount_usage = float(group['Metrics']['UnblendedCost']['Amount'])
            linked_account = group['Keys'][0]

            #create filter
            linked_account_filter = {
                "And": [
                    {
                      "Dimensions": {
                        "Key": "LINKED_ACCOUNT",
                        "Values": [
                          linked_account
                        ]
                      }
                    },
                    not_filter
                ]
            }

            #get prior-month usage, it may not exist
            try:
                data = ce.get_cost_and_usage(
                    TimePeriod={'Start': first_day_prior_month, 'End':  first_day_of_month}
                    , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=linked_account_filter
                    )
                results = data['ResultsByTime']
                amount_usage_prior_month = float(results[0]['Total']['UnblendedCost']['Amount'])
            except Exception as e:
                amount_usage_prior_month = 0

            #Forecast, there maybe insuffcient data on a new account
            try:
                data = ce.get_cost_forecast(
                    TimePeriod={'Start': today, 'End':  first_day_next_month}
                    , Granularity='MONTHLY', Metric='UNBLENDED_COST', Filter=linked_account_filter
                    )
                amount_forecast = float(data['Total']['Amount'])
            except Exception as e:
                amount_forecast = amount_usage

            variance = 100
            if amount_usage_prior_month > 0 :
                variance = (amount_forecast-amount_usage_prior_month) / amount_usage_prior_month *100

            try:
                account_name=org.describe_account(AccountId=linked_account)['Account']['Name']
            except Exception as e:
                account_name=linked_account

            result = {
                "account_name": account_name,
                "amount_usage_prior_month": amount_usage_prior_month,
                "amount_usage": amount_usage,
                "amount_forecast": amount_forecast,
                "forecast_variance": variance
            }
            output.append(result)

    return output


def format_rows(output,account_width):
    #print the heading
    cost_width=10
    change_width=8

    output_rows=[]

    row = {
        "Account": 'Account'.ljust(account_width),
        "M-1": 'M-1'.rjust(cost_width),
        "Forecast": 'Forecast'.rjust(cost_width),
        "Change": 'Change'.rjust(change_width)
    }
    output_rows.append(row)

    #print in decending order by forecast
    lines = sorted(output, key=lambda k: k.get('amount_forecast'), reverse=True)
    for line in lines :
        if len(lines) == 2 and line.get('account_name') == 'Total':
            continue
        change = "{0:,.1f}%".format(line.get('forecast_variance'))
        row = {
            "Account": line.get('account_name')[:account_width].ljust(account_width),
            "M-1": "${0:,.0f}".format(line.get('amount_usage_prior_month')).rjust(cost_width),
            "Forecast": "${0:,.0f}".format(line.get('amount_forecast')).rjust(cost_width),
            "Change": change.rjust(change_width)
        }
        output_rows.append(row)

    return output_rows

def publish_forecast(boto3_session) :
    #read params
    columns_displayed = ["Account", "M-1", "Forecast", "Change"]
    if 'FORECAST_COLUMNS_DISPLAYED' in os.environ:
        columns_displayed=os.environ['FORECAST_COLUMNS_DISPLAYED']
        columns_displayed = columns_displayed.split(',')

    account_width=22
    if 'FORECAST_ACCOUNT_COLUMN_WIDTH' in os.environ:
        account_width=os.environ['FORECAST_ACCOUNT_COLUMN_WIDTH']

    output = calc_forecast(boto3_session)
    formated_rows = format_rows(output, account_width)

    message = ""
    message += "```\n"
    for line in formated_rows :
        formated_line=""
        for column in columns_displayed :
            if formated_line != "" :
                formated_line += " "
            formated_line += line.get(column)
        message += formated_line.rstrip() + "\n"

    message += "```\n"

    message +="\nKeep in mind that using AWS Savings Plans can imply strong "
    message +="costs variations in sub-accounts (thresold effect).\n"

    display_output(message)

def lambda_handler(event, context):
  boto3_session = boto3.session.Session()
  publish_forecast(boto3)

def main():
  try:
    boto3_session = boto3.session.Session()

    if 'FORECAST_AWS_PROFILE' in os.environ:
      profile_name=os.environ['FORECAST_AWS_PROFILE']
      logger.info("Setting AWS Proflie ="+profile_name)
      boto3_session = boto3.session.Session(profile_name=profile_name)

    publish_forecast(boto3)
  except Exception as e:
      logger.error(e);
      sys.exit(1)

  sys.exit(0)

if __name__ == '__main__':
    main()
