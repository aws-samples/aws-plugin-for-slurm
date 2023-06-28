# AWS Plugin for Slurm - Version 2

> The [plugin](https://github.com/aws-samples/aws-plugin-for-slurm) initially released in 2018 has been entirely redeveloped. Major changes includes: support of EC2 Fleet capabilities such as Spot or instance type diversification, decoupling node names from instance host names or IP addresses, better error handling when a node fails to respond during its launch.

[Slurm](https://slurm.schedmd.com/) is a popular HPC cluster management system. This plugin enables the Slurm headnode to dynamically deploy and destroy compute resources in the cloud, regardless of where the headnode is executed. Traditional HPC clusters usually distribute jobs over a static set of resources. With this plugin, you can take advantage of the elasticity and pay-per-use model of the cloud to run jobs.

Typical use cases include:

* Bursting into the cloud to dynamically allocate resources in addition to your on-premises resources. This enables to run jobs faster, or to take advantage of the wide selection of AWS instance types to run jobs that have specific requirements, such as GPU-based workloads.

* Deploying a self-contained HPC cluster in the cloud, as an alternative approach to managed HPC clusters, such as [AWS ParallelCluster](https://aws.amazon.com/hpc/parallelcluster/).

## Table of Contents

* [Concepts](#tc_concepts)
* [Plugin files](#tc_files)
* [Manual deployment](#tc_manual)
* [Deployment with AWS CloudFormation](#tc_cloudformation)
* [Appendix: Examples of `partitions.json`](#tc_partitions)

<a name="tc_concepts"/>

## Concepts

This plugin relies on the existing Slurm power save logic (see [Power Saving Guide](https://slurm.schedmd.com/power_save.html) and [Cloud Scheduling Guide](https://slurm.schedmd.com/elastic_computing.html) in the Slurm documentation).

All nodes that Slurm may launch in AWS must be initially declared in the Slurm configuration, but their IP address and host name don't have to be specified in advance. These nodes are placed initially in a power saving mode. When work is assigned to them by the scheduler, the headnode executes the program `ResumeProgram` and passes the list of nodes to resume as argument. The program launches a new EC2 instance for each node, and updates the IP address and the host name in Slurm. After a idle period, when nodes are no longer required, the headnode executes the program `SuspendProgram` with the list of nodes to suspend as argument. The program terminates the associated EC2 instances, and the nodes are placed in power mode saving again.

This plugin consists of the programs that Slurm executes when nodes are restored in normal operation (`ResumeProgram`) or placed in power mode saving (`SuspendProgram`). It relies upon EC2 Fleet to launch instances.

<a name="tc_files"/>

## Plugin files

The plugin is composed of 5 Python files and 2 JSON configuration files. They all must reside in the same folder. This section details the purpose and format of each file.

### `config.json`

This JSON file specifies the plugin and Slurm configuration parameters.

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

This JSON file specifies the groups of nodes and associated partitions that Slurm can launch in AWS.

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
         ],
         "PartitionOptions": {
            "Option1": "STRING",
            "Option2": "STRING"
         }
      },
      ...
   ]
}
```

* `Partitions`: List of partitions
   * `PartitionName`: Name of the partition. Must match the pattern `^[a-zA-Z0-9]+$`.
   * `NodeGroups`: List of node groups for this partition. A node group is a set of nodes that share the same specifications.
      * `NodeGroupName`: Name of the node group. Must match the pattern `^[a-zA-Z0-9]+$`.
      * `MaxNodes`: Maximum number of nodes that Slurm can launch for this node group. For each node group, `generate_conf.py` will issue a line with `NodeName=[partition_name]-[nodegroup_name]-[0-(max_nodes-1)]`
      * `Region`: Name of the AWS region where to launch EC2 instances for this node group. Example: `us-east-1`.
      * [OPTIONAL] `ProfileName`: Name of the AWS CLI profile to use to authenticate AWS requests. If you don't specify a profile name, it uses the default profile name of EC2 metadata credentials.
      * `SlurmSpecifications`: List of Slurm configuration attributes for this node group. For example if you provide `{"CPUs": 4, "Features": "us-east-1a"}` the script `generate_conf.py`will output `CPUs=4 Features=us-east-1a` in the configuration line related to this node group.
      * `PurchasingOption`: Possible values are `spot` or `on-demand`.
      * `OnDemandOptions`: Must be included if `PurchasingOption` is equal to `on-demand` and filled in the same way than the object of the same name in the [EC2 CreateFleet API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_fleet).
      * `SpotOptions`: Must be included if `PurchasingOption` is equal to `spot` and filled in the same way than the object of the same name in the [EC2 CreateFleet API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_fleet).
      * `LaunchTemplateSpecification`: Must be filled in the same way than the object of the same name in the [EC2 CreateFleet API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_fleet).
      * `LaunchTemplateOverrides`: Must be filled in the same way then the object of the same name in the [EC2 CreateFleet API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_fleet). Do not populate the field `SubnetId` in template overrides.
      * `SubnetIds`: List of subnets where EC2 instances can be launched for this node group. If you provide multiple subnets, they must be in different availability zones, or the `CreateFleet` request may return the error message "The fleet configuration contains duplicate instance pools".
      * `Tags`: List of tags applied to the EC2 instances launched for this node group.
        * A tag `Name` is automatically added at launch, whose value is the name of the node `[partition_name]-[nodegroup_name]-[id]`. You should not delete or override this tag, because the script `suspend.py` uses it to find which instance is associated with the node to suspend.
        * You use the sequence `{ip_address}` in the value of tag, it will be replaced with the IP address. Similarly, `{node_name}` will be replaced with the name of the node, `{hostname}` with the EC2 hostname.
   * `PartitionOptions`: List of Slurm configuration attributes for the partition (optional).

Refer to the section **Examples of `partitions.json`** for examples of file content.

### `common.py`

This script contains variables and functions that are used by more than one Python scripts.

### `resume.py`

This script is the `ResumeProgram` program executed by Slurm to restore nodes in normal operation:

* It retrieves the list of nodes to resume, and for each partition and node group:
   * It creates an instant EC2 fleet to launch the requested number of EC2 instances. This call is synchronous and the response contains the list of EC2 instances that were launched. For each instance:
      * It creates a tag `Name` whose value is the name of the node `[partition_name]-[nodegroup_name]-[id]` and other tags if specified for this node group.
      * It updates the node IP address and host name in Slurm with `scontrol`.

You can manually try the resume program by running `/fullpath/resume.py (partition_name)-(nodegroup_name)-(id)` such as  `/fullpath/resume.py partition-nodegroup-0`.

### `suspend.py`

This script is the `SuspendProgram` executed by Slurm to place nodes in power saving mode:

* It retrieves the list of nodes to suspend, and for each node:
   * It finds the instance ID for this node
   * It terminates the instance

You can manually try the suspend program by running `/fullpath/suspend.py (partition_name)-(nodegroup_name)-(id)` such as  `/fullpath/suspend.py partition-nodegroup-0`.

### `change_state.py`

This script is executed every minute by `cron` to change the state of nodes that are stuck in a transient or undesired state. For example, compute nodes that failed to respond within `ResumeTimeout` seconds are placed in a `DOWN*` state and the state must be set to `POWER_DOWN`.

### `generate_conf.py`

This script is used to generate the Slurm configuration that is specific to this plugin. You must append the content of the output file to `slurm.conf`.

<a name="tc_manual"/>

## Manual deployment

### Prerequisites

* You must have a Slurm headnode that is already functional, no matter where it resides. The plugin was tested with Slurm 20.02.3, but it should be compatible with any Slurm version that supports power saving mode.

* You will need to provide one or more subnets in which the EC2 compute nodes will be launched. If the headnode is not running on AWS, you must establish private connectivity between the headnode and these subnets, such as a VPN connection.

* **Important**: The compute nodes must specify their cluster name when launching `slurmd`. The cluster name can be retrieved from the EC2 instance tag. If you use `systemctl` to launch Slurm, here is what you could do to automatically pass the node name when compute nodes start `slurmd`:

Create a script that returns the node name from the EC2 tag, or the hostname if the tag value cannot be retrieved. You must have the AWS CLI installed to run this script, and you must allow access to tags in instance metadata by setting `InstanceMetadataTags` to `enabled`. Adapt the full path of the script `/fullpath/get_nodename` to your own context:

```
cat > /fullpath/get_nodename <<'EOF'
instanceid=`/usr/bin/curl --fail -m 2 -s 169.254.169.254/latest/meta-data/instance-id`
if [[ ! -z "$instanceid" ]]; then
   hostname=`/usr/bin/curl -s http://169.254.169.254/latest/meta-data/tags/instance/Name`
fi
if [ ! -z "$hostname" -a "$hostname" != "None" ]; then
   echo $hostname
else
   echo `hostname`
fi
EOF
chmod +x /fullpath/get_nodename
```

Add or change the following attributes in the service configuration file `/lib/systemd/system/slurmd.service`:

```
ExecStartPre=/bin/bash -c "/bin/systemctl set-environment SLURM_NODENAME=$(/fullpath/get_nodename)"
ExecStart=/nfs/slurm/sbin/slurmd -N $SLURM_NODENAME $SLURMD_OPTIONS
```

### Instructions

1) Install Python 3 and boto3 on the headnode. You may also need the AWS CLI to configure AWS credentials:
```
sudo yum install python3 python3-pip -y
sudo pip3 install boto3
sudo pip3 install awscli
```

2) Copy the PY files to a folder, such as `$SLURM_ROOT/etc/aws` and make them files executable. Adapt the full path to your own context.

```
cd /fullpath
wget -q https://github.com/aws-samples/aws-plugin-for-slurm/raw/plugin-v2/common.py
wget -q https://github.com/aws-samples/aws-plugin-for-slurm/raw/plugin-v2/resume.py
wget -q https://github.com/aws-samples/aws-plugin-for-slurm/raw/plugin-v2/suspend.py
wget -q https://github.com/aws-samples/aws-plugin-for-slurm/raw/plugin-v2/generate_conf.py
wget -q https://github.com/aws-samples/aws-plugin-for-slurm/raw/plugin-v2/change_state.py 
chmod +x *.py
```

3) You need to grant the headnode AWS permissions to make EC2 requests.

If the headnode resides on AWS, create an IAM role for EC2 (see [Creating an IAM role](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html#create-iam-role)) with an inline policy that allows the actions below, and attach the role to the headnode (see [Attaching an IAM role to an instance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html#attach-iam-role)).

If the headnode is not on AWS, create an IAM user (see [Creating IAM users](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_create.html#id_users_create_console)) with an inline policy that allows the actions below. Create an access key for that user (see [Managing access keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html#Using_CreateAccessKey)). Then, configure AWS credentials on your headnode using the AWS CLI (see [Configuring the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)). You can either configure the default AWS CLI profile with `aws configure`, or create a custom profile with `aws configure --profile profile_name` that you will reference in `ProfileName`.

The minimum required permissions are:

```
ec2:CreateFleet
ec2:RunInstances
ec2:TerminateInstances
ec2:CreateTags
ec2:DescribeInstances
iam:CreateServiceLinkedRole (required if you never used EC2 Fleet in your account)
iam:PassRole (you can restrict this actions to the ARN of the EC2 role for compute nodes)
```

4) Create an IAM role for EC2 compute nodes that allows the action `ec2:DescribeTags` (see [Creating an IAM role](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html#create-iam-role)).

5) Create one or more EC2 launch templates that will be used to create EC2 compute nodes.

A launch template specifies some of the required instance configuration parameters. For each launch template, you must specify at least the AMI ID, the security group(s) to attach, the EC2 role, and eventually a key pair and some scripts to execute at launch with `UserData`. You will multiple launch templates if your EC2 compute nodes need various values for these parameters.

For example launch template to create, follow the instructions at [Creating a new launch template using parameters you define](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-templates.html#create-launch-template-define-parameters). Note the launch template name or launch template ID for later use.

6) Create the JSON configuration files `config.json` and `partitions.json` in the same folder than the PY files, and populate them as instructed in the **Plugin files** section.

7) Run `generate_conf.py` and append the content of the output file `slurm.conf.aws` to your Slurm configuration file `slurm.conf`. Refresh the Slurm configuration by running the command `scontrol reconfigure`, or by restarting Slurmctld.

Here is an example of output file:

```
PrivateData=CLOUD
ResumeProgram=/slurm/etc/aws/resume.py
SuspendRate=100
# ...More Slurm parameters

NodeName=aws-node-[0-99] State=CLOUD CPUs=4
Partition=aws Nodes=aws-node-[0-99] Default=No MaxTime=INFINITE State=UP
```

8) Change the `cron` configuration to run the script `change_state.py` every minute.

```
sudo crontab -e
```

If the Slurm user is not root, you could create the cron for that user instead `sudo crontab -e -u username`. Add the following line into the file. Make sure to adapt the path `/fullpath/change_state.py` to your own context.

```
* * * * * /fullpath/change_state.py &>/dev/null
```

<a name="tc_cloudformation"/>

## Deployment with AWS CloudFormation

You can use AWS CloudFormation to provision a sample pre-configured headnode on AWS. To proceed, create a new CloudFormation stack using the template that is provided in [`template.yaml`](template.yaml). You will need to specify an existing VPC and two subnets that are in two different availability zones where the head node and the compute nodes will be launched.

The stack will create the following resource:

* A security group that allows SSH traffic from the Internet and traffic between Slurm nodes
* Two IAM roles to grant necessary permissions to the head node and the compute nodes
* A launch template that will be used to launch compute nodes
* The head node. The stack returns the instance ID of the head node.

The plugin is configured with a single partition `aws` and a single node group `node` that contains up to 100 instances launched in on-demand mode.

To test the solution:

1) Connect onto the head node using SSH
2) You can run a `sbatch` or `srun` command to the `aws` partition, like `srun -p aws hostname`. You should see a new instance being launched in the Amazon EC2 console.
3) Once the job is completed, the node will remains idle during `SuspendTime` seconds and will be terminated.

<a name="tc_partitions"/>

## Appendix: Examples of `partitions.json`

### Example 1

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
         ],
         "PartitionOptions": {
            "Default": "yes",
            "TRESBillingWeights": "cpu=4"
         }
      }
   ]
}
```

### Example 2

Single `aws` partition with 3 node groups:

* One node group `spot4vCPU` used by default (lowest Slurm weight) that launches Spot instances with c5.large or c4.large across two subnets in two different availability zones, with the lowest price strategy.
* Two node groups `spot4vCPUa` or `spot4vCPUb` that can be used by specifying the feature `us-east-1a` or `us-east-1b` to run a job with all nodes in the same availability zone.

```
{
   "Partitions": [
      {
         "PartitionName": "aws",
         "NodeGroups": [
            {
               "NodeGroupName": "spot4vCPU",
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
               "NodeGroupName": "spot4vCPUa",
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
               "NodeGroupName": "spot4vCPUb",
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

### Example 3

Two partitions `aws` and `awsspot` with one node group in each. It uses Slurm access permissions to allow users in the "standard" account to use only Spot instances, and "VIP" account users to use Spot and On-demand instances, but weights the on-demand instances more heavily for accounting purposes.

```
{
   "Partitions": [
      {
         "PartitionName": "aws",
         "NodeGroups": [
            {
               "NodeGroupName": "node",
               "MaxNodes": 100,
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
         ],
         "PartitionOptions": {
            "TRESBillingWeights": "cpu=30",
            "AllowAccounts": "standard,VIP"
         }
      },
      {
         "PartitionName": "awsspot",
         "NodeGroups": [
            {
               "NodeGroupName": "node",
               "MaxNodes": 100,
               "Region": "us-east-1",
               "SlurmSpecifications": {
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
         ],
         "PartitionOptions": {
            "TRESBillingWeights": "cpu=10",
            "AllowAccounts": "standard"
         }
      }
   ]
}
```
