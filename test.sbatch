#!/bin/bash
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --constraint=[us-west-2a|us-west-2b|us-west-2c]

env

sleep 60
