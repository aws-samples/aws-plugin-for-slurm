#!/usr/bin/python3
import json
import sys

import common


logger, config, partitions = common.get_common('suspend')

# Retrieve the list of hosts to suspend
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
nodes_to_suspend = common.parse_node_names(expanded_hostlist)
logger.debug('Nodes to suspend: %s', json.dumps(nodes_to_suspend, indent=4))

for partition_name, nodegroups in nodes_to_suspend.items():
    for nodegroup_name, node_ids in nodegroups.items():
        
        nodegroup = common.get_partition_nodegroup(partition_name, nodegroup_name)

        # Ignore if the partition and the node group are not in partitions.json
        if nodegroup is None:
            logger.warning('Skipping partition=%s nodegroup=%s: not in partition.json' %(partition_name, nodegroup_name))
            continue

        client = common.get_ec2_client(nodegroup)
        
        # Retrieve the list of instances to terminate based on the tag Name
        instances_to_terminate = [common.get_node_name(partition_name, nodegroup_name, i) for i in node_ids]
        try:
            response_describe = client.describe_instances(
                Filters=[
                    {'Name': 'tag:Name', 'Values': instances_to_terminate},
                    {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']}
                ]
            )
        except Exception as e:
            logger.critical('Failed to describe instances to terminate - %s' %e)
        
        # Terminate each instance
        for reservation in response_describe['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                
                try:
                    for tag in instance['Tags']:
                        if tag['Key'] == 'Name':
                            node_name = tag['Value']
                            
                    client.terminate_instances(InstanceIds=[instance_id])
                    logger.info('Terminated instance %s %s' %(node_name, instance_id))
                except Exception as e:
                    logger.info('Failed to terminate instance %s %s' %(node_name, instance_id))
                