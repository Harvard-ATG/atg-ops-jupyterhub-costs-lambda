"""

BRIEF DESCRIPTION

-   A lambda function that reports the costs and usage of worker instances in a FAS/SEAS Jupyterhub cluster.
-   It gets the cost and usage data using the AWS Cost Explorer API.
-   It writes out the data into csv files and sends them out, using Amazon SES, as email attachments to specified email recipients.
-   The inputs are to be supplied as environment variables, described below.

INPUTS

-   The lambda function takes as input the following required environment variables:

1. COMMON_TAG_KEY - A common tag whose value is the same for all worker instances in a cluster.
    E.g., specify 'Name'.
    
2. COMMON_TAG_VALUE - The value of the common tag above. E.g., specify 'JUPYTER_HUB_1e_cs109a-cluster_WORKER'
    to filter workers in the cs109a cluster.
    
3. DISTINCT_TAG_KEY - A tag whose value is unique to each worker instance. E.g., specify 'owner',
    a tag whose value is the HUID of a student/TA/faculty operating a particular worker instance.
    
4. EMAIL_RECIPIENTS - A list of email addresses of the people to receive the cost and usage reports.
    E.g., specify, '[jgetega@fas.harvard.edu, abarrett@fas.harvard.edu, jemanuel@fas.harvard.edu]'
    
5. EMAIL_SENDER - The sender email address. Can be the address of the JupyterHub cluster engineer.
    E.g., specify 'jgetega@fas.harvard.edu'.
    
6. S3_BUCKET_FOR_ALL_DATA - The s3 bucket in which the spreadsheet output is stored.
    E.g., specify 'atg-jupyterhub'.
    
7. S3_KEY_FOR_COST_DATA_PER_USER - The s3 key for the cost data spreadsheet.
    E.g., specify 'cost_data/total_cost_per_user.csv'.
    
8. S3_KEY_FOR_USAGE_DATA_PER_USER - The s3 key for the usage data spreadsheet.
    E.g., specify 'cost_data/daily_usage_per_user.csv'.
    
9. START_DATE - The start date of the data in %Y-%m-%d format. Can be the beginning of a semester.
    E.g., specify, '2019-09-01'.

OUTPUTS

-   2 spreadsheets, csv files to be precise.

-   E.g:
    - 'total_cost_per_user.csv', that shows the total cost incurred by each user's instance from the START_DATE to date.
    - 'daily_usage_per_user.csv', that shows the compute time of each user's instance for each day from START_DATE to date.
    
-   The csv filenames are automatically gotten from the S3_KEY_FOR_COST_DATA_PER_USER and S3_KEY_FOR_USAGE_DATA_PER_USER
    environment variables described above.
    
"""

import os
import datetime
import calendar
import time
import json
import boto3
import csv
from dateutil import parser
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

# Serialize datetime in json object
def myconverter(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()
    
# Return result to the caller
def returnmsg(msg="",sts=200, content="application/json", ident=4, convertor=myconverter ):
    return {
        "statusCode": sts,
        "body": json.dumps(msg, default=convertor , indent=ident, cls=DecimalEncoder),
        "headers": {'Content-Type': content, 'Access-Control-Allow-Origin': '*' }
    }

# Search/retrieve a group of instances using a tag that is shared/common among them. 
# Return a list of tags that is specific to each individual instance in the group.
# Call:
#   get_distinct_tag_key_list_of_values('Name','CS-109B','owner')
#   will retrive a list of tag:Values of tag:Key='owner' from instances with tag:Key='Name', tag:Value='CS-109B'
# usage: 
#     for tagValue in get_distinct_tag_key_list_of_values('Name','CS109B','owner') : 
#         get-cost-of (tagKey:owner, tagValue: tagValue)
def get_distinct_tag_key_list_of_values(commonTagKey, commonTagValue, distinctTagKey='owner'):
    
    listOfDistinctEc2TagValues = []
    ec2Client = boto3.client('ec2',region_name='us-east-1')
    filters = [{'Name':'tag:'+commonTagKey, 'Values':[commonTagValue]}]

    reservations = ec2Client.describe_instances(Filters=filters)['Reservations']
    if reservations:
        for res in reservations:
            tag = res['Instances'][0]['Tags']
            rettag = [nm['Value'] for nm in tag if nm['Key'] == distinctTagKey]
            if rettag:
                listOfDistinctEc2TagValues.append (rettag[0])
    return (listOfDistinctEc2TagValues)

# Fetch daily usage in hours for a specific user
def fetch_daily_usage_for_specific_user(start, end, tagKey='owner', tagValue='studentId'):
    ceClient = boto3.client('ce',region_name='us-east-1')
    timeperiod   = {'Start': start,'End': end}
    granularity  = 'DAILY'                    # 'DAILY'|'MONTHLY'|'HOURLY'
    metrics      = ['UsageQuantity']            # AmortizedCost | BlendedCost | NetAmortizedCost | NetUnblendedCost | NormalizedUsageAmount | UnblendedCost | UsageQuantity
    userComputeTimeFilter= { "And" : [{'Dimensions': {'Key': 'USAGE_TYPE', 'Values': ['BoxUsage:t2.small']}}, {'Tags': {'Key': tagKey,'Values': [tagValue]}}] }
    rawDataForUser  = ceClient.get_cost_and_usage(TimePeriod=timeperiod, Granularity=granularity, Metrics=metrics,Filter=userComputeTimeFilter)
    dateAndCostDataForUser   = rawDataForUser['ResultsByTime']
    dailyUsageDictForUser = {}
    for item in dateAndCostDataForUser:
        dailyUsageDictForUser[item['TimePeriod']['Start']] = float(item['Total'][metrics[0]]['Amount'])
    return(dailyUsageDictForUser)

# Calculate total cost incurred by a specific user
def calculate_total_cost_for_specific_user(start, end, tagKey='owner', tagValue='studentId'):
    ceClient = boto3.client('ce',region_name='us-east-1')
    timeperiod   = {'Start': start,'End': end}
    granularity  = 'DAILY'                    # 'DAILY'|'MONTHLY'|'HOURLY'
    metrics      = ['UnblendedCost']            # AmortizedCost | BlendedCost | NetAmortizedCost | NetUnblendedCost | NormalizedUsageAmount | UnblendedCost | UsageQuantity
    costTagFilter= {'Tags': {'Key': tagKey,'Values': [tagValue]}}
    rawcostdata  = ceClient.get_cost_and_usage(TimePeriod=timeperiod, Granularity=granularity, Metrics=metrics,Filter=costTagFilter)
    costbytime   = rawcostdata['ResultsByTime']
    totalcost    = 0
    for cbt in costbytime:
        gran_cost = float(cbt['Total'][metrics[0]]['Amount'])
        totalcost = totalcost + gran_cost
    return(totalcost)


# Lambda main handler
def lambda_handler(event, context):

    try:
        commonTagKey = os.environ['COMMON_TAG_KEY']
        commonTagValue = os.environ['COMMON_TAG_VALUE']
        distinctTagKey = os.environ['DISTINCT_TAG_KEY']
        startDate = os.environ['START_DATE']
        s3BucketForAllData = os.environ['S3_BUCKET_FOR_ALL_DATA']
        s3KeyForCostDataPerUser = os.environ['S3_KEY_FOR_COST_DATA_PER_USER']
        s3KeyForUsageDataPerUser = os.environ['S3_KEY_FOR_USAGE_DATA_PER_USER']
        emailSenderAddress = os.environ['EMAIL_SENDER_ADDRESS']
        emailSenderName = os.environ['EMAIL_SENDER_NAME']
        emailRecipients = os.environ['EMAIL_RECIPIENTS']
        atgHelpEmailAddress = os.environ['ATG_HELP_EMAIL_ADDRESS']
    except:
        return(returnmsg(msg="Some environment variables are missing",sts=404))

    today = datetime.date.today()
    endDate = today.strftime("%Y-%m-%d")
    startDateAsObj = parser.parse(startDate)
    endDateAsObj = parser.parse(endDate)
    prettyStartDateString = calendar.month_abbr[startDateAsObj.month] + ' ' + str(startDateAsObj.day) + ', ' + str(startDateAsObj.year) 
    
    print("startDateAsObj:", startDateAsObj) # Debugging statement. Expected e.g., 2019-09-01 00:00:00
    print("endDateAsObj:", endDateAsObj) # Debugging statement. Expected e.g., 2019-10-31 00:00:00
    
    # Get the list of values for the tag that distinguishes ec2 instances in a cluster
    # An example of such a tag would be the 'owner' tag whose value is a HUID
    listOfDistinctEc2TagValues = get_distinct_tag_key_list_of_values(commonTagKey, commonTagValue, distinctTagKey)
    
    if startDateAsObj < endDateAsObj:
        ownerscost=[]
        
        if listOfDistinctEc2TagValues:
            
            s3 = boto3.resource('s3')
            
            #Write csv that shows daily usage per user and upload it to S3
            localDailyUsageFileName = '/tmp/{}'.format(os.path.basename(s3KeyForUsageDataPerUser))
            if os.path.exists(localDailyUsageFileName):
                os.remove(localDailyUsageFileName)
            s3.meta.client.download_file(s3BucketForAllData, s3KeyForUsageDataPerUser, localDailyUsageFileName)
            with open(localDailyUsageFileName, 'w', newline='') as dailyUsageCsvFile:
                dailyUsageCsvFileWriter = csv.writer(dailyUsageCsvFile, delimiter=',')
                headerRow = []
                headerRowAdded = False
                for distinctEc2TagValue in listOfDistinctEc2TagValues:
                    dailyUsageDictForUser = fetch_daily_usage_for_specific_user(startDate, endDate, distinctTagKey, distinctEc2TagValue)
                    if not headerRowAdded:
                        headerRow.append('User ID')
                        headerRow.extend(dailyUsageDictForUser.keys())
                        dailyUsageCsvFileWriter.writerow(headerRow)
                        headerRowAdded = True
                    userCostRow = []
                    userCostRow.append(distinctEc2TagValue) # E.g. a user ID (HUID) if the distinct tag key is 'owner'
                    for dictKey in dailyUsageDictForUser:
                        userUsage = dailyUsageDictForUser.get(dictKey)
                        userUsage = '%.1f'%userUsage
                        userCostRow.append(userUsage)
                    dailyUsageCsvFileWriter.writerow(userCostRow)
            s3.meta.client.upload_file(localDailyUsageFileName, s3BucketForAllData, s3KeyForUsageDataPerUser)
            
            #Write spreadsheet that shows total cost per user and upload it to S3
            localTotalCostFileName = '/tmp/{}'.format(os.path.basename(s3KeyForCostDataPerUser))
            if os.path.exists(localTotalCostFileName):
                os.remove(localTotalCostFileName)
            s3.meta.client.download_file(s3BucketForAllData, s3KeyForCostDataPerUser, localTotalCostFileName)
            with open(localTotalCostFileName, 'w', newline='') as csv_file:
                csv_file_writer = csv.writer(csv_file, delimiter=',')
                for distinctEc2TagValue in listOfDistinctEc2TagValues:
                    cost = calculate_total_cost_for_specific_user(startDate, endDate, distinctTagKey, distinctEc2TagValue)
                    cost = '%.2f'%cost
                    ownerscost.append({distinctEc2TagValue:cost})
                    csv_file_writer.writerow([distinctEc2TagValue, cost])
                #### Alternative output: Writing to a json file
                # key = 'cost_data/total_cost_per_user.json'
                # s3JsonObject = s3.Object(bucket, key)
                # s3JsonObject.put(
                #    Body=(bytes(json.dumps(ownerscost).encode('UTF-8')))
                # )
            s3.meta.client.upload_file(localTotalCostFileName, s3BucketForAllData, s3KeyForCostDataPerUser)
            
            awsRegion = "us-east-1"
            emailSubject = "Weekly JupyterHub Usage and Cost Report"
            attachments = [localDailyUsageFileName, localTotalCostFileName]
            bodyText = MIMEText("""Hello,

Please find attached usage and cost reports for your JupyterHub cluster.

The {0} spreadsheet shows the compute time for every user on any given day from {1} to date.

On the other hand, the {2} spreadsheet shows the total cost incurred by every user's server from {1} to date.

Please contact {3} with any questions you may have.

Best,

{4}
Harvard University Information Technology
""".format(os.path.basename(localDailyUsageFileName), prettyStartDateString, os.path.basename(localTotalCostFileName), atgHelpEmailAddress, emailSenderName))

            msg = MIMEMultipart('Mixed')
            msg['Subject'] = emailSubject
            msg['FROM'] = emailSenderAddress
            msg['To'] = emailRecipients

            print("Email Sender:", msg['FROM']) #Debugging statement. Expected e.g., jgetega@fas.harvard.edu
            print("Email Recipients:", msg['To']) #Debugging statement. Expected e.g., jgetega@fas.harvard.edu, jgetega@gmail.com, ogetegajoshua@yahoo.com

            msg.attach(bodyText)
            
            for attachment in attachments:
                att = MIMEApplication(open(attachment, 'rb').read())
                att.add_header('Content-Disposition','attachment',filename=os.path.basename(attachment))
                msg.attach(att)

            client = boto3.client('ses', region_name=awsRegion)

            try:
                response = client.send_raw_email(
                    RawMessage={
                        'Data' :msg.as_string(), 
                    }
                )
            except ClientError as e:
                print(e.response['Error']['Message'])
            else:
                print(response['MessageId'])
            
            return(ownerscost)
        else:
            return (returnmsg(msg="No searchable tag found"))
    else:
        return(returnmsg(msg="0"))
