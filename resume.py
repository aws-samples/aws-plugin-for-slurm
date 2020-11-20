#!/usr/bin/python3
import copy
import json
import re
import sys
import time

import common


logger, config, partitions = common.get_common('resume')


# Retry in case the request failed because of eventual consistency
def retry(func, *args, **kwargs):
    nb_retry = 1
    MAX_RETRIES = 3
    while True:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if nb_retry <= MAX_RETRIES:
                logger.debug('Failed %s %d time(s): %s', func.__name__, nb_retry, e)
                nb_retry += 1
                time.sleep(nb_retry)
            else:
                raise e


# Retrieve the list of hosts to resume
try:
    hostlist = sys.argv[1]
    logger.info('Hostlist: %s' %hostlist)
except:
    logger.critical('Missing hostlist argument')
    sys.exit(1)

# Expand the hoslist and retrieve a list of node names
expanded_hostlist = common.expand_hostlist(hostlist)
logger.debug('Expanded hostlist: %s' %', '.join(expanded_hostlist))

# Parse the expanded hostlist
nodes_to_resume = common.parse_node_names(expanded_hostlist)
logger.debug('Nodes to resume: %s', json.dumps(nodes_to_resume, indent=4))

for partition_name, nodegroups in nodes_to_resume.items():
    for nodegroup_name, node_ids in nodegroups.items():
        
        nb_nodes_to_resume = len(node_ids)
        nodegroup = common.get_partition_nodegroup(partition_name, nodegroup_name)
        
        # Ignore if the partition and the node group are not in partitions.json
        if nodegroup is None:
            logger.warning('Skipping partition=%s nodegroup=%s: not in partition.json' %(partition_name, nodegroup_name))
            continue
        
        client = common.get_ec2_client(nodegroup)

        # Create a dict for the EC2 CreateFleet request
        request_fleet = {
            'LaunchTemplateConfigs': [
                {
                    'LaunchTemplateSpecification': nodegroup['LaunchTemplateSpecification'],
                    'Overrides': []
                }
            ],
            'TargetCapacitySpecification': {
                'TotalTargetCapacity': nb_nodes_to_resume,
                'DefaultTargetCapacityType': nodegroup['PurchasingOption']
            },
            'Type': 'instant'
        }
            
        # Populate on-demand options
        if 'OnDemandOptions' in nodegroup:
            request_fleet['OnDemandOptions'] = nodegroup['OnDemandOptions']
        
        # Populate spot options
        if 'SpotOptions' in nodegroup:
            request_fleet['SpotOptions'] = nodegroup['SpotOptions']
            request_fleet['SpotOptions']['InstanceInterruptionBehavior'] = 'terminate'
            
        # Populate launch configuration overrides. Duplicate overrides for each subnet
        for override in nodegroup['LaunchTemplateOverrides']:
            for subnet in nodegroup['SubnetIds']:
                override_copy = copy.deepcopy(override)
                override_copy['SubnetId'] = subnet
                override_copy['WeightedCapacity'] = 1
                request_fleet['LaunchTemplateConfigs'][0]['Overrides'].append(override_copy)

        # Create an EC2 fleet
        try:
            logger.debug('EC2 CreateFleet request: %s' %json.dumps(request_fleet, indent=4))
            response_fleet = client.create_fleet(**request_fleet)
            logger.debug('EC2 CreateFleet response: %s' %json.dumps(response_fleet, indent=4))
        except Exception as e:
            logger.error('Failed to launch nodes for partition=%s and nodegroup=%s - %s' %(partition_name, nodegroup_name, e))
            continue
        
        # This variable will be used as an incremental index of node_ids
        node_id_index = 0
        
        # For all instances that were successfully launched
        for instance in response_fleet['Instances']:
            
            # Retrieve additional instance details
            try:
                response_describe = retry(client.describe_instances, InstanceIds=instance['InstanceIds'])
            except Exception as e:
                logger.error('Failed to describe instances %s: %s' %(', '.join(instance['InstanceIds']), e))
                continue
            
            # For each instance that was successfully launched
            for instance_id in instance['InstanceIds']:
                node_id = node_ids[node_id_index]
                node_id_index += 1
                node_name = common.get_node_name(partition_name, nodegroup_name, node_id)
                
                # Isolate details for the current instance
                for reservation in response_describe['Reservations']:
                    for instance_details in reservation['Instances']:
                        if instance_details['InstanceId'] == instance_id:
                            ip_address = instance_details['PrivateIpAddress']
                            hostname = 'ip-%s' %'-'.join(ip_address.split('.'))
                            
                logger.info('Launched node %s %s %s' %(node_name, instance_id, ip_address))
                
                # Tag the instance
                tags = [
                    {
                        'Key': 'Name',
                        'Value': '{node_name}'
                    }
                ]
                if 'Tags' in nodegroup:
                    tags += nodegroup['Tags']

                # Replace the following sequences with context values
                # For example, replace {ip_address} with the private IP address
                sequences = (
                    ('{ip_address}', ip_address),
                    ('{node_name}', node_name),
                    ('{hostname}', hostname)
                )
                for tag in tags:
                    for sequence in sequences:
                      tag['Value'] = tag['Value'].replace(*sequence)

                try:
                    request_tags = {
                        'Resources': [instance_id],
                        'Tags': tags
                    }
                    retry(client.create_tags, **request_tags)
                    logger.debug('Tagged node %s: %s' %(node_name, json.dumps(request_tags, indent=4)))
                except Exception as e:
                    logger.error('Failed to tag node %s - %s' %(node_name, e))
                    continue
                
                # Update node information in Slurm
                try:
                    slurm_param = 'nodeaddr=%s nodehostname=%s' %(ip_address, hostname)
                    common.update_node(node_name, slurm_param)
                    logger.debug('Updated node information in Slurm %s' %node_name)
                except Exception as e:
                    logger.error('Failed to update node information in Slurm %s - %s' %(node_name, e))

        # Log how many nodes failed to launch
        nb_failed_nodes = nb_nodes_to_resume - node_id_index
        if nb_failed_nodes > 0:
            logger.warning('Failed to launch %s nodes' %nb_failed_nodes)

        # Log EC2 fleet errors
        error_codes = []
        for error in response_fleet['Errors']:
            override = error['LaunchTemplateAndOverrides']['Overrides']
            logger.debug('EC2 Fleet error - %s - Instance type: %s Subnet: %s Lifecycle: %s' %(
                error['ErrorMessage'], override['InstanceType'], override['SubnetId'],
                error['Lifecycle']
            ))
            if not error['ErrorCode'] in error_codes:
                error_codes.append(error['ErrorCode'])

        if len(error_codes) > 0:
            logger.warning('EC2 Fleet error codes: %s' %', '.join(error_codes))
