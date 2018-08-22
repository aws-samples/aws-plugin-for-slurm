## AWS Plugin for Slurm

A sample integration of AWS services with Slurm

## License Summary

This sample code is made available under a modified MIT license. See the LICENSE file.

## Requirements

You will need an AWS Account with S3 Read/Write permissions. As well as the ability to execute CloudFormation scripts. The cloudformation script will provision a landing zone with a public subnet and 3 private subnets each private subnet will route into the public subnet via a NAT Gateway. Permissions to create the network topology will be needed.

<p align="center">
  <img src="/imgs/slurm-burst.png?raw=true" alt="SLURM Bursting Network" width="500" height="500"/>
</p>

You can optionally add an EFS endpoint so that all ephemeral SLURM compute nodes and the headnode can have a common namespace.

## Instructions

1) Clone the github and sync the contents into a S3 bucket which will be used later to stand up the cluster.
2) Download the SLURM source from SchedMD [here](https://www.schedmd.com/downloads.php) and copy into the S3 bucket created earlier.
3) Edit slurm_headnode_cloudformation.yml file with the version of the SLURM source used:

```python
  SlurmVersion:
    Description: Select SLURM version to install
    Type: String
    Default: 17.11.8
    AllowedValues:
      - 17.11.8
```

4) Open the AWS Cloudformation Console and upload the slurm_headnode_cloudformation.yml under the Cloudformation -> Create Stack

<p align="center">
  <img src="/imgs/slurm-cf.png?raw=true" alt="SLURM CloudFormation Template"/>
</p>

The cloudformation will create the 1 Public and 3 Private Subnets and a single EC2 Instance as the SLURM Headnode. The SLURM source package you uploaded earlier will be retrieved, extracted, and the SLURM stack will be installed. A NFS server will be setup which will be used a common namespace for the slurm configuration.

5) The elastic compute portion of the slurm.conf can be found at ```/nfs/slurm/etc/slurm.conf``` 

```bash
SuspendTime=60
ResumeTimeout=250
TreeWidth=60000
SuspendExcNodes=ip-10-0-0-251
SuspendProgram=/nfs/slurm/bin/slurm-aws-shutdown.sh
ResumeProgram=/nfs/slurm/bin/slurm-aws-startup.sh
ResumeRate=0
SuspendRate=0
```
You will find explainations of the parameters on the [SLURM Elastic Computing - SchedMD](https://slurm.schedmd.com/elastic_computing.html).

6) Example of the running the slurm ephermal cluster, in the initial state the ```sinfo``` shows that no nodes are currently available. Once the ```test.sbatch``` file is submitted 2 nodes will be stood up (executed by the ResumeProgram) added to the cluster and will be ready for work.

<p align="center">
  <img src="/imgs/slurm-submit.gif?raw=true" alt="SLURM Bursting"/>
</p>

NOTE: The cluster will just allow the ephemeral nodes to be stood up in a single AZ. For additional AZs follow the example the in ```/nfs/slurm/etc/slrum.conf.d/slurm_nodes.conf```

```bash
NodeName=ip-10-0-1-[6-250] CPUs=8 Feature=us-west-2a State=Cloud
NodeName=ip-10-0-2-[6-250] CPUs=8 Feature=us-west-2b State=Cloud
NodeName=ip-10-0-3-[6-250] CPUs=8 Feature=us-west-2c State=Cloud
``