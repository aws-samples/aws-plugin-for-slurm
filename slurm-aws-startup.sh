#!/bin/bash
# AUTHOR: AMR RAGAB
# DESCRIPTION: SLURM STARTUP
# Script/Code is provided, as is, and with no warranty


export SLURM_HEADNODE=$(curl -sS http://169.254.169.254/latest/meta-data/local-ipv4)
export AWS_DEFAULT_REGION=$(curl -sS http://169.254.169.254/latest/dynamic/instance-identity/document | grep region | awk '{print $3}' | sed 's/"//g' | sed 's/,//g')
AWS_DEFAULT_MAC=$(curl -sS http://169.254.169.254/latest/meta-data/mac)
export AWS_SUBNET_ID=@SUBNETID@
export AWS_SECURITY=$(curl -sS http://169.254.169.254/latest/meta-data/network/interfaces/macs/$AWS_DEFAULT_MAC/security-group-ids)
export AWS_AMI=@BASEAMI@
export AWS_KEYNAME=@KEYNAME@
export S3BUCKET=@S3BUCKET@
export SLURM_POWER_LOG=/var/log/power_save.log

##############################################
# DONOT EDIT BELOW THIS LINE
##############################################


function nametoip()
{
    echo $1 | tr "-" "." | cut -c 4-
}

function aws_startup()
{
    TMPFILE=$(mktemp)
    cat << END > $TMPFILE
#!/bin/bash -xe
sudo sed -i "s|enforcing|disabled|g" /etc/selinux/config
sudo yum --nogpgcheck install wget curl epel-release nfs-utils -y
sudo yum install python2-pip -y
sudo pip install awscli
sudo mkdir -p /nfs
aws s3 cp $S3BUCKET/slurm-compute.sh /home/centos/slurm-compute.sh
chmod +x /home/centos/slurm-compute.sh
sudo /home/centos/slurm-compute.sh $SLURM_HEADNODE
END

    aws ec2 run-instances --image-id $AWS_AMI --instance-type $3 --key-name $AWS_KEYNAME \
                      --security-group-ids $AWS_SECURITY --subnet-id $AWS_SUBNET_ID \
                      --iam-instance-profile Name=@SLURMROLE@ \
                      --user-data file://${TMPFILE} --region $AWS_DEFAULT_REGION --private-ip-address $2 \
		                  --block-device-mappings '[ {"DeviceName":"/dev/sda1","Ebs": {"DeleteOnTermination": true}} ]' \
                      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$1_slurm-compute-processor}]" \
    >> $SLURM_POWER_LOG 2>&1

    rm -rf $TMPFILE
}

export SLURM_ROOT=/nfs/slurm
echo "`date` Resume invoked $0 $*" >> $SLURM_POWER_LOG
hosts=$($SLURM_ROOT/bin/scontrol show hostnames $1)
num_hosts=$(echo "$hosts" | wc -l)
aws cloudwatch put-metric-data --metric-name BurstNodeRequestCount --namespace SLURM --value $num_hosts --region $AWS_DEFAULT_REGION
for host in $hosts
do
   private_ip=$(nametoip $host)
   if [[ $host == *ip-10-0-1* ]]; then
      export AWS_SUBNET_ID=@PRIVATE1@
      aws_startup $host $private_ip c4.2xlarge
   elif [[ $host == *ip-10-0-2* ]]; then
      export AWS_SUBNET_ID=@PRIVATE2@
      aws_startup $host $private_ip c4.2xlarge
   elif [[ $host == *ip-10-0-3* ]]; then
      export AWS_SUBNET_ID=@PRIVATE3@
      aws_startup $host $private_ip c4.2xlarge
   fi

   $SLURM_ROOT/bin/scontrol update nodename=$host nodeaddr=$private_ip nodehostname=$host
done
