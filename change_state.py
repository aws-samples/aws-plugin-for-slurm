#!/usr/bin/python3
import json
import sys

import common


logger, config, partitions = common.get_common('change_state')

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

def change_state(node_name, new_state, reason=None):
    try:
        slurm_param = 'state=%s' %new_state
        if reason is not None:
            slurm_param += ' reason=%s' %reason
        common.update_node(node_name, slurm_param)
        logger.info('Set node %s to state %s' %(node_name, new_state))
    except Exception as e:
        logger.error('Failed to set node %s to state %s - %s' %(node_name, new_state, e))

# Extract node details and change the state if required
for line in lines:
    line_split = [i for i in line.split(' ') if '=' in i]
    node_attributes = {i.split('=')[0]: i.split('=')[1] for i in line_split}
    node_name = node_attributes['NodeName']
    node_states = node_attributes['State'].split('+')  # A node should have multiple states like IDLE+CLOUD+POWER

    # Power down nodes that are stuck in DOWN* or IDLE* state (node is not responding)
    if 'DOWN*' in node_states or 'IDLE*' in node_states:
        change_state(node_name, 'POWER_DOWN', reason='node_not_responding')

    # In some situations, a node may be placed in COMPLETING+DRAIN state by Slurm 
    # and remains stuck. In that case, force the node to become DOWN
    if 'COMPLETING' in node_states and 'DRAIN' in node_states:
        change_state(node_name, 'DOWN', reason='node_stuck')

    # If the node is DOWN and in power saving mode, set the node to IDLE
    if 'DOWN' in node_states and 'POWER' in node_states:
        change_state(node_name, 'IDLE')

    # If the node is DOWN but still up, power down the node
    if 'DOWN' in node_states and not 'POWER' in node_states:
        change_state(node_name, 'POWER_DOWN', reason='node_stuck')

    # If the node is in power saving mode but still draining, set the node to UNDRAIN
    if 'DRAIN' in node_states and 'POWER' in node_states:
        change_state(node_name, 'UNDRAIN')
