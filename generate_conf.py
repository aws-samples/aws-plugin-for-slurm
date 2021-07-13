#!/usr/bin/python3
import common


logger, config, partitions = common.get_common('generate_conf')

filename = 'slurm.conf.aws'

# This script generates a file to append to slurm.conf
with open(filename, 'w') as f:
    
    # Write Slurm configuration parameters
    for item, value in config['SlurmConf'].items():
        f.write('%s=%s\n' %(item, value))
    f.write('\n')
    
    for partition in partitions:
        partition_nodes = ()
        
        for nodegroup in partition['NodeGroups']:
            nodes = common.get_node_range(partition, nodegroup)
            partition_nodes += nodes,
            
            nodegroup_specs = ()
            for key, value in nodegroup['SlurmSpecifications'].items():
                nodegroup_specs += '%s=%s' %(key, value),
            
            # Write a line for each node group
            line = 'NodeName=%s State=CLOUD %s' %(nodes, ' '.join(nodegroup_specs))
            f.write('%s\n' %line)

        part_options = ()
        if 'PartitionOptions' in partition:
            for key, value in partition['PartitionOptions'].items():
                part_options += '%s=%s' %(key, value),

        # Write a line for each partition
        line = 'PartitionName=%s Nodes=%s Default=No MaxTime=INFINITE State=UP %s' %(partition['PartitionName'], ','.join(partition_nodes), ' '.join(part_options))
        f.write('%s\n\n' %line)

    logger.info('Output file: %s' %filename)
