#!/usr/bin/python3
import json
import sys

import common


logger, config, partitions = common.get_common('power_down')

# Populate a hostlist with all AWS nodes
hostlist = []
for partition in partitions:
    for nodegroup in partition['NodeGroups']:
        hostlist.append(common.get_node_range(partition, nodegroup))

# Retrieve nodes information using 'scontrol show node'
try:
    arguments = ['show', 'node', ','.join(hostlist), '-o']
    lines = common.run_scommand('scontrol', arguments)
except Exception as e:
    logger.critical('Failed to get nodes info - %s' %e)
    sys.exit(1)

# Extract node details and evaluate state
for line in lines:
    line_split = [i for i in line.split(' ') if '=' in i]
    node_attributes = {i.split('=')[0]: i.split('=')[1] for i in line_split}
    node_name = node_attributes['NodeName']
    node_states = node_attributes['State'].split('+')  # A node should have multiple states like IDLE+CLOUD+POWER

    # Skip the node if it is in a transient state
    if 'POWERING_DOWN' in node_states:
        continue
    
    # Power down nodes that are stuck in DOWN* or IDLE* state
    if 'DOWN*' in node_states or 'IDLE*' in node_states:
        try:
            slurm_param = 'state=POWER_DOWN reason=node_stuck'
            common.update_node(node_name, slurm_param)
            logger.info('Set node state %s to POWER_DOWN' %node_name)
        except Exception as e:
            logger.error('Failed to set node state %s to POWER_DOWN - %s' %(node_name, e))

    # Set node state to IDLE if it is in DOWN state
    if 'DOWN' in node_states:
        try:
            slurm_param = 'state=IDLE'
            common.update_node(node_name, slurm_param)
            logger.info('Set node state %s to IDLE' %node_name)
        except Exception as e:
            logger.error('Failed to set node state %s to IDLE - %s' %(node_name, e))

    # Set node state to UNDRAIN if it is in DRAIN and POWER states
    if 'DRAIN' in node_states and 'POWER' in node_states:
        try:
            slurm_param = 'state=UNDRAIN'
            common.update_node(node_name, slurm_param)
            logger.info('Set node state %s to UNDRAIN' %node_name)
        except Exception as e:
            logger.error('Failed to set node state %s to UNDRAIN - %s' %(node_name, e))
