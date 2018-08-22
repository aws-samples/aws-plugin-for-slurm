#!/bin/bash
# AUTHOR: AMR RAGAB
# DESCRIPTION: SLURM SHUTDOWN
# Script/Code is provided, as is, and with no warranty

export SLURM_ROOT=/nfs/slurm
export SLURM_CONF=/nfs/slurm/etc/slurm.conf
export AWS_DEFAULT_REGION=$(curl -sS http://169.254.169.254/latest/dynamic/instance-identity/document | grep region | awk '{print $3}' | sed 's/"//g' | sed 's/,//g')
export SLURM_POWER_LOG=/var/log/power_save.log

function aws_shutdown()
{
    AWS_INSTANCE=$(aws ec2 describe-instances --query 'Reservations[*].Instances[*].{DNS:PrivateDnsName,ID:InstanceId}' --region $AWS_DEFAULT_REGION \
             | grep -A1 -B1 $1 | grep ID | awk -F: '{print $2}' | tr -d '"' | tr -d ',')


    aws ec2 terminate-instances --instance-ids $AWS_INSTANCE --region $AWS_DEFAULT_REGION >> $SLURM_POWER_LOG 2>&1

    sleep 10

    sed -i "/$1/d" $SLURM_ROOT/etc/slurm.conf.d/slurm_nodes.conf
}

export SLURM_ROOT=/nfs/slurm

echo "`date` Suspend invoked $0 $*" >> $SLURM_POWER_LOG
hosts=$($SLURM_ROOT/bin/scontrol show hostnames $1)
num_hosts=$(echo "$hosts" | wc -l)
aws cloudwatch put-metric-data --metric-name ShutdownNodeRequestCount --namespace SLURM --value $num_hosts --region $AWS_DEFAULT_REGION
for host in $hosts
do
   if [[ $host == *ip-10-0-1* ]]; then
      aws_shutdown $host
   elif [[ $host == *ip-10-0-2* ]]; then
      aws_shutdown $host
   elif [[ $host == *ip-10-0-3* ]]; then
      aws_shutdown $host
   fi

   $SLURM_ROOT/bin/scontrol reconfigure
done
