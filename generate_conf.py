#!/usr/bin/python3
import common


logger, config, partitions = common.get_common('generate_conf')

slurm_filename = 'slurm.conf.aws'
gres_filename = 'gres.conf.aws'

# This script generates a file to append to slurm.conf
with open(slurm_filename, 'w') as f:
    
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
        line = 'PartitionName=%s Nodes=%s MaxTime=INFINITE State=UP %s' %(partition['PartitionName'], ','.join(partition_nodes), ' '.join(part_options))
        f.write('%s\n\n' %line)

    logger.info('Output slurm.conf file: %s' %slurm_filename)

# This script generates a file to append to gres.conf
with open(gres_filename, 'w') as g:
    for partition in partitions:
        
        for nodegroup in partition['NodeGroups']:
            nodes = common.get_node_range(partition, nodegroup)
            for key, value in nodegroup['SlurmSpecifications'].items():
                if key.upper() == "GRES":

                    # Write a line for each node group with Gres
                    fields=value.split(':')
                    if len(fields) == 2:
                        name=fields[0]
                        qty=fields[1]
                        typestring=""
                    elif len(fields) == 3:
                        name=fields[0]
                        typestring="Type=%s" % fields[1]
                        qty=fields[2]
                    else:
                        assert false, "Invalid GRES field in %" % nodegroup

                    if name.upper() == "GPU":
                        qty=int(qty)
                        if qty == 1:
                            gresfilestring="File=/dev/nvidia[0]"
                        else:
                            gresfilestring="File=/dev/nvidia[0-%d]"%(int(qty) - 1)
                    else:
                        gresfilestring=""

                    line='NodeName=%s Name=%s %s %s' %(nodes, name, typestring, gresfilestring)
                    g.write('%s\n' %line)

    logger.info('Output gres.conf file: %s' %gres_filename)
