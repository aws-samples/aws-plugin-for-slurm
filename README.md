
# AWS Plugin for Slurm - Version 2

> The [plugin](https://github.com/aws-samples/aws-plugin-for-slurm) initially released in 2018 has been entirely redeveloped. Major changes includes: support of EC2 Fleet capabilities such as Spot or instance type diversification, decoupling node names from instance host names or IP addresses, better error handling when a node fails to respond during its launch. Contrary to the *master* branch, this branch does not provide a CloudFormation template to deploy the Slurm headnode on AWS.

[Slurm](https://slurm.schedmd.com/) is a popular HPC cluster management system. This plugin enables the Slurm headnode to dynamically deploy and destroy compute resources in the cloud, regardless of where the headnode is executed. Traditional HPC clusters usually distribute jobs over a static set of resources. With this plugin, you can take advantage of the elasticity and pay-per-use model of the cloud to run jobs.

Typical use cases include:

* Bursting into the cloud to dynamically allocate resources in addition to your on-premises resources. This enables to run jobs faster, or to take advantage of the wide selection of AWS instance types to run jobs that have specific requirements, such as GPU-based workloads.

* Deploying a self-contained HPC cluster in the cloud, as an alternative approach to managed HPC clusters, such as [AWS ParallelCluster](https://aws.amazon.com/hpc/parallelcluster/).

## Concepts

This plugin relies on the existing Slurm power save logic (see [Power Saving Guide](https://slurm.schedmd.com/power_save.html) and [Cloud Scheduling Guide](https://slurm.schedmd.com/elastic_computing.html) in the Slurm documentation).

All nodes that Slurm may launch in AWS must be initially declared in the Slurm configuration, but their IP address or host name in advance doesn't have to be specified in advance. These nodes are placed initially in a power saving mode. When work is assigned to them by the scheduler, the headnode executes the program `ResumeProgram` and passes the list of nodes to resume as argument. The program launches a new EC2 instance for each node, and updates the IP address and the host name in Slurm. After a idle period, when nodes are no longer required, the headnode executes the program `SuspendProgram` with the list of nodes to suspend as argument. The program terminates the associated EC2 instances, and the nodes are placed in power mode saving again.

This plugin consists of the programs that Slurm executes when nodes are restored in normal operation (`ResumeProgram`) or placed in power mode saving (`SuspendProgram`). It relies upon EC2 Fleet to launch instances.

## Plugin files

The plugin is composed of 5 Python files and 2 JSON configuration files. They must reside in the same folder.

### `config.json`

You must create this JSON file to specify the plugin and Slurm configuration parameters.

```
{
   "LogLevel": "STRING",
   "LogFileName": "STRING",
   "SlurmBinPath": "STRING",
   "SlurmConf": {
      "PrivateData": "STRING",
      "ResumeProgram": "STRING",
      "SuspendProgram": "STRING",
      "ResumeRate": INT,
      "SuspendRate": INT,
      "ResumeTimeout": INT,
      "SuspendTime": INT,
      "TreeWidth": INT
      ...
   }
}
```

* `LogLevel`: Logging level. Possible values are `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`. Default is `DEBUG`.
* `LogFileName`: Full path to the log file location. Default is `PLUGIN_PATH\aws_plugin.log`.
* `SlurmBinPath`: Full path to the folder that contains Slurm binaries like `scontrol` or `sinfo`. Example: `/slurm/bin`.
* `SlurmConf`: These attributes are used by `generate_conf.py` to generate the content that must be appended to the Slurm configuration file. You must specify at least the following attributes:
   * `PrivateData`: Must be equal to `CLOUD` such that EC2 compute nodes that are idle are returned by Slurm command outputs such as `sinfo`.
   * `ResumeProgram`: Full path to the location of `resume.py`. Example: `/slurm/etc/aws/resume.py`.
   * `SuspendProgram`: Full path to the location of `suspend.py`. Example: `/slurm/etc/aws/suspend.py`.
   * `ResumeRate`: Maximum number of EC2 instances that Slurm can launch per minute. You might reach EC2 request rate limits if this value is too high. Recommended value is `100`.
   * `SuspendRate`: Maximum number of EC2 instances that Slurm can terminate per minute. You might reach EC2 request rate limits if this value is too high. Recommended value is `100`.
   * `ResumeTimeout`: Maximum time permitted (in seconds) between when a node resume request is issued and when the node is actually available for use. You should take into consideration the time it takes to launch an instance and to run your bootstrap scripts when defining this value.
   * `SuspendTime`: Nodes becomes eligible for power saving mode after being idle or down for this number of seconds. As per the Slurm documentation, it is recommended that the value of `SuspendTime` be at least as large as the sum of `SuspendTimeout` (default is 30 seconds) plus `ResumeTimeout`.
   * `TreeWidth`. Refer to the Slurm documentation. Recommended value is `60000`.

Example:

```
{
   "LogLevel": "INFO",
   "LogFileName": "/var/log/slurm/aws.log",
   "SlurmBinPath": "/slurm/bin",
   "SlurmConf": {
      "PrivateData": "CLOUD",
      "ResumeProgram": "/slurm/etc/aws/resume.py",
      "SuspendProgram": "/slurm/etc/aws/suspend.py",
      "ResumeRate": 100,
      "SuspendRate": 100,
      "ResumeTimeout": 300,
      "SuspendTime": 350,
      "TreeWidth": 60000
   }
}
```

### `partitions.json`

You must create this file to specify the groups of nodes and associated partitions that Slurm can launch in AWS.

```
{
   "Partitions": [
      {
         "PartitionName": "STRING",
         "NodeGroups": [
            {
               "NodeGroupName": "STRING",
               "MaxNodes": INT,
               "Region": "STRING",
               "ProfileName": "STRING",
               "SlurmSpecifications": {
                  "NodeSpec1": "STRING",
                  "NodeSpec2": "STRING",
                  ...
               },
               "PurchasingOption": "spot|on-demand",
               "OnDemandOptions": DICT,
               "SpotOptions": DICT,
               "LaunchTemplateSpecification": DICT,
               "LaunchTemplateOverrides": ARRAY,
               "SubnetIds": [ "STRING" ],
               "Tags": [
                  {
                     "Key": "STRING",
                     "Value": "STRING"
                  }
               ]
            },
            ...
         ]
      },
      ...
   ]
}
```

* `Partitions`: List of partitions
   * `PartitionName`: Name of the partition. Must match the pattern `^[a-zA-Z0-9_]+$`.
   * `NodeGroups`: List of node groups for this partition. A node group is a set of nodes that share the same specifications.
      * `NodeGroupName`: Name of the node group. Must match the pattern `^[a-zA-Z0-9_]+$`.
      * `MaxNodes`: Maximum number of nodes that Slurm can launch for this node group. For each node group, `generate_conf.py` will issue a line with `NodeName=[partition_name]-[nodegroup_name][0-(max_nodes-1)]`
      * `Region`: Name of the AWS region where to launch EC2 instances for this node group. Example: `us-east-1`.
      * [OPTIONAL] `ProfileName`: Name of the AWS CLI profile to use to authenticate AWS requests. If you don't specify a profile name, it uses the default profile name of EC2 metadata credentials.
      * `SlurmSpecifications`: List of Slurm configuration attributes for this node group. For example if you provide `{"CPUs": 4, "Features": "us-east-1a"}` the script `generate_conf.py`will output `CPUs=4 Features=us-east-1a` in the configuration line related to this node group.
      * `PurchasingOption`: Possible values are `spot` or `on-demand`.
      * `OnDemandOptions`: Must be included if `PurchasingOption` is equal to `on-demand` and filled in the same way than the object of the same name in the [EC2 CreateFleet API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_fleet).
      * `SpotOptions`: Must be included if `PurchasingOption` is equal to `spot` and filled in the same way than the object of the same name in the [EC2 CreateFleet API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_fleet).
      * `LaunchTemplateSpecification`: Must be filled in the same way than the object of the same name in the [EC2 CreateFleet API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_fleet).
      * `LaunchTemplateOverrides`: Must be filled in the same way then the object of the same name in the [EC2 CreateFleet API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_fleet). Do not populate the field `SubnetId` in template overrides.
      * `SubnetIds`: List of subnets where EC2 instances can be launched for this node group. If you provide multiple subnets, they must be in different availability zones.
      * `Tags`: List of tags applied to the EC2 instances launched for this node group.

Refer to the section **Partitions examples** below for examples of `partitions.json`.

### `common.py`

This script contains variables and functions that are used by more than one Python scripts.

### `resume.py`

This file is the `ResumeProgram` program executed by Slurm to restore nodes in normal operation:

* It retrieves the list of nodes to resume, and for each partition and node group:
   * It creates an instant EC2 fleet to launch the requested number of EC2 instances. This call is synchronous and the response contains the list of EC2 instances that were launched. For each instance:
      * It creates a tag `Name` whose value is the name of the node `[partition_name]-[nodegroup_name][id]` and other tags if specified for this node group.
      * It updates the node IP address and host name in Slurm with `scontrol`.

You can manually try the program by running `/fullpath/resume.py (partition_name)-(nodegroup_name)(id)` such as  `/fullpath/resume.py partition-nodegroup0`.

### `suspend.py`

This script is the `SuspendProgram` executed by Slurm to place nodes in power saving mode:

* It retrieves the list of nodes to suspend, and for each node:
   * It finds the instance ID for this node
   * It terminates the instance

You can manually try the program by running `/fullpath/suspend.py (partition_name)-(nodegroup_name)(id)` such as  `/fullpath/suspend.py partition-nodegroup0`.

### `power_down.py`

This script is executed every minute by `cron` to unblock nodes that failed to respond within `ResumeTimeout` seconds. When this happens, the node is placed in a `DOWN*` state and the state must be set to `POWER_DOWN`. The node is then placed in `DOWN` state and the state must be changed to `IDLE` state, such that work can be assigned to them again.

### `generate_conf.py`

This script is used to generate the Slurm configuration that is specific to this plugin. You must append the content of the output file to `slurm.conf`.

## Prerequisites

1) You must have a Slurm headnode that is already functional. You can adapt the CloudFormation template provided with the [previous plugin](https://github.com/aws-samples/aws-plugin-for-slurm) if you want to provision the headnode on AWS.

2) You will need to provide one or more subnets in which the EC2 compute nodes will be launched. Private connectivity must be established between the headnode and these subnets, such as a VPN connection.

3) You will need to provide one or more [launch templates](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-templates.html) that will be used to launch EC2 compute nodes. Each launch template must include at least the AMI ID, one or more security groups to assign, the IAM instance profile (see Compute nodes below) and eventually the bootstrap script `UserData` to execute at launch to configure the Slurm client.

**Important**: The compute nodes must specify their cluster name when launching `slurmd`. The cluster name can be retrieved from the EC2 instance tag. If you use `systemctl` to launch Slurm, here is what you could do to automatically pass the node name when compute nodes start `slurmd`:

* Create a script that returns the node name from the EC2 tag, or the hostname if the tag value cannot be retrieved. You must have the AWS CLI installed to run this script, and you must attach an IAM role to the EC2 compute nodes that grants `ec2:DescribeInstances`. Adapt the full path of the script `/fullpath/get_nodename` to your own context:

```
cat > /fullpath/get_nodename <<'EOF'
instanceid=`/usr/bin/curl --fail -m 2 -s 169.254.169.254/latest/meta-data/instance-id`
if [[ ! -z "$instanceid" ]]
then
   region=`/usr/bin/curl --fail -s 169.254.169.254/latest/meta-data/placement/availability-zone`
   region=${region::-1}
   echo `/usr/bin/aws ec2 describe-tags --filters "Name=resource-id,Values=$instanceid" "Name=key,Values=Name" --region $region --query "Tags[0].Value" --output=text`
else
   echo `hostname`
fi
EOF
chmod +x /fullpath/get_nodename
```

* Add or change the following attributes in the service configuration file `/lib/systemd/system/slurmd.service`:

```
ExecStartPre=/bin/bash -c "/bin/systemctl set-environment SLURM_NODENAME=$(/fullpath/get_nodename)"
ExecStart=/nfs/slurm/sbin/slurmd -N $SLURM_NODENAME $SLURMD_OPTIONS
```

## Deployment instructions

1) Install Python 3 and boto3 on the headnode. You may also need the AWS CLI to configure AWS credentials:
```
sudo yum install python3 python3-pip -y
sudo pip3 install boto3
sudo pip3 install awscli
```

2) Copy the plugin files to a folder, such as `$SLURM_ROOT/etc/aws` and make the PY files executable.
```
# Command to copy the plugin files from the Git repository to the headnode
chmod +x *.py
```

3) If the headnode is located on-premises, you should configure AWS credentials. You can either configure the default AWS CLI profile, or create a custom profile that you will reference in `ProfileName`. See [Configuring the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) for detailed instructions. The minimum required IAM permissions are:

```
ec2:CreateFleet
ec2:RunInstances
ec2:TerminateInstances
ec2:CreateTags
ec2:DescribeInstances
iam:PassRole (can be restricted to the ARN of the EC2 role for compute nodes)
```

4) Create the JSON configuration files `config.json` and `partitions.json` in the same folder than the plugin files, and populate them as instructed in the **Plugin files** section.

5) Run `generate_conf.py` and append the content of the output file to `slurm.conf`. Refresh the Slurm configuration by running the command `scontrol reconfigure`.

6) Change the `cron` configuration to run the script `power_down.py` every minute.

```
sudo crontab -e
```

Add the following line into the file. Make sure to adapt the path `/path/power_down.py` to your own context.

```
* * * * * /path/power_down.py
```

# Partitions examples

## Example 1

Single `aws` partition with 2 node groups:

* One node group `ondemand` with up to 10 nodes that is used in priority (Slurm `Weight=1`)
* Another node group `spot` with up to 100 nodes and a lower priority (Slurm `Weight=2`). The scheduler will automatically launch and allocate jobs to the Spot instances when all the on-demand nodes are running and busy.

```
{
   "Partitions": [
      {
         "PartitionName": "aws",
         "NodeGroups": [
            {
               "NodeGroupName": "ondemand",
               "MaxNodes": 10,
               "Region": "us-east-1",
               "SlurmSpecifications": {
                  "CPUs": "4",
                  "Weight": "1"
               },
               "PurchasingOption": "on-demand",
               "OnDemandOptions": {
                   "AllocationStrategy": "lowest-price"
               },
               "LaunchTemplateSpecification": {
                  "LaunchTemplateName": "template-name",
                  "Version": "$Latest"
               },
               "LaunchTemplateOverrides": [
                  {
                     "InstanceType": "c5.xlarge"
                  }
               ],
               "SubnetIds": [
                  "subnet-11111111",
                  "subnet-22222222"
               ],
               "Tags": [
                  {
                     "Key": "NodeGroup",
                     "Value": "ondemand"
                  }
               ]
            },
            {
               "NodeGroupName": "spot",
               "MaxNodes": 100,
               "Region": "us-east-1",
               "SlurmSpecifications": {
                  "CPUs": "4",
                  "Weight": "2"
               },
               "PurchasingOption": "spot",
               "OnDemandOptions": {
                   "AllocationStrategy": "lowest-price"
               },
               "LaunchTemplateSpecification": {
                  "LaunchTemplateName": "template-name",
                  "Version": "$Latest"
               },
               "LaunchTemplateOverrides": [
                  {
                     "InstanceType": "c5.xlarge"
                  }
               ],
               "SubnetIds": [
                  "subnet-11111111",
                  "subnet-22222222"
               ],
               "Tags": [
                  {
                     "Key": "NodeGroup",
                     "Value": "spot"
                  }
               ]
            }
         ]
      }
   ]
}
```

## Example 2

Single `aws` partition with 3 node groups:

* One node group `spot_4vCPU` used by default (lowest Slurm weight) that launches Spot instances with c5.large or c4.large across two subnets in two different availability zones, with the lowest price strategy.
* Two node groups `spot_4vCPU_a` or `spot_4vCPU_b` that can be used by specifying the feature `us-east-1a` or `us-east-1b` to run a job with all nodes in the same availability zone.

```
{
   "Partitions": [
      {
         "PartitionName": "aws",
         "NodeGroups": [
            {
               "NodeGroupName": "spot_4vCPU",
               "MaxNodes": 100,
               "Region": "us-east-1",
               "SlurmSpecifications": {
                  "CPUs": "4",
                  "Weight": "1"
               },
               "PurchasingOption": "spot",
               "OnDemandOptions": {
                   "AllocationStrategy": "lowest-price"
               },
               "LaunchTemplateSpecification": {
                  "LaunchTemplateName": "template-name",
                  "Version": "$Latest"
               },
               "LaunchTemplateOverrides": [
                  {
                     "InstanceType": "c5.xlarge"
                  },
                  {
                     "InstanceType": "c4.xlarge"
                  }
               ],
               "SubnetIds": [
                  "subnet-11111111",
                  "subnet-22222222"
               ]
            },
            {
               "NodeGroupName": "spot_4vCPU_a",
               "MaxNodes": 100,
               "Region": "us-east-1",
               "SlurmSpecifications": {
                  "CPUs": "4",
                  "Features": "us-east-1a",
                  "Weight": "2"
               },
               "PurchasingOption": "spot",
               "OnDemandOptions": {
                   "AllocationStrategy": "lowest-price"
               },
               "LaunchTemplateSpecification": {
                  "LaunchTemplateName": "template-name",
                  "Version": "$Latest"
               },
               "LaunchTemplateOverrides": [
                  {
                     "InstanceType": "c5.xlarge"
                  },
                  {
                     "InstanceType": "c4.xlarge"
                  }
               ],
               "SubnetIds": [
                  "subnet-11111111"
               ]
            },
            {
               "NodeGroupName": "spot_4vCPU_b",
               "MaxNodes": 100,
               "Region": "us-east-1",
               "SlurmSpecifications": {
                  "CPUs": "4",
                  "Features": "us-east-1b",
                  "Weight": "2"
               },
               "PurchasingOption": "spot",
               "OnDemandOptions": {
                   "AllocationStrategy": "lowest-price"
               },
               "LaunchTemplateSpecification": {
                  "LaunchTemplateName": "template-name",
                  "Version": "$Latest"
               },
               "LaunchTemplateOverrides": [
                  {
                     "InstanceType": "c5.xlarge"
                  },
                  {
                     "InstanceType": "c4.xlarge"
                  }
               ],
               "SubnetIds": [
                  "subnet-22222222"
               ]
            }
         ]
      }
   ]
}
```

## Example 3

Two partitions `aws` and `aws_spot` with one node group in each. You could use Slurm access permissions to allow "standard" users to use only Spot instances, and "VIP" users to use Spot and On-demand instances.

```
{
   "Partitions": [
      {
         "PartitionName": "aws",
         "NodeGroups": [
            {
               "NodeGroupName": "node",
               "MaxNodes: 100,
               "Region": "us-east-1",
               "SlurmSpecifications: {
                  "CPUs": "4",
                  "Weight": "1"
               },
               "PurchasingOption": "on-demand",
               "OnDemandOptions": {
                   "AllocationStrategy": "lowest-price"
               },
               "LaunchTemplateSpecification": {
                  "LaunchTemplateName": "template-name",
                  "Version": "$Latest"
               },
               "LaunchTemplateOverrides": [
                  {
                     "InstanceType": "c5.xlarge"
                  },
                  {
                     "InstanceType": "c4.xlarge"
                  }
               ],
               "SubnetIds": [
                  "subnet-11111111",
                  "subnet-22222222"
               ]
            }
         }
      },
      {
         "PartitionName": "aws_spot",
         "NodeGroups": [
            {
               "NodeGroupName": "node",
               "MaxNodes: 100,
               "Region": "us-east-1",
               "SlurmSpecifications: {
                  "CPUs": "4",
                  "Weight": "1"
               },
               "PurchasingOption": "spot",
               "SpotOptions": {
                   "AllocationStrategy": "lowest-price"
               },
               "LaunchTemplateSpecification": {
                  "LaunchTemplateName": "template-name",
                  "Version": "$Latest"
               },
               "LaunchTemplateOverrides": [
                  {
                     "InstanceType": "c5.xlarge"
                  },
                  {
                     "InstanceType": "c4.xlarge"
                  }
               ],
               "SubnetIds": [
                  "subnet-11111111",
                  "subnet-22222222"
               ]
            }
         }
      }
   ]
}
```
