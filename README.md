## AWS Plugin for Slurm

A sample integration of AWS services with Slurm

## License Summary

This sample code is made available under a modified MIT license. See the LICENSE file.

## Requirements

You will need an AWS Account with S3 Read/Write permissions. As well as the ability to execute CloudFormation scripts. The cloudformation script will provision a landing zone with a public subnet and 3 private subnets each private subnet will route into the public subnet via a NAT Gateway. Permissions to create the network topology will be needed.

<p align="center">
  <img src="/imgs/slurm-burst.png?raw=true" alt="SLURM Bursting Network"/>
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

3) Open the AWS Cloudformation Console and upload the slurm_headnode_cloudformation.yml under the Cloudformation -> Create Stack

<p align="center">
  <img src="/imgs/slurm-cf.png?raw=true" alt="SLURM CloudFormation Template"/>
</p>