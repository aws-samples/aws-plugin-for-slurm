#!/bin/bash
# Update the host's name with the information from the Name Tag
# This is usually is added by the aws-plugin-for-slurm
# Tag:  Name=awscpu-0
# set the hostname to awscpu-0
# Can be added to the userdata to be used when the instance is instantiated
instanceid=`/usr/bin/curl --fail -m 2 -s 169.254.169.254/latest/meta-data/instance-id`
if [[ ! -z "$instanceid" ]]; then
   region=`/usr/bin/curl -s 169.254.169.254/latest/meta-data/placement/availability-zone`
   region=${region::-1}
   hostname=`/usr/bin/aws ec2 describe-tags --filters "Name=resource-id,Values=$instanceid" "Name=key,Values=Name" --region $region --query "Tags[0].Value" --output=text`
fi
if [ ! -z "$hostname" -a "$hostname" != "None" ]; then
   hostnamectl set-hostname ${hostname}
   echo $hostname
else
   echo `hostname`
fi
