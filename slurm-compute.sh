#!/bin/bash
RELEASE=unknown

if [ -f /etc/system-release ]; then
   if grep -q "CentOS" /etc/system-release; then
      RELEASE=centos
   elif grep -q "Red" /etc/system-release; then
      RELEASE=rhel
   elif grep -q "Amazon" /etc/system-release; then
      RELEASE=amazon
   fi
elif lsb_release -d | grep -q "Ubuntu"; then
   RELEASE=ubuntu
   echo "Slurm Install on Ubuntu/Debian is not supported at this moment"
   exit 0
fi

echo $RELEASE

# Setup MUNGE
if [ $RELEASE == "centos" ] || [ $RELEASE == "rhel" ]; then
   sudo yum --nogpgcheck install epel-release -y
   sudo yum --nogpgcheck install munge munge-libs munge-devel -y
elif [ $RELEASE == "amazon" ]; then
   sed -i "s|enabled=0|enabled=1|g" /etc/yum.repos.d/epel.repo
   sudo yum install munge munge-libs munge-devel -y
fi


echo "welcometoslurmamazonuserwelcometoslurmamazonuserwelcometoslurmamazonuser" | sudo tee /etc/munge/munge.key
sudo chown munge:munge /etc/munge/munge.key
sudo chmod 600 /etc/munge/munge.key
sudo chown -R munge /etc/munge/ /var/log/munge/
sudo chmod 0700 /etc/munge/ /var/log/munge/

sudo systemctl enable munge
sudo systemctl start munge

sleep 15

#Setup SLURM
sudo yum install openssl openssl-devel pam-devel numactl numactl-devel hwloc hwloc-devel lua lua-devel \
                 readline-devel rrdtool-devel ncurses-devel man2html libibmad libibumad rpm-build -y

#Mount SLURM NFS
sudo mkdir -p /nfs
sudo mount -t nfs $1:/nfs /nfs

export SLURM_HOME=/nfs/slurm

#Calculate n GPUs
if [ -z /dev/nvidia* ]; then
   NUM_GPUS=$(ls -l /dev/nvidia* | wc -l)
   export GPU_STANZA=$(echo `Gres=gpu:$NUM_GPUS`)
   for i in $(seq 0 `expr $NUM_GPUS - 1`); do
       export SLURM_COMPUTE_NODE=$(echo `/nfs/slurm/sbin/slurmd -C` | cut -d " " -f1)
       echo $SLURM_COMPUTE_NODE Name=gpu File=/dev/nvidia$i | sudo -E tee -a $SLURM_HOME/etc/gres.conf
   done
fi


export SLURM_COMPUTE=$(echo `/nfs/slurm/sbin/slurmd -C` | cut -d " " -f1,2,5,6,7)

#echo NodeName=$2 $SLURM_COMPUTE NodeHostname=$HOSTNAME State=CLOUD $GPU_STANZA | sudo -E tee -a $SLURM_HOME/etc/slurm.conf.d/slurm_nodes.conf

sudo mkdir -p /var/spool/slurm
sudo -E cp $SLURM_HOME/etc/slurm/slurmd.service /lib/systemd/system
sudo systemctl enable slurmd.service
sudo systemctl start slurmd.service
